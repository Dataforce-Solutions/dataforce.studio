"""What the Agent concludes from Docker's answer about a deployment's container."""

from unittest.mock import AsyncMock, patch

import pytest
from aiodocker.exceptions import DockerError

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.clients.docker_client import DockerService

DEPLOYMENT_ID = "01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"


def _service(get: AsyncMock) -> DockerService:
    service = DockerService.__new__(DockerService)
    service.client = AsyncMock()
    service.client.containers.get = get
    return service


def _container(status: str = "running") -> AsyncMock:
    container = AsyncMock()
    container.show = AsyncMock(
        return_value={"State": {"Status": status}, "Config": {"Labels": {"df.model_id": "m"}}}
    )
    return container


class TestContainerInspection:
    async def test_only_a_404_means_the_container_is_not_there(self) -> None:
        service = _service(
            AsyncMock(side_effect=DockerError(404, {"message": "No such container"}))
        )

        with pytest.raises(ContainerNotFoundError):
            await service.check_container_running(DEPLOYMENT_ID)

    async def test_a_daemon_error_is_retried_and_then_raised_as_itself(self) -> None:
        """A 5xx says nothing about the container.

        Callers act on "not found" — recreating a container, or giving up a wait — so a
        daemon hiccup must never be dressed up as one.
        """
        get = AsyncMock(side_effect=DockerError(500, {"message": "daemon is busy"}))
        service = _service(get)

        with (
            patch("agent.clients.docker_client.asyncio.sleep", new=AsyncMock()),
            pytest.raises(DockerError) as raised,
        ):
            await service.check_container_running(DEPLOYMENT_ID)

        assert raised.value.status == 500
        assert get.await_count == DockerService.INSPECT_ATTEMPTS

    async def test_a_passing_hiccup_is_absorbed(self) -> None:
        get = AsyncMock(side_effect=[DockerError(502, {"message": "bad gateway"}), _container()])
        service = _service(get)

        with patch("agent.clients.docker_client.asyncio.sleep", new=AsyncMock()):
            labels = await service.check_container_running(DEPLOYMENT_ID)

        assert labels == {"df.model_id": "m"}

    async def test_a_stopped_container_is_reported_as_such(self) -> None:
        service = _service(AsyncMock(return_value=_container(status="exited")))

        with pytest.raises(ContainerNotRunningError):
            await service.check_container_running(DEPLOYMENT_ID)

    async def test_a_container_removed_between_lookup_and_read_is_not_there(self) -> None:
        container = AsyncMock()
        container.show = AsyncMock(side_effect=DockerError(404, {"message": "No such container"}))
        service = _service(AsyncMock(return_value=container))

        with pytest.raises(ContainerNotFoundError):
            await service.check_container_running(DEPLOYMENT_ID)

    async def test_a_hiccup_on_the_status_read_is_retried_too(self) -> None:
        flaky = AsyncMock()
        flaky.show = AsyncMock(
            side_effect=[
                DockerError(500, {"message": "daemon is busy"}),
                {"State": {"Status": "running"}, "Config": {"Labels": {"df.model_id": "m"}}},
            ]
        )
        service = _service(AsyncMock(return_value=flaky))

        with patch("agent.clients.docker_client.asyncio.sleep", new=AsyncMock()):
            labels = await service.check_container_running(DEPLOYMENT_ID)

        assert labels == {"df.model_id": "m"}
        assert flaky.show.await_count == 2
