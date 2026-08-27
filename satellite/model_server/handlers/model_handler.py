import hashlib
import json
import logging
import os
import shutil
import tempfile
import traceback
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from clients.agent_client import AgentClient
from conda_manager import ModelCondaManager
from fnnx.envs.conda import CondaLikeEnvManager, install_micromamba
from utils.logging import log_success  # type: ignore

from .file_handler import ArtifactAccessExpired, FileHandler

logger = logging.getLogger(__name__)


class ModelHandler:
    def __init__(self, url: str | None = None, agent: AgentClient | None = None) -> None:
        # A URL passed in directly is a caller that already has one (tests, local runs);
        # otherwise the Agent is asked for one at the moment it is needed.
        self._model_url = url
        self._agent = agent or AgentClient()
        self._models_cache_dir = self._get_model_cache_dir()
        self._file_handler = FileHandler()
        self._request_model_schema = None
        self._response_model_schema = None
        self._model_envs = None
        self.conda_worker: ModelCondaManager | None = None

        try:
            self.extracted_path = self._get_or_extract_model()
            self._model_envs = self._create_model_env()

            self.conda_worker = ModelCondaManager(
                self._get_env_name(),
                self._model_envs["manager"],
                self.extracted_path,
                self._get_model_data_for_worker(),
            )
            self.conda_worker.start()
        except Exception as error:
            logger.error(
                f"Model handler initialization failed: {error}\nTraceback: {traceback.format_exc()}"
            )
            raise

    @log_success("Model data for worker generated successfully.")
    def _get_model_data_for_worker(self) -> dict[str, Any]:
        return {
            "model_name": os.getenv("MODEL_NAME", ""),
            "manifest": self._get_manifest(),
            "dtypes_schemas": self._load_dtypes_schemas(),
            "reference_profile": self._get_reference_profile(),
            "model_path": self.extracted_path,
        }

    @staticmethod
    def _get_model_cache_dir() -> Path:
        models_cache_dir = Path("/app/models")
        models_cache_dir.mkdir(parents=True, exist_ok=True)
        return models_cache_dir

    @staticmethod
    def _generate_model_id(url: str) -> str:
        """Fallback cache key for a caller that supplied its own URL and no artifact id."""
        parsed_url = urlparse(url)
        url_path = parsed_url.path.split("?")[0]
        return hashlib.md5(url_path.encode()).hexdigest()

    def _download_with_retry(self, url: str) -> Path:
        """Download, and on a refused URL ask the Agent for one more and try again.

        A large artifact can outlive its own link: the URL is signed before the transfer
        starts and may expire part-way through. One retry with a freshly signed URL covers
        that without turning a genuinely revoked artifact into a retry loop.
        """
        try:
            return self._download_model(url)
        except ArtifactAccessExpired:
            if self._caller_supplied_url():  # caller-supplied URL: nothing fresher to ask
                raise
            logger.warning("Download URL was refused; asking the Agent for a fresh one.")
            fresh_url, _ = self._resolve_artifact()
            return self._download_model(fresh_url)

    @log_success("Model downloaded successfully.")
    def _download_model(self, url: str) -> Path:
        temp_dir = tempfile.mkdtemp(prefix="dfs_model_download_")
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name.split("?")[0] or "model.dfs"
        model_archive_path = Path(temp_dir) / filename
        self._file_handler.download_file(url, model_archive_path)
        return model_archive_path

    @log_success("Model archive removed successfully.")
    def _clean_model_archive(self, file_path: Path) -> None:
        self._file_handler.remove_file(file_path)

    @log_success("Model unpacked successfully.")
    def _unpack_model_archive(self, model_archive_path: Path, extraction_dir: Path) -> str:
        return self._file_handler.unpack_tar_archive(model_archive_path, extraction_dir)

    def _caller_supplied_url(self) -> str | None:
        """A download URL the container was handed instead of a token, if any.

        Tests and local runs pass one directly; an Agent from before the token contract
        passes one through MODEL_ARTIFACT_URL. Both must be honoured — a new image
        launched by an old Agent holds a perfectly valid link and nothing else, and
        ignoring it would crash-loop a container that has everything it needs.
        """
        return self._model_url or os.getenv("MODEL_ARTIFACT_URL") or None

    def _known_model_id(self) -> str | None:
        """The cache key, if it can be known without asking anyone.

        The Agent pins it in the environment when it creates the container, so a model that
        is already unpacked can be found with no network at all. A caller that supplied its
        own URL keys on that instead.
        """
        url = self._caller_supplied_url()
        if url:
            return self._generate_model_id(url)
        return os.getenv("MODEL_ARTIFACT_ID") or None

    def _resolve_artifact(self) -> tuple[str, str]:
        """The download URL and the cache key, asking the Agent for a link signed just now.

        A presigned URL expires in hours while this container lives for weeks, so the only
        link that can be trusted is one minted for this request.
        """
        url = self._caller_supplied_url()
        if url:
            return url, self._generate_model_id(url)
        artifact = self._agent.fetch_artifact()
        return artifact.url, artifact.artifact_id

    @log_success("Unpacked Model path extracted successfully.")
    def _get_or_extract_model(self) -> str:
        """The extracted model, from the shared cache when it is already there.

        The cache is checked before anything is asked of anyone, so a container whose model
        is already unpacked comes back up even while the Agent or the Platform is down. Only
        a miss needs a download URL, and that one is minted on the spot.
        """
        known_id = self._known_model_id()
        if known_id:
            cached = self._models_cache_dir / known_id
            if self._file_handler.dir_exist(cached):
                logger.info(f"Using cached model {known_id} from {cached}")
                return str(cached)

        url, model_id = self._resolve_artifact()
        extraction_dir = self._models_cache_dir / model_id

        if self._file_handler.dir_exist(extraction_dir):
            logger.info(f"Using cached model {model_id} from {extraction_dir}")
            return str(extraction_dir)

        logger.info("Model not in cache, downloading...")
        model_archive_path = self._download_with_retry(url)

        # Unpacked beside the target and moved into place only once complete. Extracting
        # straight into the cache would leave a half-unpacked model behind on a crash, and
        # the next start would read it as a hit — a poisoned cache that survives restarts
        # and needs the volume cleaned by hand.
        #
        # The staging directory is unique per attempt because the cache is shared by every
        # model container on this Satellite: two deployments of the same artifact can be
        # unpacking it at the same moment, and a shared staging path would have them
        # overwriting each other's half-written files.
        staging_dir = self._models_cache_dir / f".{model_id}.{os.getpid()}.{uuid4().hex}.partial"
        try:
            self._unpack_model_archive(model_archive_path, staging_dir)
            try:
                os.replace(staging_dir, extraction_dir)
            except OSError:
                # Someone else finished first. Their copy is as good as ours — the archive
                # is immutable — so keep theirs and drop ours.
                if not self._file_handler.dir_exist(extraction_dir):
                    raise
                logger.info(f"Model {model_id} was cached by another container; using it.")
                shutil.rmtree(staging_dir, ignore_errors=True)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        finally:
            self._clean_model_archive(model_archive_path)

        return str(extraction_dir)

    @log_success("Model manifest.json loaded successfully.")
    def _get_manifest(self) -> dict[str, Any]:
        manifest_path = Path(self.extracted_path) / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                return json.load(f)
        return {}

    def _get_reference_profile(self) -> dict[str, Any]:
        profile_path = Path(self.extracted_path) / "reference_profile.json"
        if profile_path.exists():
            with open(profile_path) as f:
                return json.load(f)
        return {}

    def _get_env(self) -> dict[str, Any] | None:
        env_path = Path(self.extracted_path) / "env.json"
        if env_path.exists():
            with open(env_path) as f:
                return json.load(f)
        return None

    @log_success("Model dtypes.json loaded successfully.")
    def _load_dtypes_schemas(self) -> dict[str, Any]:
        dtypes_path = Path(self.extracted_path) / "dtypes.json"
        if dtypes_path.exists():
            with open(dtypes_path) as f:
                return json.load(f)
        return {}

    def _get_env_name(self) -> str:
        if not self._model_envs:
            raise ValueError("Model environment not initialized")
        if self._model_envs.get("path"):
            return self._model_envs["path"].split("/")[-1]
        else:
            return self._model_envs["name"]

    @staticmethod
    def _get_default_env_spec() -> dict[str, Any]:
        return {
            "python3::conda_pip": {
                "python_version": "3.12.6",
                "build_dependencies": [],
                "dependencies": [
                    {
                        "package": f"uvicorn=={importlib_metadata.version('uvicorn')}",
                        "extra_pip_args": None,
                        "condition": None,
                    },
                    {
                        "package": f"fnnx[core]=={importlib_metadata.version('fnnx')}",
                        "extra_pip_args": None,
                        "condition": None,
                    },
                ],
            }
        }

    @log_success("Model env created successfully.")
    def _create_model_env(self) -> dict[str, Any]:
        env_spec = self._get_env()
        if not env_spec:
            env_spec = self._get_default_env_spec()

        try:
            install_micromamba()
            env_type, env_config = next(iter(env_spec.items()))

            if "dependencies" not in env_config:
                env_config["dependencies"] = []

            existing_packages = set()
            for dep in env_config["dependencies"]:
                if isinstance(dep, dict) and "package" in dep:
                    existing_packages.add(
                        dep["package"].split("==")[0].split(">=")[0].split("<=")[0].strip()
                    )
            for pkg_name in [
                "uvicorn",
                "opentelemetry-api",
                "opentelemetry-sdk",
                "opentelemetry-exporter-otlp-proto-grpc",
            ]:
                if pkg_name not in existing_packages:
                    version = importlib_metadata.version(pkg_name)
                    env_config["dependencies"].append({"package": f"{pkg_name}=={version}"})

            env_manager = CondaLikeEnvManager(env_config)
            env_path = env_manager.ensure()
            env_name = f"fnnx-{env_manager.env_id}"

            return {"name": env_name, "path": env_path, "manager": env_manager}

        except Exception as e:
            logger.error(
                f"[CREATE_ENV] Failed to create model environment: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            raise RuntimeError(f"Failed to create conda environment: {e}") from e
