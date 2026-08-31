"""The conda environment a model container builds for its worker.

The worker (``conda_worker.py``) runs inside the model's environment and needs a few
packages of its own on top of the model's. Adding them must not make the model's own
pins unsatisfiable, and a build that fails must not leave a half-built environment for
the container's next start to trip over.
"""

import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

# model_server code imports via bare module names (e.g. `from clients...`) because
# conda_worker.py runs with model_server/ on sys.path.
_model_server_dir = str(Path(__file__).resolve().parent.parent.parent / "model_server")
if _model_server_dir not in sys.path:
    sys.path.insert(0, _model_server_dir)

# fnnx builds conda environments and is a model-server runtime dependency, not a test one.
_fnnx_conda = types.ModuleType("fnnx.envs.conda")
_fnnx_conda.CondaLikeEnvManager = object
_fnnx_conda.install_micromamba = lambda *args, **kwargs: None
sys.modules.setdefault("fnnx", types.ModuleType("fnnx"))
sys.modules.setdefault("fnnx.envs", types.ModuleType("fnnx.envs"))
sys.modules.setdefault("fnnx.envs.conda", _fnnx_conda)

from handlers.model_handler import WORKER_PACKAGES, ModelHandler  # noqa: E402

from handlers import model_handler as model_handler_module  # noqa: E402


def _deps(*specs: str) -> list[dict]:
    return [{"package": spec, "extra_pip_args": None, "condition": None} for spec in specs]


def _packages(extra: list[dict]) -> dict[str, str]:
    return {d["package"].split("==")[0]: d["package"].split("==")[1] for d in extra}


class FakeEnvManager:
    """Stands in for fnnx's CondaLikeEnvManager: the prefix exists, pip failed inside it."""

    _exe = "/usr/local/bin/micromamba"
    env_id = "deadbeef"

    def __init__(self, env_config: dict) -> None:
        self.env_config = env_config

    def ensure(self) -> str:
        raise RuntimeError("Command failed: pip install -r requirements.txt")


class TestModelEnvSetup:
    def test_worker_packages_follow_the_model_pin_of_the_opentelemetry_family(self) -> None:
        """A model that ships one part of OpenTelemetry pins the family for everyone.

        The image's own 1.43 parts next to the model's 1.42 part gave pip no solution;
        the family is released in lockstep, so the worker takes the model's version.
        """
        extra = ModelHandler._worker_dependencies(
            _deps("langgraph==1.2.4", "opentelemetry-exporter-otlp-proto-common==1.42.1")
        )

        packages = _packages(extra)
        assert packages["opentelemetry-api"] == "1.42.1"
        assert packages["opentelemetry-sdk"] == "1.42.1"
        assert packages["opentelemetry-exporter-otlp-proto-grpc"] == "1.42.1"
        assert "uvicorn" in packages  # the image's own version: the model said nothing

    def test_without_a_model_pin_the_image_versions_are_used(self) -> None:
        with patch.object(model_handler_module.importlib_metadata, "version", return_value="9.9.9"):
            extra = ModelHandler._worker_dependencies(_deps("scikit-learn==1.8.0"))

        assert _packages(extra) == dict.fromkeys(WORKER_PACKAGES, "9.9.9")

    def test_packages_the_model_already_ships_are_not_added_twice(self) -> None:
        """Name matching is by distribution, however the model spelled it."""
        extra = ModelHandler._worker_dependencies(
            _deps("Uvicorn==0.30.6", "opentelemetry_api==1.42.1 ; python_version >= '3.10'")
        )

        names = set(_packages(extra))
        assert "uvicorn" not in names
        assert "opentelemetry-api" not in names
        assert _packages(extra)["opentelemetry-sdk"] == "1.42.1"

    def test_a_family_pin_without_an_exact_version_does_not_pin_the_worker(self) -> None:
        """`>=` is a floor, not a version; only an exact pin can be followed."""
        with patch.object(
            model_handler_module.importlib_metadata, "version", return_value="1.43.0"
        ):
            extra = ModelHandler._worker_dependencies(_deps("opentelemetry-api>=1.30"))

        assert _packages(extra)["opentelemetry-sdk"] == "1.43.0"

    def test_a_failed_build_discards_the_half_built_environment(self) -> None:
        """Left behind, the prefix is 'reused' on the container's restart and the worker
        dies on the first missing package — hiding what really failed."""
        handler = ModelHandler.__new__(ModelHandler)
        handler._get_env = lambda: {  # type: ignore[method-assign]
            "python3::conda_pip": {"python_version": "3.12", "dependencies": _deps("numpy==2.0")}
        }
        removed: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            removed.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        with (
            patch.object(model_handler_module, "CondaLikeEnvManager", FakeEnvManager),
            patch.object(model_handler_module.importlib_metadata, "version", return_value="1.0"),
            patch.object(model_handler_module.subprocess, "run", fake_run),
        ):
            try:
                handler._create_model_env()
            except RuntimeError as error:
                assert "pip install" in str(error)  # the real failure, not a follow-on one
            else:
                raise AssertionError("a failed build must raise")

        assert removed == [
            ["/usr/local/bin/micromamba", "env", "remove", "-n", "fnnx-deadbeef", "-y"]
        ]
