"""Startup reconciliation of model containers that are no longer running.

The artifact URL a container carries is presigned and expires in hours, while the container
lives for weeks. A stopped container can therefore never simply be started again — it would
try to download its model from a dead link. These tests pin the recovery: recreate it, with
a URL signed at that moment.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import respx

from agent._exceptions import ContainerNotFoundError, ContainerNotRunningError
from agent.clients import ModelServerClient
from agent.handlers import artifact_tokens
from agent.handlers.container_launcher import LAUNCHER_PROTOCOL, LAUNCHER_PROTOCOL_LABEL
from agent.handlers.model_server_handler import RECOVERING_REASON, ModelServerHandler
from agent.settings import config

PLATFORM_URL = str(config.PLATFORM_URL).rstrip("/")

DEPLOYMENT_ID = "01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"
ARTIFACT_ID = "01a014fd-0000-7021-b0f5-fe92f2fdaf9b"


def _platform_record() -> dict:
    return {
        "id": DEPLOYMENT_ID,
        "orbit_id": str(uuid.uuid4()),
        "satellite_id": str(uuid.uuid4()),
        "satellite_name": "test-sat",
        "name": "iris",
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "iris_classification",
        "collection_id": str(uuid.uuid4()),
        "status": "active",
        "monitoring_mode": "full",
        "dynamic_attributes_secrets": {},
        "env_variables": {},
        "env_variables_secrets": {},
        "created_at": "2026-08-18T13:10:44Z",
    }


def _mock_platform(*, record: dict | None = None) -> None:
    record = record or _platform_record()
    respx.get(f"{PLATFORM_URL}/satellites/v1/deployments").mock(
        return_value=httpx.Response(200, json=[record])
    )
    respx.get(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=record)
    )


def _mock_model_server(*, healthy: bool = True) -> None:
    code = 200 if healthy else 503
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/healthz").mock(
        return_value=httpx.Response(code, json={"status": "healthy" if healthy else "down"})
    )
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/manifest").mock(
        return_value=httpx.Response(200, json={"name": "iris", "version": "1"})
    )
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/openapi\.json").mock(
        return_value=httpx.Response(200, json={"openapi": "3.0.0"})
    )
    respx.get(url__regex=rf"http://sat-{DEPLOYMENT_ID}:\d+/reference_profile").mock(
        return_value=httpx.Response(404)
    )


def _stopped_docker() -> AsyncMock:
    docker = AsyncMock()
    docker.check_container_running = AsyncMock(
        side_effect=ContainerNotRunningError(DEPLOYMENT_ID, "exited")
    )
    docker.__aenter__ = AsyncMock(return_value=docker)
    docker.__aexit__ = AsyncMock(return_value=False)
    return docker


def _running_docker(*, labels: dict[str, str] | None = None) -> AsyncMock:
    """A docker whose container runs — launched by the current protocol unless said otherwise."""
    docker = AsyncMock()
    docker.check_container_running = AsyncMock(
        return_value={LAUNCHER_PROTOCOL_LABEL: LAUNCHER_PROTOCOL} if labels is None else labels
    )
    docker.__aenter__ = AsyncMock(return_value=docker)
    docker.__aexit__ = AsyncMock(return_value=False)
    return docker


def _patched(docker: AsyncMock):  # noqa: ANN202 — test helper
    return patch("agent.handlers.model_server_handler.DockerService", return_value=docker)


class TestContainerRelaunch:
    @respx.mock
    async def test_a_stopped_container_is_recreated_with_a_token_not_a_url(self) -> None:
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_awaited_once()
        kwargs = docker.run_model_container.await_args.kwargs
        env = kwargs["env"]
        # the container carries no download link — that is the whole point; it asks for one
        assert "MODEL_ARTIFACT_URL" not in env
        assert env["MODEL_ARTIFACT_TOKEN"] == artifact_tokens.mint(DEPLOYMENT_ID)
        # pinned so a warm cache can be found without asking the Agent anything
        assert env["MODEL_ARTIFACT_ID"] == ARTIFACT_ID
        assert env["DEPLOYMENT_ID"] == DEPLOYMENT_ID
        assert env["MODEL_NAME"] == "iris_classification"
        assert kwargs["name"] == f"sat-{DEPLOYMENT_ID}"
        # the label matches the cache key the container will use, so undeploy cleans that entry
        assert kwargs["labels"]["df.model_id"] == ARTIFACT_ID
        # stamped with the current protocol, so no future reconciliation mistakes it for legacy
        assert kwargs["labels"][LAUNCHER_PROTOCOL_LABEL] == LAUNCHER_PROTOCOL
        # the cache volume is named after the artifact — the isolation boundary between models
        assert kwargs["model_id"] == ARTIFACT_ID

        # once it answers, the deployment is serving again and known locally
        assert DEPLOYMENT_ID in handler.deployments
        assert handler.deployments[DEPLOYMENT_ID].monitoring_enabled is True
        # recovering while it boots, active once it answers — and never `pending`, which
        # reconciliation skips: an Agent dying mid-recovery must not strand the deployment
        updates = [call.request.read() for call in patch_route.calls]
        assert b'"not_responding"' in updates[0]
        assert b'"active"' in updates[-1]
        assert all(b'"pending"' not in update for update in updates)

    @respx.mock
    async def test_a_container_that_cannot_be_recreated_is_reported_not_responding(self) -> None:
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )
        docker = _stopped_docker()
        docker.run_model_container = AsyncMock(side_effect=RuntimeError("no such image"))

        with _patched(docker):
            await handler.sync_deployments()

        assert DEPLOYMENT_ID not in handler.deployments
        final = json.loads(patch_route.calls[-1].request.read())
        assert final["status"] == "not_responding"
        # the marker survives the failure: replacement may already have deleted the old
        # container, and only marked records are allowed a container-less retry
        assert final["error_message"]["reason"] == RECOVERING_REASON

    async def test_a_replacement_that_lost_its_container_is_retried_by_the_next_start(
        self,
    ) -> None:
        """Replacement deletes before it creates, and the creation can fail.

        Without the persisted marker the next reconciliation would find no container and
        refuse to create one — by design, since resurrecting arbitrary container-less
        deployments revived 19 abandoned ones at once. The marker is recovery's own
        signature: recreating a record that carries it is a retry, not a resurrection.
        """
        # First pass: the old container is deleted, the new one never gets created.
        handler = ModelServerHandler()
        with respx.mock:
            _mock_platform()
            _mock_model_server()
            patch_route = respx.patch(
                f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
            ).mock(return_value=httpx.Response(200, json=_platform_record()))
            docker = _stopped_docker()
            docker.run_model_container = AsyncMock(side_effect=RuntimeError("pull failed"))
            with _patched(docker):
                await handler.sync_deployments()
            left_behind = json.loads(patch_route.calls[-1].request.read())

        # Second pass: a fresh Agent finds the record as the first one left it and no
        # container at all — exactly what the resurrection guard normally refuses.
        record = _platform_record() | {
            "status": left_behind["status"],
            "error_message": left_behind["error_message"],
        }
        fresh_handler = ModelServerHandler()
        with respx.mock:
            _mock_platform(record=record)
            _mock_model_server()
            patch_route = respx.patch(
                f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
            ).mock(return_value=httpx.Response(200, json=record))
            docker = AsyncMock()
            docker.check_container_running = AsyncMock(
                side_effect=ContainerNotFoundError(DEPLOYMENT_ID)
            )
            docker.__aenter__ = AsyncMock(return_value=docker)
            docker.__aexit__ = AsyncMock(return_value=False)
            with _patched(docker):
                await fresh_handler.sync_deployments()

            docker.run_model_container.assert_awaited_once()
            assert b'"active"' in patch_route.calls[-1].request.read()
        assert DEPLOYMENT_ID in fresh_handler.deployments

    @respx.mock
    async def test_a_recreated_container_that_never_answers_is_reported_not_responding(
        self,
    ) -> None:
        handler = ModelServerHandler()
        handler.recovery_health_check_timeout = 1  # one attempt, not thirty minutes
        _mock_platform()
        _mock_model_server(healthy=False)
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_awaited_once()
        assert DEPLOYMENT_ID not in handler.deployments
        assert b'"not_responding"' in patch_route.calls[-1].request.read()

    @respx.mock
    async def test_a_deployment_an_earlier_run_gave_up_on_is_still_recovered(self) -> None:
        """Otherwise the first failed reconciliation is permanent.

        Marking a deployment `not_responding` takes it out of `active`, so a reconciliation that
        only looked at `active` would never see it again — exactly the dead end this recovery
        exists to remove.
        """
        handler = ModelServerHandler()
        record = _platform_record() | {"status": "not_responding"}
        _mock_platform(record=record)
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=record)
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_awaited_once()
        assert DEPLOYMENT_ID in handler.deployments
        assert b'"active"' in patch_route.calls[-1].request.read()

    @respx.mock
    async def test_a_recovered_container_that_still_runs_is_promoted_back_to_active(self) -> None:
        handler = ModelServerHandler()
        record = _platform_record() | {"status": "not_responding"}
        _mock_platform(record=record)
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=record)
        )
        docker = _running_docker()

        with _patched(docker):
            await handler.sync_deployments()

        # it answers on its own, so it is promoted without touching the container
        docker.run_model_container.assert_not_awaited()
        assert b'"active"' in patch_route.calls[-1].request.read()

    async def test_a_recovery_the_agent_did_not_live_to_finish_is_settled_by_the_next_start(
        self,
    ) -> None:
        """The status recovery parks a deployment in must be one reconciliation looks at.

        Relaunching and seeing the container answer can be half an hour apart, and the Agent
        can die in between. All that survives it is the interim status on the Platform. Were
        that `pending` — which reconciliation skips as "a deploy task owns this" — the
        deployment would be stranded there forever, its container healthy and serving.
        """
        # First life: the stopped container is relaunched, then the Agent dies before it
        # answers — nothing after the interim status write is allowed to matter.
        handler = ModelServerHandler()
        handler.recovery_health_check_timeout = 1
        with respx.mock:
            _mock_platform()
            _mock_model_server(healthy=False)
            patch_route = respx.patch(
                f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
            ).mock(return_value=httpx.Response(200, json=_platform_record()))
            with _patched(_stopped_docker()):
                await handler.sync_deployments()
            interim_status = json.loads(patch_route.calls[0].request.read())["status"]

        # Second life: a fresh Agent finds the world as the first one left it — the record in
        # the interim status, the relaunched container running and by now healthy.
        record = _platform_record() | {"status": interim_status}
        fresh_handler = ModelServerHandler()
        with respx.mock:
            _mock_platform(record=record)
            _mock_model_server()
            patch_route = respx.patch(
                f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}"
            ).mock(return_value=httpx.Response(200, json=record))
            with _patched(_running_docker()):
                await fresh_handler.sync_deployments()

            assert patch_route.called, f"a deployment in '{interim_status}' was never looked at"
            assert b'"active"' in patch_route.calls[-1].request.read()
        assert DEPLOYMENT_ID in fresh_handler.deployments

    @respx.mock
    async def test_a_recovery_interrupted_mid_boot_is_waited_for_not_written_off(self) -> None:
        """The next Agent finishes the wait its predecessor began.

        The Agent died while its relaunched container was still booting. The next start finds
        the container running but not yet answering — and the record carrying the recovery
        marker. One failed health check must not condemn it: minutes later it will answer, and
        an Agent that wrote it off would neither serve it nor look again until the next restart.
        """
        handler = ModelServerHandler()
        record = _platform_record() | {
            "status": "not_responding",
            "error_message": {"reason": RECOVERING_REASON, "error": "container was relaunched"},
        }
        _mock_platform(record=record)
        _mock_model_server()  # healthy for the settling wait — it answers once waited for
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=record)
        )
        docker = _running_docker()

        # not yet healthy when reconciliation first looks (is_healthy retries internally for
        # minutes, so the "first look fails" moment is pinned directly)
        with (
            _patched(docker),
            patch.object(ModelServerClient, "is_healthy", AsyncMock(return_value=False)),
        ):
            await handler.sync_deployments()

        # the container itself was fine — nothing recreated, just waited for and promoted
        docker.run_model_container.assert_not_awaited()
        assert DEPLOYMENT_ID in handler.deployments
        final = json.loads(patch_route.calls[-1].request.read())
        assert final["status"] == "active"
        # the marker is cleared explicitly: the Platform honours only the fields sent,
        # so an omitted error_message would leave the recovery marker on an active record
        assert "error_message" in final and final["error_message"] is None

    @respx.mock
    async def test_a_deletion_requested_mid_recovery_wins_over_the_promotion(self) -> None:
        """The Platform speaks before the local registry, and may say no.

        Recovery can wait half an hour between relaunching a container and seeing it
        answer; a deletion requested during that wait makes the Platform refuse the
        stale promotion to active. The refusal must be final: no local registration —
        serving a deployment the user is deleting — no crash that would cancel the
        settling of every other recovered deployment, and no replacement container
        left behind: the undeploy task may already be past its own removal step, with
        recovery's replacement created just after it.
        """
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            side_effect=[
                httpx.Response(200, json=_platform_record()),  # the recovery marker lands
                httpx.Response(400, json={"detail": "Deployment is being deleted"}),
            ]
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()  # must not raise

        docker.run_model_container.assert_awaited_once()
        # promoted nowhere: not on the Platform, not locally — and the replacement is gone
        assert len(patch_route.calls) == 2
        assert DEPLOYMENT_ID not in handler.deployments
        docker.remove_model_container.assert_awaited_once_with(deployment_id=DEPLOYMENT_ID)

    @respx.mock
    async def test_a_deployment_deleted_mid_recovery_takes_its_orphan_container_with_it(
        self,
    ) -> None:
        """A 404 on the promotion means deletion won — and the container is nobody's.

        The undeploy task removed the old container and the record while recovery was
        waiting; the container recovery created is invisible to every record-driven
        path, so recovery itself must take it down.
        """
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            side_effect=[
                httpx.Response(200, json=_platform_record()),  # the recovery marker lands
                httpx.Response(404, json={"detail": "Deployment not found"}),
            ]
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        docker.remove_model_container.assert_awaited_once_with(deployment_id=DEPLOYMENT_ID)
        assert DEPLOYMENT_ID not in handler.deployments

    @respx.mock
    async def test_a_platform_blip_during_promotion_does_not_unserve_a_healthy_container(
        self,
    ) -> None:
        """Only a deliberate 4xx is a refusal; a 5xx says nothing about the deployment.

        Treating a network blip as "the Platform said no" left a healthy container
        unserved until the next Agent restart. The blip only delays the status flip:
        the container is registered and serves, and a later reconciliation retries.
        """
        handler = ModelServerHandler()
        record = _platform_record() | {"status": "not_responding"}
        _mock_platform(record=record)
        _mock_model_server()
        respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(502)
        )
        docker = _running_docker()

        with _patched(docker):
            await handler.sync_deployments()

        assert DEPLOYMENT_ID in handler.deployments
        docker.remove_model_container.assert_not_awaited()

    @respx.mock
    async def test_a_rate_limited_promotion_is_a_blip_not_a_refusal(self) -> None:
        """408 and 429 speak about the moment, not about the deployment."""
        handler = ModelServerHandler()
        record = _platform_record() | {"status": "not_responding"}
        _mock_platform(record=record)
        _mock_model_server()
        respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(429)
        )
        docker = _running_docker()

        with _patched(docker):
            await handler.sync_deployments()

        assert DEPLOYMENT_ID in handler.deployments
        docker.remove_model_container.assert_not_awaited()

    @respx.mock
    async def test_a_platform_blip_while_settling_does_not_unserve_the_recovered_container(
        self,
    ) -> None:
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            side_effect=[
                httpx.Response(200, json=_platform_record()),  # the recovery marker lands
                httpx.Response(502),  # the promotion hits a one-off Platform error
            ]
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_awaited_once()
        assert DEPLOYMENT_ID in handler.deployments
        docker.remove_model_container.assert_not_awaited()

    @respx.mock
    async def test_an_orphan_container_is_removed_on_the_next_start(self) -> None:
        """A container whose deployment no longer exists is invisible to reconciliation.

        Sync walks Platform records; a container left behind by a lost race with
        deletion has none, so only a container-side check can find it. The check runs
        against a listing fetched at that moment, not the opening snapshot — a
        deployment deleted mid-sync would hide behind the snapshot until the next
        restart. A container whose record appeared moments ago is spared: the fresh
        listing knows it.
        """
        orphan_id = str(uuid.uuid4())
        fresh_id = str(uuid.uuid4())
        deleted_mid_sync_id = str(uuid.uuid4())

        def _container(name: str, dep_id: str | None) -> AsyncMock:
            fake = AsyncMock()
            labels = {"df.deployment_id": dep_id} if dep_id else {}
            fake.show = AsyncMock(return_value={"Name": f"/{name}", "Config": {"Labels": labels}})
            return fake

        handler = ModelServerHandler()
        record = _platform_record()
        # in the opening snapshot, deleted before the orphan check ran ("failed" keeps
        # the serving loop away from it; what matters is that the fresh listing lacks it)
        deleted_record = _platform_record() | {"id": deleted_mid_sync_id, "status": "failed"}
        fresh_record = _platform_record() | {"id": fresh_id}
        respx.get(f"{PLATFORM_URL}/satellites/v1/deployments").mock(
            side_effect=[
                httpx.Response(200, json=[record, deleted_record]),  # the opening snapshot
                httpx.Response(200, json=[record, fresh_record]),  # the confirming look
            ]
        )
        _mock_model_server()
        respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=record)
        )
        docker = _running_docker()
        docker.client.containers.list = AsyncMock(
            return_value=[
                _container(f"sat-{orphan_id}", orphan_id),
                _container(f"sat-{deleted_mid_sync_id}", deleted_mid_sync_id),
                _container(f"sat-{fresh_id}", fresh_id),  # deploying right now — spared
                _container("df-studio-postgres", None),  # not ours — never touched
            ]
        )

        with _patched(docker):
            await handler.sync_deployments()

        removed = {
            call.kwargs["deployment_id"] for call in docker.remove_model_container.await_args_list
        }
        assert removed == {orphan_id, deleted_mid_sync_id}

    @respx.mock
    async def test_the_recovery_wait_is_bounded_by_wall_clock_not_attempts(self) -> None:
        """A hanging health endpoint spends seconds per attempt.

        Counting attempts would multiply the configured timeout by the seconds each
        hanging request takes — an "1800-second" wait quietly becoming hours. The wait
        is bounded by elapsed time, so a check that hangs simply gets fewer attempts.
        """
        handler = ModelServerHandler()
        record = _platform_record() | {"satellite_parameters": {"health_check_timeout": 2}}
        _mock_platform(record=record)
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=record)
        )
        docker = _stopped_docker()

        async def hanging_check(*args: object, **kwargs: object) -> bool:
            await asyncio.sleep(1.5)  # most of the 2-second budget, every attempt
            return False

        health = AsyncMock(side_effect=hanging_check)
        with _patched(docker), patch.object(ModelServerClient, "check_health_once", health):
            await handler.sync_deployments()

        # an attempt count of 2 would have allowed a second try past the deadline
        assert health.await_count == 1
        assert b'"not_responding"' in patch_route.calls[-1].request.read()

    @respx.mock
    async def test_a_wedged_container_without_the_recovery_marker_is_reported_at_once(self) -> None:
        """Only an interrupted recovery earns the wait; a plain broken container does not.

        A deployment that was serving and stopped answering carries no recovery marker, and
        stalling its bad news by a health-check timeout would help nobody.
        """
        handler = ModelServerHandler()
        _mock_platform()  # status "active", no recovery marker
        _mock_model_server(healthy=False)
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )
        docker = _running_docker()

        with (
            _patched(docker),
            patch.object(ModelServerClient, "is_healthy", AsyncMock(return_value=False)),
        ):
            await handler.sync_deployments()

        docker.run_model_container.assert_not_awaited()
        assert DEPLOYMENT_ID not in handler.deployments
        assert b'"not_responding"' in patch_route.calls[-1].request.read()

    @respx.mock
    async def test_a_deployment_without_a_container_is_not_resurrected(self) -> None:
        """Recovery restarts what this Satellite holds; it does not deploy from nothing.

        Creating a container for a deployment that has none would revive every deployment that
        ever failed on any Satellite — on the demo stand that was 19 abandoned ones at once.
        """
        handler = ModelServerHandler()
        _mock_platform(record=_platform_record() | {"status": "not_responding"})
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )

        docker = AsyncMock()
        docker.check_container_running = AsyncMock(
            side_effect=ContainerNotFoundError(DEPLOYMENT_ID)
        )
        docker.__aenter__ = AsyncMock(return_value=docker)
        docker.__aexit__ = AsyncMock(return_value=False)

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_not_awaited()
        assert b'"not_responding"' in patch_route.calls[-1].request.read()

    @respx.mock
    async def test_a_failed_deployment_is_not_touched(self) -> None:
        """A deploy that never worked needs a real redeploy, not a container restart."""
        handler = ModelServerHandler()
        _mock_platform(record=_platform_record() | {"status": "failed"})
        _mock_model_server()
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_not_awaited()
        assert handler.deployments == {}

    @respx.mock
    async def test_a_running_container_is_left_alone(self) -> None:
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )
        docker = _running_docker()

        with _patched(docker):
            await handler.sync_deployments()

        # recreating a healthy container would drop live traffic for no reason
        docker.run_model_container.assert_not_awaited()
        assert DEPLOYMENT_ID in handler.deployments
        # the only thing written back is where its dashboard lives — never a status
        assert all(b'"status"' not in call.request.read() for call in patch_route.calls)

    @respx.mock
    async def test_a_healthy_legacy_container_is_replaced_with_the_new_protocol(self) -> None:
        """A running container from an older Agent is one restart away from a dead URL.

        It was launched with a presigned MODEL_ARTIFACT_URL baked into its environment and a
        mount of the shared cache volume — and it serves fine until its first restart, which
        happens when nothing is watching. Reconciliation is the moment somebody is watching,
        so the replacement happens there, not later.
        """
        handler = ModelServerHandler()
        _mock_platform()
        _mock_model_server()
        patch_route = respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=_platform_record())
        )
        # a legacy container carries the old labels and no protocol stamp
        docker = _running_docker(labels={"df.model_id": ARTIFACT_ID})

        with _patched(docker):
            await handler.sync_deployments()

        docker.run_model_container.assert_awaited_once()
        env = docker.run_model_container.await_args.kwargs["env"]
        assert "MODEL_ARTIFACT_URL" not in env
        assert "MODEL_ARTIFACT_TOKEN" in env
        assert b'"active"' in patch_route.calls[-1].request.read()
        assert DEPLOYMENT_ID in handler.deployments

    @respx.mock
    async def test_deployment_env_cannot_override_the_runtime_contract(self) -> None:
        """User-supplied env_variables must never redefine token, identity or cache key.

        A deployment that could set MODEL_ARTIFACT_TOKEN or MODEL_ARTIFACT_ID in its own
        environment would be redefining the boundary that isolates it from the others.
        """
        handler = ModelServerHandler()
        record = _platform_record() | {
            "env_variables": {
                "MODEL_ARTIFACT_TOKEN": "forged",
                "MODEL_ARTIFACT_ID": "someone-elses-artifact",
                "DEPLOYMENT_ID": "someone-elses-deployment",
                "SOME_APP_SETTING": "kept",
            }
        }
        _mock_platform(record=record)
        _mock_model_server()
        respx.patch(f"{PLATFORM_URL}/satellites/v1/deployments/{DEPLOYMENT_ID}").mock(
            return_value=httpx.Response(200, json=record)
        )
        docker = _stopped_docker()

        with _patched(docker):
            await handler.sync_deployments()

        env = docker.run_model_container.await_args.kwargs["env"]
        assert env["MODEL_ARTIFACT_TOKEN"] == artifact_tokens.mint(DEPLOYMENT_ID)
        assert env["MODEL_ARTIFACT_ID"] == ARTIFACT_ID
        assert env["DEPLOYMENT_ID"] == DEPLOYMENT_ID
        # ordinary variables still pass through — only the contract is off limits
        assert env["SOME_APP_SETTING"] == "kept"

    async def test_model_containers_are_told_where_the_agent_is(self) -> None:
        """The callback address, built from the Agent's own host and port.

        It used to be assembled from the model server's port and a hostname with no network
        alias behind it, so it resolved to nothing. Nothing read the variable, so nothing broke
        — until something needed to call back. And it wins over a caller-supplied value: a
        container that could point it elsewhere would send its artifact token to that
        elsewhere.
        """
        from agent.clients.docker_client import AGENT_HOST, DockerService

        with patch("agent.clients.docker_client.aiodocker.Docker"):
            service = DockerService()
            service.client.containers.create_or_replace = AsyncMock()
            await service.run_model_container(
                image="img",
                name="sat-x",
                model_id=ARTIFACT_ID,
                env={"SATELLITE_AGENT_URL": "http://attacker:1"},
            )
            config_arg = service.client.containers.create_or_replace.await_args.kwargs["config"]

        env = dict(entry.split("=", 1) for entry in config_arg["Env"])
        assert env["SATELLITE_AGENT_URL"] == f"http://{AGENT_HOST}:{config.AGENT_PORT}"
        assert str(config.MODEL_SERVER_PORT) not in env["SATELLITE_AGENT_URL"]

    async def test_a_model_container_mounts_a_cache_private_to_its_artifact(self) -> None:
        """Deployments of one artifact share a volume; no container sees any other's cache.

        The volume name carries the artifact id — that, not anything inside the filesystem,
        is the isolation boundary between models running on the same Satellite. One shared
        volume let any model enumerate or poison every other model's cache.
        """
        from agent.clients.docker_client import MODEL_CACHE_MOUNT, DockerService, model_cache_volume

        with patch("agent.clients.docker_client.aiodocker.Docker"):
            service = DockerService()
            service.client.containers.create_or_replace = AsyncMock()
            await service.run_model_container(
                image="img", name="sat-x", model_id=ARTIFACT_ID, env={}
            )
            config_arg = service.client.containers.create_or_replace.await_args.kwargs["config"]

        assert config_arg["HostConfig"]["Binds"] == [
            f"{model_cache_volume(ARTIFACT_ID)}:{MODEL_CACHE_MOUNT}"
        ]
        # two artifacts, two volumes — never a path into someone else's cache
        assert model_cache_volume("a") != model_cache_volume("b")

    async def test_the_stale_cache_sweep_removes_orphans_and_spares_the_living(self) -> None:
        """Unreferenced cache volumes go entirely; live ones only lose abandoned staging.

        Docker refuses to delete a volume a container still references, so the deletion
        attempt itself is the in-use check. Inside the survivors only `.partial` staging
        directories old enough to have no live owner are swept — the sweep runs while
        relaunched containers may still be unpacking into fresh staging of their own.
        """
        from aiodocker.exceptions import DockerError

        from agent.clients.docker_client import (
            LEGACY_MODEL_CACHE_VOLUME,
            STALE_STAGING_MINUTES,
            DockerService,
            model_cache_volume,
        )

        orphan = model_cache_volume("abandoned-artifact")
        alive = model_cache_volume("serving-artifact")
        deployed = model_cache_volume("still-deployed-artifact")

        with patch("agent.clients.docker_client.aiodocker.Docker"):
            service = DockerService()
            service.client.volumes.list = AsyncMock(
                return_value={
                    "Volumes": [
                        {"Name": orphan},
                        {"Name": alive},
                        {"Name": deployed},
                        {"Name": LEGACY_MODEL_CACHE_VOLUME},
                        {"Name": "unrelated-volume"},
                    ]
                }
            )

            volumes: dict[str, AsyncMock] = {}

            def _get(name: str) -> AsyncMock:
                volume = AsyncMock()
                if name == alive:
                    volume.delete = AsyncMock(
                        side_effect=DockerError(409, {"message": "volume is in use"})
                    )
                volumes[name] = volume
                return volume

            service.client.volumes.get = AsyncMock(side_effect=_get)
            service.client.containers.create = AsyncMock()
            service.client.images.get = AsyncMock()

            await service.cleanup_stale_staging(keep_artifacts={"still-deployed-artifact"})

            config_arg = service.client.containers.create.await_args.kwargs["config"]

        # the orphaned and legacy volumes are gone; volumes that are not caches were not
        # touched, and the artifact a live record points at was never even attempted —
        # a redeploy caught in its delete-then-create gap must not lose its warm cache
        volumes[orphan].delete.assert_awaited_once()
        volumes[LEGACY_MODEL_CACHE_VOLUME].delete.assert_awaited_once()
        assert "unrelated-volume" not in volumes
        assert deployed not in volumes

        # the volume that refused deletion and the kept one are swept for stale staging,
        # and only for directories whose whole tree has gone quiet — the root's own mtime
        # freezes early in a live unpack, so the age test must look inside
        assert set(config_arg["HostConfig"]["Binds"]) == {
            f"{alive}:/sweep/{alive}",
            f"{deployed}:/sweep/{deployed}",
        }
        script = config_arg["Cmd"][2]
        assert config_arg["Cmd"][:2] == ["sh", "-c"]
        assert ".partial" in script
        assert f'find "$d" -mmin -{STALE_STAGING_MINUTES}' in script
        assert "rm -rf" in script
