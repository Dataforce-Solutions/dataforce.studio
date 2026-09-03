from collections.abc import AsyncIterator, Awaitable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from luml.handlers.lineage import LineageHandler
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactNotFoundError,
    InsufficientPermissionsError,
    NotFoundError,
    OrbitNotFoundError,
)
from luml.models.lineage import LineageEdgeOrm, LineageNodeOrm
from luml.repositories.lineage import LineageRepository
from luml.schemas.artifacts import (
    ArtifactListed,
    ArtifactStatus,
    ArtifactType,
    LumlArtifactManifest,
)
from luml.schemas.lineage import (
    LineageBatchIn,
    LineageNodeRef,
    LineagePair,
    LineagePosition,
    LineageVia,
)
from luml.schemas.permissions import Action, Resource
from sqlalchemy.ext.asyncio import AsyncSession

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
COLLECTION_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")
EXPERIMENT_COLLECTION_ID = UUID("0199c337-09f5-7815-a7bd-403c946747f1")
MODEL_COLLECTION_ID = UUID("0199c337-09f6-766a-bbd5-c457d65e2050")
ARTIFACT_A_ID = UUID("0199c337-09fa-7ff6-b1e7-fc89a65f8622")
ARTIFACT_B_ID = UUID("0199c337-09fb-72eb-a8c8-77e55d873463")
ARTIFACT_C_ID = UUID("0199c337-09fc-75de-8581-9fd795cb8ebf")
NODE_A_ID = UUID("0199c337-0a01-7d9f-9cd8-ee95ab3c4bd1")
NODE_B_ID = UUID("0199c337-0a02-7c1e-8a3b-3f0e1a6d95c4")
NODE_C_ID = UUID("0199c337-0a03-7f5a-bb17-2c9d4e8a1b63")
MISSING_ID = UUID("0199c337-0a04-7755-b82e-8f38a1128ca1")
EDGE_ID = UUID("0199c337-0a05-7cb3-8d16-c40ab75581b9")
NEW_EDGE_A_ID = UUID("0199c337-0a06-7123-9ceb-2251e583cb88")
NEW_EDGE_B_ID = UUID("0199c337-0a07-7fef-962d-435a52af014e")
CREATED_AT = datetime(2026, 9, 3, tzinfo=UTC)

handler = LineageHandler()


def _artifact(
    artifact_id: UUID,
    name: str,
    *,
    artifact_type: ArtifactType = ArtifactType.MODEL,
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
    collection_id: UUID = COLLECTION_ID,
    collection_name: str = "Models",
) -> ArtifactListed:
    return ArtifactListed.model_validate(
        {
            "id": artifact_id,
            "collection_id": collection_id,
            "collection": {"name": collection_name},
            "file_name": f"{name}.luml",
            "name": name,
            "description": None,
            "extra_values": {},
            "manifest": LumlArtifactManifest(
                artifact_type=artifact_type.value,
                variant="default",
                producer_name="tests",
                producer_version="1",
                producer_tags=[],
                payload={},
            ),
            "file_hash": f"hash-{name}",
            "file_index": {},
            "bucket_location": f"artifacts/{name}",
            "size": 1,
            "unique_identifier": f"uid-{name}",
            "tags": [],
            "status": status,
            "created_by_user": "Lineage User",
            "created_at": CREATED_AT,
            "updated_at": None,
            "type": artifact_type,
            "deployments": [],
        }
    )


def _node(
    node_id: UUID,
    artifact_id: UUID | None,
    name: str,
    *,
    artifact_type: str = "model",
    collection_name: str | None = "Models",
    x: float | None = None,
    y: float | None = None,
) -> LineageNodeOrm:
    return LineageNodeOrm(
        id=node_id,
        orbit_id=ORBIT_ID,
        artifact_id=artifact_id,
        name=name,
        type=artifact_type,
        collection_name=collection_name,
        x=x,
        y=y,
        created_at=CREATED_AT,
    )


def _edge(
    edge_id: UUID,
    source: UUID,
    target: UUID,
    *,
    via: LineageVia = LineageVia.API,
) -> LineageEdgeOrm:
    return LineageEdgeOrm(
        id=edge_id,
        orbit_id=ORBIT_ID,
        source_node_id=source,
        target_node_id=target,
        created_by_user="Lineage User",
        created_via=via.value,
        created_at=CREATED_AT,
    )


@dataclass
class HandlerMocks:
    session: AsyncSession
    transaction_errors: list[BaseException]
    check_permissions: AsyncMock
    get_orbit: AsyncMock
    get_user: AsyncMock
    get_artifacts: AsyncMock
    get_edges_by_ids: AsyncMock
    delete_edges: AsyncMock
    get_nodes_by_ids: AsyncMock
    get_or_create_node: AsyncMock
    get_edges_by_pairs: AsyncMock
    create_edges: AsyncMock
    get_nodes_by_artifact_ids: AsyncMock
    update_positions: AsyncMock
    delete_edgeless_nodes: AsyncMock
    get_node_by_artifact_id: AsyncMock
    traverse: AsyncMock


@pytest.fixture
def lineage_mocks() -> Iterator[HandlerMocks]:
    session = cast(AsyncSession, Mock(spec=AsyncSession))
    transaction_errors: list[BaseException] = []

    @asynccontextmanager
    async def transaction(
        repository: LineageRepository,
    ) -> AsyncIterator[AsyncSession]:
        try:
            yield session
        except BaseException as error:
            transaction_errors.append(error)
            raise

    with (
        patch(
            "luml.handlers.lineage.PermissionsHandler.check_permissions",
            new_callable=AsyncMock,
        ) as check_permissions,
        patch(
            "luml.handlers.lineage.OrbitRepository.get_orbit_simple",
            new_callable=AsyncMock,
        ) as get_orbit,
        patch(
            "luml.handlers.lineage.UserRepository.get_public_user_by_id",
            new_callable=AsyncMock,
        ) as get_user,
        patch(
            "luml.handlers.lineage.ArtifactRepository.get_artifacts_by_ids_in_orbit",
            new_callable=AsyncMock,
        ) as get_artifacts,
        patch(
            "luml.handlers.lineage.LineageRepository.get_edges_by_ids",
            new_callable=AsyncMock,
        ) as get_edges_by_ids,
        patch(
            "luml.handlers.lineage.LineageRepository.delete_edges",
            new_callable=AsyncMock,
        ) as delete_edges,
        patch(
            "luml.handlers.lineage.LineageRepository.get_nodes_by_ids",
            new_callable=AsyncMock,
        ) as get_nodes_by_ids,
        patch(
            "luml.handlers.lineage.LineageRepository.get_or_create_node",
            new_callable=AsyncMock,
        ) as get_or_create_node,
        patch(
            "luml.handlers.lineage.LineageRepository.get_edges_by_pairs",
            new_callable=AsyncMock,
        ) as get_edges_by_pairs,
        patch(
            "luml.handlers.lineage.LineageRepository.create_edges",
            new_callable=AsyncMock,
        ) as create_edges,
        patch(
            "luml.handlers.lineage.LineageRepository.get_nodes_by_artifact_ids",
            new_callable=AsyncMock,
        ) as get_nodes_by_artifact_ids,
        patch(
            "luml.handlers.lineage.LineageRepository.update_positions",
            new_callable=AsyncMock,
        ) as update_positions,
        patch(
            "luml.handlers.lineage.LineageRepository.delete_edgeless_nodes",
            new_callable=AsyncMock,
        ) as delete_edgeless_nodes,
        patch(
            "luml.handlers.lineage.LineageRepository.get_node_by_artifact_id",
            new_callable=AsyncMock,
        ) as get_node_by_artifact_id,
        patch(
            "luml.handlers.lineage.LineageRepository.traverse",
            new_callable=AsyncMock,
        ) as traverse,
        patch("luml.handlers.lineage.LineageRepository.transaction", new=transaction),
    ):
        get_orbit.return_value = Mock()
        get_user.return_value = Mock(
            full_name="Lineage User", email="lineage@example.com"
        )
        get_artifacts.return_value = []
        get_edges_by_ids.return_value = []
        get_nodes_by_ids.return_value = []
        get_edges_by_pairs.return_value = []
        create_edges.return_value = []
        get_nodes_by_artifact_ids.return_value = []
        get_node_by_artifact_id.return_value = None
        traverse.return_value = ([], [], False)
        yield HandlerMocks(
            session=session,
            transaction_errors=transaction_errors,
            check_permissions=check_permissions,
            get_orbit=get_orbit,
            get_user=get_user,
            get_artifacts=get_artifacts,
            get_edges_by_ids=get_edges_by_ids,
            delete_edges=delete_edges,
            get_nodes_by_ids=get_nodes_by_ids,
            get_or_create_node=get_or_create_node,
            get_edges_by_pairs=get_edges_by_pairs,
            create_edges=create_edges,
            get_nodes_by_artifact_ids=get_nodes_by_artifact_ids,
            update_positions=update_positions,
            delete_edgeless_nodes=delete_edgeless_nodes,
            get_node_by_artifact_id=get_node_by_artifact_id,
            traverse=traverse,
        )


def _creation_changes(
    source_artifact_id: UUID = ARTIFACT_A_ID,
    target_artifact_id: UUID = ARTIFACT_B_ID,
) -> LineageBatchIn:
    return LineageBatchIn(
        create=[
            LineagePair(
                source=LineageNodeRef(artifact_id=source_artifact_id),
                target=LineageNodeRef(artifact_id=target_artifact_id),
            )
        ]
    )


def _configure_artifact_pair(
    mocks: HandlerMocks,
) -> tuple[LineageNodeOrm, LineageNodeOrm]:
    artifact_a = _artifact(ARTIFACT_A_ID, "A")
    artifact_b = _artifact(ARTIFACT_B_ID, "B", status=ArtifactStatus.PENDING_UPLOAD)
    node_a = _node(NODE_A_ID, ARTIFACT_A_ID, "A")
    node_b = _node(NODE_B_ID, ARTIFACT_B_ID, "B")
    mocks.get_artifacts.return_value = [artifact_a, artifact_b]
    mocks.get_or_create_node.side_effect = [node_a, node_b]
    return node_a, node_b


@pytest.mark.asyncio
async def test_create_links_builds_a_chain_across_collections(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    dataset = _artifact(
        ARTIFACT_A_ID,
        "Dataset",
        artifact_type=ArtifactType.DATASET,
        collection_name="Datasets",
    )
    experiment = _artifact(
        ARTIFACT_B_ID,
        "Experiment",
        artifact_type=ArtifactType.EXPERIMENT,
        status=ArtifactStatus.PENDING_UPLOAD,
        collection_id=EXPERIMENT_COLLECTION_ID,
        collection_name="Experiments",
    )
    model = _artifact(
        ARTIFACT_C_ID,
        "Model",
        collection_id=MODEL_COLLECTION_ID,
        collection_name="Models",
    )
    dataset_node = _node(
        NODE_A_ID,
        ARTIFACT_A_ID,
        "Dataset",
        artifact_type="dataset",
        collection_name="Datasets",
    )
    experiment_node = _node(
        NODE_B_ID,
        ARTIFACT_B_ID,
        "Experiment",
        artifact_type="experiment",
        collection_name="Experiments",
    )
    model_node = _node(NODE_C_ID, ARTIFACT_C_ID, "Model")
    dataset_edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID)
    experiment_edge = _edge(NEW_EDGE_B_ID, NODE_B_ID, NODE_C_ID)
    mocks.get_artifacts.side_effect = [
        [dataset, experiment],
        [experiment, model],
        [model],
        [model, experiment, dataset],
    ]
    mocks.get_or_create_node.side_effect = [
        dataset_node,
        experiment_node,
        experiment_node,
        model_node,
    ]
    mocks.create_edges.side_effect = [[dataset_edge], [experiment_edge]]

    first = await handler.create_links(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        ARTIFACT_A_ID,
        [ARTIFACT_B_ID],
        LineageVia.API,
    )
    second = await handler.create_links(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        ARTIFACT_B_ID,
        [ARTIFACT_C_ID],
        LineageVia.API,
    )

    mocks.get_node_by_artifact_id.return_value = model_node
    mocks.traverse.return_value = (
        [model_node, experiment_node, dataset_node],
        [dataset_edge, experiment_edge],
        False,
    )
    graph = await handler.get_graph(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_C_ID, 2
    )

    assert first == [dataset_edge.to_edge()]
    assert second == [experiment_edge.to_edge()]
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert {node.collection_name for node in graph.nodes} == {
        "Datasets",
        "Experiments",
        "Models",
    }
    assert all(edge.created_by_user == "Lineage User" for edge in graph.edges)
    assert all(edge.created_via == LineageVia.API for edge in graph.edges)
    assert mocks.create_edges.await_args_list[0].args[1] == [(NODE_A_ID, NODE_B_ID)]
    assert mocks.create_edges.await_args_list[1].args[1] == [(NODE_B_ID, NODE_C_ID)]


@pytest.mark.asyncio
async def test_create_links_collapses_duplicate_targets(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    artifacts = [
        _artifact(ARTIFACT_A_ID, "A"),
        _artifact(
            ARTIFACT_B_ID,
            "B",
            status=ArtifactStatus.PENDING_UPLOAD,
        ),
        _artifact(ARTIFACT_C_ID, "C"),
    ]
    nodes = [
        _node(NODE_A_ID, ARTIFACT_A_ID, "A"),
        _node(NODE_B_ID, ARTIFACT_B_ID, "B"),
        _node(NODE_C_ID, ARTIFACT_C_ID, "C"),
    ]
    created = [
        _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID),
        _edge(NEW_EDGE_B_ID, NODE_A_ID, NODE_C_ID),
    ]
    mocks.get_artifacts.return_value = artifacts
    mocks.get_or_create_node.side_effect = nodes
    mocks.create_edges.return_value = created

    result = await handler.create_links(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        ARTIFACT_A_ID,
        [ARTIFACT_B_ID, ARTIFACT_C_ID, ARTIFACT_B_ID],
        LineageVia.API,
    )

    assert result == [edge.to_edge() for edge in created]
    mocks.create_edges.assert_awaited_once_with(
        ORBIT_ID,
        [(NODE_A_ID, NODE_B_ID), (NODE_A_ID, NODE_C_ID)],
        "Lineage User",
        LineageVia.API,
        mocks.session,
    )


@pytest.mark.asyncio
async def test_create_links_can_use_access_checked_by_artifact_creation(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    node_a, node_b = _configure_artifact_pair(mocks)
    edge = _edge(NEW_EDGE_A_ID, node_a.id, node_b.id)
    mocks.create_edges.return_value = [edge]

    result = await handler.create_links(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        ARTIFACT_A_ID,
        [ARTIFACT_B_ID],
        LineageVia.API,
        check_access=False,
    )

    assert result == [edge.to_edge()]
    mocks.check_permissions.assert_not_awaited()
    mocks.get_orbit.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_changes_orders_operations_and_collapses_duplicate_pairs(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    artifact_a = _artifact(ARTIFACT_A_ID, "A")
    artifact_b = _artifact(ARTIFACT_B_ID, "B", status=ArtifactStatus.PENDING_UPLOAD)
    artifact_c = _artifact(ARTIFACT_C_ID, "C")
    node_a = _node(NODE_A_ID, ARTIFACT_A_ID, "A")
    node_b = _node(NODE_B_ID, ARTIFACT_B_ID, "B")
    node_c = _node(NODE_C_ID, ARTIFACT_C_ID, "C")
    deleted_edge = _edge(EDGE_ID, NODE_B_ID, NODE_C_ID)
    created_edges = [
        _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID),
        _edge(NEW_EDGE_B_ID, NODE_B_ID, NODE_C_ID),
    ]

    mocks.get_artifacts.return_value = [artifact_a, artifact_b, artifact_c]
    mocks.get_edges_by_ids.return_value = [deleted_edge]
    mocks.get_nodes_by_ids.side_effect = [[], [node_a]]
    mocks.get_or_create_node.side_effect = [node_a, node_b, node_c]
    mocks.create_edges.return_value = created_edges
    mocks.get_nodes_by_artifact_ids.return_value = [node_c]

    operation_order = Mock()
    operation_order.attach_mock(mocks.delete_edges, "delete")
    operation_order.attach_mock(mocks.create_edges, "create")
    operation_order.attach_mock(mocks.update_positions, "position")
    operation_order.attach_mock(mocks.delete_edgeless_nodes, "cleanup")

    pair_a_b = LineagePair(
        source=LineageNodeRef(artifact_id=ARTIFACT_A_ID),
        target=LineageNodeRef(artifact_id=ARTIFACT_B_ID),
    )
    changes = LineageBatchIn(
        delete=[EDGE_ID],
        create=[
            pair_a_b,
            pair_a_b,
            LineagePair(
                source=LineageNodeRef(artifact_id=ARTIFACT_B_ID),
                target=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
            ),
        ],
        positions=[
            LineagePosition(ref=LineageNodeRef(node_id=NODE_A_ID), x=10.0, y=20.0),
            LineagePosition(
                ref=LineageNodeRef(artifact_id=ARTIFACT_C_ID), x=30.0, y=40.0
            ),
            LineagePosition(ref=LineageNodeRef(node_id=MISSING_ID), x=50.0, y=60.0),
        ],
    )

    result = await handler.apply_changes(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        changes,
        LineageVia.API,
    )

    assert [edge.id for edge in result.deleted] == [EDGE_ID]
    assert [edge.id for edge in result.created] == [NEW_EDGE_A_ID, NEW_EDGE_B_ID]
    mocks.create_edges.assert_awaited_once_with(
        ORBIT_ID,
        [(NODE_A_ID, NODE_B_ID), (NODE_B_ID, NODE_C_ID)],
        "Lineage User",
        LineageVia.API,
        mocks.session,
    )
    mocks.update_positions.assert_awaited_once_with(
        ORBIT_ID,
        {NODE_A_ID: (10.0, 20.0), NODE_C_ID: (30.0, 40.0)},
        mocks.session,
    )
    assert [item[0] for item in operation_order.mock_calls] == [
        "delete",
        "create",
        "position",
        "cleanup",
    ]
    mocks.check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID,
        USER_ID,
        Resource.ARTIFACT,
        Action.UPDATE,
        ORBIT_ID,
    )


@pytest.mark.asyncio
async def test_apply_changes_replaces_a_node_and_keeps_its_position(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    replacement = _artifact(ARTIFACT_C_ID, "B prime")
    source_node = _node(NODE_A_ID, ARTIFACT_A_ID, "A")
    replacement_node = _node(NODE_C_ID, ARTIFACT_C_ID, "B prime")
    deleted_edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
    created_edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_C_ID)
    mocks.get_edges_by_ids.return_value = [deleted_edge]
    mocks.get_artifacts.return_value = [replacement]
    mocks.get_nodes_by_ids.side_effect = [[source_node], []]
    mocks.get_or_create_node.return_value = replacement_node
    mocks.create_edges.return_value = [created_edge]
    mocks.get_nodes_by_artifact_ids.return_value = [replacement_node]
    changes = LineageBatchIn(
        delete=[EDGE_ID],
        create=[
            LineagePair(
                source=LineageNodeRef(node_id=NODE_A_ID),
                target=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
            )
        ],
        positions=[
            LineagePosition(
                ref=LineageNodeRef(artifact_id=ARTIFACT_C_ID),
                x=300.0,
                y=100.0,
            )
        ],
    )

    result = await handler.apply_changes(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        changes,
        LineageVia.UI,
    )

    assert result.deleted == [deleted_edge.to_edge()]
    assert result.created == [created_edge.to_edge()]
    mocks.update_positions.assert_awaited_once_with(
        ORBIT_ID,
        {NODE_C_ID: (300.0, 100.0)},
        mocks.session,
    )
    mocks.delete_edgeless_nodes.assert_awaited_once_with(ORBIT_ID, mocks.session)


@pytest.mark.asyncio
async def test_apply_changes_rejects_a_loop_and_rolls_back(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    artifact = _artifact(ARTIFACT_A_ID, "A")
    node = _node(NODE_A_ID, ARTIFACT_A_ID, "A")
    existing = _edge(EDGE_ID, NODE_B_ID, NODE_C_ID)
    mocks.get_edges_by_ids.return_value = [existing]
    mocks.get_artifacts.return_value = [artifact]
    mocks.get_or_create_node.return_value = node
    changes = LineageBatchIn(
        delete=[EDGE_ID],
        create=[
            LineagePair(
                source=LineageNodeRef(artifact_id=ARTIFACT_A_ID),
                target=LineageNodeRef(artifact_id=ARTIFACT_A_ID),
            )
        ],
    )

    with pytest.raises(
        ApplicationError, match="Artifact cannot be linked to itself"
    ) as error:
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            LineageVia.API,
        )

    assert error.value.status_code == 400
    assert mocks.transaction_errors == [error.value]
    mocks.delete_edges.assert_awaited_once()
    mocks.create_edges.assert_not_awaited()
    mocks.delete_edgeless_nodes.assert_not_awaited()


@pytest.mark.parametrize(
    ("existing_source", "existing_target", "message"),
    [
        (NODE_A_ID, NODE_B_ID, "Lineage connection already exists"),
        (NODE_B_ID, NODE_A_ID, "Reverse lineage connection already exists"),
    ],
)
@pytest.mark.asyncio
async def test_apply_changes_rejects_existing_pair_in_either_direction(
    lineage_mocks: HandlerMocks,
    existing_source: UUID,
    existing_target: UUID,
    message: str,
) -> None:
    mocks = lineage_mocks
    _configure_artifact_pair(mocks)
    mocks.get_edges_by_pairs.return_value = [
        _edge(EDGE_ID, existing_source, existing_target)
    ]

    with pytest.raises(ApplicationError, match=message) as error:
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            _creation_changes(),
            LineageVia.UI,
        )

    assert error.value.status_code == 409
    mocks.create_edges.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_changes_rejects_reverse_pairs_in_the_same_batch(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    _configure_artifact_pair(mocks)
    changes = LineageBatchIn(
        create=[
            *_creation_changes().create,
            LineagePair(
                source=LineageNodeRef(artifact_id=ARTIFACT_B_ID),
                target=LineageNodeRef(artifact_id=ARTIFACT_A_ID),
            ),
        ]
    )

    with pytest.raises(
        ApplicationError, match="Reverse lineage connection already exists"
    ) as error:
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            LineageVia.API,
        )

    assert error.value.status_code == 409
    mocks.get_edges_by_pairs.assert_not_awaited()
    mocks.create_edges.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_changes_rejects_artifact_outside_the_orbit(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    mocks.get_artifacts.return_value = [_artifact(ARTIFACT_A_ID, "A")]

    with pytest.raises(ArtifactNotFoundError, match="Artifact not found"):
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            _creation_changes(),
            LineageVia.API,
        )

    mocks.get_or_create_node.assert_not_awaited()
    mocks.create_edges.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_changes_rejects_node_outside_the_orbit(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    mocks.get_artifacts.return_value = [_artifact(ARTIFACT_A_ID, "A")]
    changes = LineageBatchIn(
        create=[
            LineagePair(
                source=LineageNodeRef(artifact_id=ARTIFACT_A_ID),
                target=LineageNodeRef(node_id=NODE_B_ID),
            )
        ]
    )

    with pytest.raises(NotFoundError, match="Lineage node not found"):
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            changes,
            LineageVia.API,
        )

    mocks.get_nodes_by_ids.assert_awaited_once_with(
        ORBIT_ID, [NODE_B_ID], mocks.session
    )
    mocks.get_or_create_node.assert_not_awaited()
    mocks.create_edges.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_changes_can_connect_to_a_deleted_artifact_node(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    artifact = _artifact(ARTIFACT_A_ID, "A")
    live_node = _node(NODE_A_ID, ARTIFACT_A_ID, "A")
    deleted_node = _node(NODE_B_ID, None, "Deleted source")
    edge = _edge(NEW_EDGE_A_ID, NODE_A_ID, NODE_B_ID)
    mocks.get_artifacts.return_value = [artifact]
    mocks.get_nodes_by_ids.return_value = [deleted_node]
    mocks.get_or_create_node.return_value = live_node
    mocks.create_edges.return_value = [edge]
    changes = LineageBatchIn(
        create=[
            LineagePair(
                source=LineageNodeRef(artifact_id=ARTIFACT_A_ID),
                target=LineageNodeRef(node_id=NODE_B_ID),
            )
        ]
    )

    result = await handler.apply_changes(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        changes,
        LineageVia.API,
    )

    assert result.created == [edge.to_edge()]


@pytest.mark.asyncio
async def test_apply_changes_rejects_an_edge_outside_the_orbit(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks

    with pytest.raises(NotFoundError, match="Lineage connection not found"):
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LineageBatchIn(delete=[EDGE_ID]),
            LineageVia.API,
        )

    mocks.delete_edges.assert_not_awaited()
    mocks.delete_edgeless_nodes.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_changes_empty_batch_returns_empty_result(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks

    result = await handler.apply_changes(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        LineageBatchIn(),
        LineageVia.UI,
    )

    assert result.created == []
    assert result.deleted == []
    mocks.get_user.assert_not_awaited()
    mocks.get_artifacts.assert_not_awaited()
    mocks.delete_edgeless_nodes.assert_awaited_once_with(ORBIT_ID, mocks.session)


@pytest.mark.parametrize(
    ("artifact_id", "node_id", "name"),
    [
        (ARTIFACT_A_ID, NODE_A_ID, "A"),
        (ARTIFACT_B_ID, NODE_B_ID, "B"),
    ],
)
@pytest.mark.asyncio
async def test_delete_link_accepts_either_edge_end(
    lineage_mocks: HandlerMocks,
    artifact_id: UUID,
    node_id: UUID,
    name: str,
) -> None:
    mocks = lineage_mocks
    artifact = _artifact(artifact_id, name)
    node = _node(node_id, artifact_id, name)
    edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
    mocks.get_artifacts.return_value = [artifact]
    mocks.get_node_by_artifact_id.return_value = node
    mocks.get_edges_by_ids.side_effect = [[edge], [edge]]

    result = await handler.delete_link(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        artifact_id,
        EDGE_ID,
    )

    assert result == edge.to_edge()
    mocks.delete_edges.assert_awaited_once_with(ORBIT_ID, [EDGE_ID], mocks.session)
    mocks.check_permissions.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_link_rejects_an_artifact_outside_the_orbit(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks

    with pytest.raises(ArtifactNotFoundError, match="Artifact not found"):
        await handler.delete_link(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_A_ID,
            EDGE_ID,
        )

    mocks.get_node_by_artifact_id.assert_not_awaited()
    mocks.delete_edges.assert_not_awaited()


@pytest.mark.parametrize("edge_in_orbit", [True, False])
@pytest.mark.asyncio
async def test_delete_link_rejects_a_foreign_or_non_owned_edge(
    lineage_mocks: HandlerMocks,
    edge_in_orbit: bool,
) -> None:
    mocks = lineage_mocks
    artifact_c = _artifact(ARTIFACT_C_ID, "C")
    node_c = _node(NODE_C_ID, ARTIFACT_C_ID, "C")
    edge = _edge(EDGE_ID, NODE_A_ID, NODE_B_ID)
    mocks.get_artifacts.return_value = [artifact_c]
    mocks.get_node_by_artifact_id.return_value = node_c
    mocks.get_edges_by_ids.return_value = [edge] if edge_in_orbit else []

    with pytest.raises(NotFoundError, match="Lineage connection not found"):
        await handler.delete_link(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_C_ID,
            EDGE_ID,
        )

    mocks.delete_edges.assert_not_awaited()


@pytest.mark.parametrize("operation", ["batch", "single-create", "single-delete"])
@pytest.mark.asyncio
async def test_write_permission_failure_prevents_repository_access(
    lineage_mocks: HandlerMocks,
    operation: str,
) -> None:
    mocks = lineage_mocks
    mocks.check_permissions.side_effect = InsufficientPermissionsError()

    operation_call: Awaitable[object]
    if operation == "batch":
        operation_call = handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            _creation_changes(),
            LineageVia.API,
        )
    elif operation == "single-create":
        operation_call = handler.create_links(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_A_ID,
            [ARTIFACT_B_ID],
            LineageVia.API,
        )
    else:
        operation_call = handler.delete_link(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_A_ID,
            EDGE_ID,
        )

    with pytest.raises(InsufficientPermissionsError):
        await operation_call

    mocks.get_orbit.assert_not_awaited()
    mocks.get_artifacts.assert_not_awaited()
    mocks.create_edges.assert_not_awaited()
    mocks.delete_edges.assert_not_awaited()
    mocks.delete_edgeless_nodes.assert_not_awaited()


@pytest.mark.asyncio
async def test_orbit_must_belong_to_the_organization(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    mocks.get_orbit.return_value = None

    with pytest.raises(OrbitNotFoundError, match="Orbit not found"):
        await handler.apply_changes(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LineageBatchIn(),
            LineageVia.API,
        )

    mocks.delete_edgeless_nodes.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_graph_returns_empty_graph_without_a_lineage_node(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    focal = _artifact(ARTIFACT_A_ID, "A")
    mocks.get_artifacts.return_value = [focal]

    result = await handler.get_graph(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_A_ID, 2
    )

    assert result.nodes == []
    assert result.edges == []
    assert result.focal_artifact_id == ARTIFACT_A_ID
    assert result.depth == 2
    assert result.truncated is False
    mocks.traverse.assert_not_awaited()
    mocks.check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID,
        USER_ID,
        Resource.ARTIFACT,
        Action.READ,
        ORBIT_ID,
    )


@pytest.mark.asyncio
async def test_get_graph_uses_live_data_and_deleted_node_copies(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    focal = _artifact(
        ARTIFACT_A_ID,
        "Live name",
        artifact_type=ArtifactType.EXPERIMENT,
        collection_name="Experiments",
    )
    focal_node = _node(
        NODE_A_ID,
        ARTIFACT_A_ID,
        "Stale name",
        artifact_type="model",
        collection_name="Old collection",
        x=10.0,
        y=20.0,
    )
    deleted_node = _node(
        NODE_B_ID,
        None,
        "Deleted dataset",
        artifact_type="dataset",
        collection_name="Datasets",
        x=-320.0,
        y=0.0,
    )
    edge = _edge(EDGE_ID, NODE_B_ID, NODE_A_ID, via=LineageVia.UI)
    mocks.get_artifacts.side_effect = [[focal], [focal]]
    mocks.get_node_by_artifact_id.return_value = focal_node
    mocks.traverse.return_value = ([focal_node, deleted_node], [edge], True)

    result = await handler.get_graph(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_A_ID, 5
    )

    assert result.depth == 5
    assert result.truncated is True
    assert result.edges == [edge.to_edge()]
    assert result.nodes[0].name == "Live name"
    assert result.nodes[0].type == "experiment"
    assert result.nodes[0].collection_name == "Experiments"
    assert (result.nodes[0].x, result.nodes[0].y) == (10.0, 20.0)
    assert result.nodes[0].data == focal
    assert result.nodes[0].is_deleted is False
    assert result.nodes[1].artifact_id is None
    assert result.nodes[1].name == "Deleted dataset"
    assert result.nodes[1].type == "dataset"
    assert result.nodes[1].collection_name == "Datasets"
    assert (result.nodes[1].x, result.nodes[1].y) == (-320.0, 0.0)
    assert result.nodes[1].data is None
    assert result.nodes[1].is_deleted is True
    mocks.traverse.assert_awaited_once_with(ORBIT_ID, NODE_A_ID, 5)


@pytest.mark.asyncio
async def test_get_graph_rejects_a_nonexistent_or_foreign_focal_artifact(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks

    with pytest.raises(ArtifactNotFoundError, match="Artifact not found"):
        await handler.get_graph(USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_A_ID, 2)

    mocks.get_node_by_artifact_id.assert_not_awaited()
    mocks.traverse.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_permission_failure_prevents_repository_access(
    lineage_mocks: HandlerMocks,
) -> None:
    mocks = lineage_mocks
    mocks.check_permissions.side_effect = InsufficientPermissionsError()

    with pytest.raises(InsufficientPermissionsError):
        await handler.get_graph(USER_ID, ORGANIZATION_ID, ORBIT_ID, ARTIFACT_A_ID, 2)

    mocks.get_orbit.assert_not_awaited()
    mocks.get_artifacts.assert_not_awaited()
