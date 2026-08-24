"""How the model container gets to its artifact.

The container is given no download link: a presigned URL expires in hours and the container
lives for weeks. It asks the Agent when it downloads, and skips even that when the model is
already in the shared cache.
"""

import sys
import tarfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

# model_server code imports via bare module names (e.g. `from clients...`) because
# conda_worker.py runs with model_server/ on sys.path.
_model_server_dir = str(Path(__file__).resolve().parent.parent / "model_server")
if _model_server_dir not in sys.path:
    sys.path.insert(0, _model_server_dir)

# fnnx builds conda environments and is a model-server runtime dependency, not a test one.
# Only its import is in the way of reaching the download logic.
_fnnx_conda = types.ModuleType("fnnx.envs.conda")
_fnnx_conda.CondaLikeEnvManager = object
_fnnx_conda.install_micromamba = lambda *args, **kwargs: None
sys.modules.setdefault("fnnx", types.ModuleType("fnnx"))
sys.modules.setdefault("fnnx.envs", types.ModuleType("fnnx.envs"))
sys.modules.setdefault("fnnx.envs.conda", _fnnx_conda)

from clients.agent_client import AgentClient, ArtifactResolutionError  # noqa: E402
from handlers.file_handler import ArtifactAccessExpired  # noqa: E402
from handlers.model_handler import ModelHandler  # noqa: E402

AGENT_URL = "http://satellite-agent:8000"
DEPLOYMENT_ID = "01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"
ARTIFACT_ID = "01a014fd-0000-7021-b0f5-fe92f2fdaf9b"
TOKEN = "a-token"
DOWNLOAD_URL = "https://s3.example.com/artifacts/iris.luml?X-Amz-Signature=fresh"


def _agent() -> AgentClient:
    return AgentClient(base_url=AGENT_URL, deployment_id=DEPLOYMENT_ID, token=TOKEN)


def _artifact_route(**kwargs) -> respx.Route:  # noqa: ANN003 — test helper
    return respx.get(f"{AGENT_URL}/satellites/deployments/{DEPLOYMENT_ID}/artifact").mock(**kwargs)


def _ok_response() -> httpx.Response:
    return httpx.Response(200, json={"url": DOWNLOAD_URL, "artifact_id": ARTIFACT_ID})


def _make_archive(tmp_path: Path) -> bytes:
    """A minimal .luml tarball, enough to unpack."""
    payload = tmp_path / "manifest.json"
    payload.write_text('{"name": "iris"}')
    archive = tmp_path / "model.tar"
    with tarfile.open(archive, "w") as tar:
        tar.add(payload, arcname="manifest.json")
    return archive.read_bytes()


def _handler(cache_dir: Path, agent: AgentClient | None = None) -> ModelHandler:
    """A ModelHandler stopped after extraction — building a conda env is not under test."""
    handler = ModelHandler.__new__(ModelHandler)
    handler._model_url = None
    handler._agent = agent or _agent()
    handler._models_cache_dir = cache_dir
    from handlers.file_handler import FileHandler

    handler._file_handler = FileHandler()
    return handler


@respx.mock
def test_the_url_is_asked_for_at_download_time(tmp_path: Path) -> None:
    route = _artifact_route(return_value=_ok_response())
    respx.get(DOWNLOAD_URL).mock(return_value=httpx.Response(200, content=_make_archive(tmp_path)))
    cache = tmp_path / "models"
    cache.mkdir()

    extracted = _handler(cache)._get_or_extract_model()

    assert route.called
    # keyed on the artifact, not on the URL whose signature changes every request
    assert Path(extracted) == cache / ARTIFACT_ID
    assert (Path(extracted) / "manifest.json").exists()


@respx.mock
def test_a_cached_model_never_touches_the_network(tmp_path: Path) -> None:
    """This is what lets a container come back up while the Agent or Platform is down."""
    route = _artifact_route(return_value=_ok_response())
    cache = tmp_path / "models"
    (cache / ARTIFACT_ID).mkdir(parents=True)
    (cache / ARTIFACT_ID / "manifest.json").write_text("{}")

    handler = _handler(cache)
    handler._agent = MagicMock(spec=AgentClient)
    handler._agent.fetch_artifact.return_value = type(
        "Ref", (), {"url": DOWNLOAD_URL, "artifact_id": ARTIFACT_ID}
    )()

    extracted = handler._get_or_extract_model()

    assert Path(extracted) == cache / ARTIFACT_ID
    assert not route.called


@respx.mock
def test_a_url_that_expires_mid_download_is_retried_once(tmp_path: Path) -> None:
    """A large artifact can outlive the link it started downloading from."""
    _artifact_route(return_value=_ok_response())
    respx.get(DOWNLOAD_URL).mock(
        side_effect=[
            httpx.Response(403),
            httpx.Response(200, content=_make_archive(tmp_path)),
        ]
    )
    cache = tmp_path / "models"
    cache.mkdir()

    extracted = _handler(cache)._get_or_extract_model()

    assert (Path(extracted) / "manifest.json").exists()


@respx.mock
def test_a_second_refusal_is_not_retried_forever(tmp_path: Path) -> None:
    _artifact_route(return_value=_ok_response())
    respx.get(DOWNLOAD_URL).mock(return_value=httpx.Response(403))
    cache = tmp_path / "models"
    cache.mkdir()

    with pytest.raises(ArtifactAccessExpired):
        _handler(cache)._get_or_extract_model()


@respx.mock
def test_a_caller_supplied_url_is_used_as_is(tmp_path: Path) -> None:
    """Local runs and tests pass a URL directly; there is no Agent to ask."""
    route = _artifact_route(return_value=_ok_response())
    respx.get(DOWNLOAD_URL).mock(return_value=httpx.Response(200, content=_make_archive(tmp_path)))
    cache = tmp_path / "models"
    cache.mkdir()

    handler = _handler(cache)
    handler._model_url = DOWNLOAD_URL

    extracted = handler._get_or_extract_model()

    assert not route.called
    assert (Path(extracted) / "manifest.json").exists()


@respx.mock
def test_an_unreachable_agent_says_so_plainly(tmp_path: Path) -> None:
    _artifact_route(side_effect=httpx.ConnectError("no route to host"))

    with pytest.raises(ArtifactResolutionError, match="unreachable"):
        _agent().fetch_artifact()


@respx.mock
def test_a_rejected_token_points_at_the_fix() -> None:
    _artifact_route(return_value=httpx.Response(403))

    with pytest.raises(ArtifactResolutionError, match="redeploy"):
        _agent().fetch_artifact()


def test_a_container_without_its_environment_fails_loudly() -> None:
    with patch.dict("os.environ", {}, clear=True):
        client = AgentClient()
        assert not client.configured
        with pytest.raises(ArtifactResolutionError, match="missing from the environment"):
            client.fetch_artifact()
