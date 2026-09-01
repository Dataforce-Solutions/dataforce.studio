import uuid

import pytest
from aiodocker.exceptions import DockerError

from agent.clients.docker_client import AGENT_HOST, DockerService


class TestSmokeAgentAlias:
    async def test_the_agent_alias_resolves_from_a_dynamically_created_container(self) -> None:
        try:
            service = DockerService()
        except Exception:
            pytest.skip("Docker is not available")

        async with service:
            try:
                await service.client.version()
            except Exception:
                pytest.skip("Docker daemon is not reachable")

            networks = {net.get("Name", "") for net in await service.client.networks.list()}
            if service.network_name not in networks:
                pytest.skip(f"Compose network '{service.network_name}' is not up")

            # The alias resolves only while the aliased container is attached and running,
            # so a half-down stack must skip rather than accuse the alias.
            alias_is_live = False
            for running in await service.client.containers.list():
                info = await running.show()
                attachments = info.get("NetworkSettings", {}).get("Networks", {})
                aliases = (attachments.get(service.network_name) or {}).get("Aliases") or []
                if AGENT_HOST in aliases:
                    alias_is_live = True
                    break
            if not alias_is_live:
                pytest.skip(
                    f"No running container carries the '{AGENT_HOST}' alias — "
                    "is the Compose stack up?"
                )

            image = "alpine:latest"
            try:
                await service.client.images.get(image)
            except DockerError:
                await service.client.images.pull(image)

            container = await service.client.containers.create(
                config={
                    "Image": image,
                    "Cmd": ["getent", "hosts", AGENT_HOST],
                    # the same attachment run_model_container uses — the point of the test
                    "HostConfig": {"NetworkMode": service.network_name},
                },
                name=f"sat-smoke-{uuid.uuid4().hex[:8]}",
            )
            try:
                await container.start()
                result = await container.wait()
                logs = await container.log(stdout=True, stderr=True)
            finally:
                await container.delete(force=True)

        output = "".join(logs) if isinstance(logs, list) else str(logs)
        assert result["StatusCode"] == 0, (
            f"'{AGENT_HOST}' does not resolve on '{service.network_name}'. "
            f"Is the 'satellite-agent' alias still declared in docker-compose? Output: {output!r}"
        )
