from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactNotFoundError,
    NotFoundError,
    OrbitNotFoundError,
)
from luml.models.lineage import LineageNodeOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.lineage import (
    LineageBatchIn,
    LineageBatchResult,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineageNodeRef,
    LineagePair,
    LineageVia,
)
from luml.schemas.permissions import Action, Resource


class LineageHandler:
    __repository = LineageRepository(engine)
    __artifact_repository = ArtifactRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __user_repository = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def _check_access(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        action: Action,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            action,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit:
            raise OrbitNotFoundError()

    async def _get_created_by_user(self, user_id: UUID) -> str:
        user = await self.__user_repository.get_public_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return str(user.full_name or user.email)

    @staticmethod
    def _resolve_node_reference(
        ref: LineageNodeRef,
        nodes_by_id: dict[UUID, LineageNodeOrm],
        nodes_by_artifact_id: dict[UUID, LineageNodeOrm],
    ) -> UUID:
        if ref.node_id is not None:
            return nodes_by_id[ref.node_id].id
        if ref.artifact_id is None:
            raise RuntimeError("Validated lineage reference has no identifier")
        return nodes_by_artifact_id[ref.artifact_id].id

    async def _resolve_creation_pairs(
        self,
        orbit_id: UUID,
        pairs: list[LineagePair],
        session: AsyncSession,
    ) -> list[tuple[UUID, UUID]]:
        artifact_ids = list(
            dict.fromkeys(
                ref.artifact_id
                for pair in pairs
                for ref in (pair.source, pair.target)
                if ref.artifact_id is not None
            )
        )
        artifacts = await self.__artifact_repository.get_artifacts_by_ids_in_orbit(
            orbit_id, artifact_ids, session
        )
        artifacts_by_id = {artifact.id: artifact for artifact in artifacts}
        if set(artifacts_by_id) != set(artifact_ids):
            raise ArtifactNotFoundError()

        node_ids = list(
            dict.fromkeys(
                ref.node_id
                for pair in pairs
                for ref in (pair.source, pair.target)
                if ref.node_id is not None
            )
        )
        nodes = await self.__repository.get_nodes_by_ids(orbit_id, node_ids, session)
        nodes_by_id = {node.id: node for node in nodes}
        if set(nodes_by_id) != set(node_ids):
            raise NotFoundError("Lineage node not found")

        nodes_by_artifact_id: dict[UUID, LineageNodeOrm] = {}
        for artifact_id in artifact_ids:
            nodes_by_artifact_id[
                artifact_id
            ] = await self.__repository.get_or_create_node(
                orbit_id, artifacts_by_id[artifact_id], session
            )

        resolved: list[tuple[UUID, UUID]] = []
        seen: set[tuple[UUID, UUID]] = set()
        for pair in pairs:
            node_pair = (
                self._resolve_node_reference(
                    pair.source, nodes_by_id, nodes_by_artifact_id
                ),
                self._resolve_node_reference(
                    pair.target, nodes_by_id, nodes_by_artifact_id
                ),
            )
            if node_pair[0] == node_pair[1]:
                raise ApplicationError(
                    "Artifact cannot be linked to itself",
                    status.HTTP_400_BAD_REQUEST,
                )
            if node_pair in seen:
                continue
            if (node_pair[1], node_pair[0]) in seen:
                raise ApplicationError(
                    "Reverse lineage connection already exists",
                    status.HTTP_409_CONFLICT,
                )
            seen.add(node_pair)
            resolved.append(node_pair)
        return resolved

    async def _resolve_positions(
        self,
        orbit_id: UUID,
        changes: LineageBatchIn,
        session: AsyncSession,
    ) -> dict[UUID, tuple[float, float]]:
        artifact_ids = list(
            dict.fromkeys(
                position.ref.artifact_id
                for position in changes.positions
                if position.ref.artifact_id is not None
            )
        )
        node_ids = list(
            dict.fromkeys(
                position.ref.node_id
                for position in changes.positions
                if position.ref.node_id is not None
            )
        )
        artifact_nodes = await self.__repository.get_nodes_by_artifact_ids(
            orbit_id, artifact_ids, session
        )
        nodes = await self.__repository.get_nodes_by_ids(orbit_id, node_ids, session)
        by_artifact_id = {
            node.artifact_id: node
            for node in artifact_nodes
            if node.artifact_id is not None
        }
        by_node_id = {node.id: node for node in nodes}

        resolved: dict[UUID, tuple[float, float]] = {}
        for position in changes.positions:
            ref = position.ref
            if ref.node_id is not None:
                node = by_node_id.get(ref.node_id)
            elif ref.artifact_id is not None:
                node = by_artifact_id.get(ref.artifact_id)
            else:
                continue
            if node is not None:
                resolved[node.id] = (position.x, position.y)
        return resolved

    async def _apply_changes(
        self,
        user_id: UUID,
        orbit_id: UUID,
        changes: LineageBatchIn,
        via: LineageVia,
    ) -> LineageBatchResult:
        created_by_user = (
            await self._get_created_by_user(user_id) if changes.create else ""
        )

        async with self.__repository.transaction() as session:
            delete_ids = list(dict.fromkeys(changes.delete))
            deleted: list[LineageEdge] = []
            if delete_ids:
                deleted_models = await self.__repository.get_edges_by_ids(
                    orbit_id, delete_ids, session
                )
                if {edge.id for edge in deleted_models} != set(delete_ids):
                    raise NotFoundError("Lineage connection not found")
                deleted = [edge.to_edge() for edge in deleted_models]
                await self.__repository.delete_edges(orbit_id, delete_ids, session)

            created: list[LineageEdge] = []
            if changes.create:
                pairs = await self._resolve_creation_pairs(
                    orbit_id, changes.create, session
                )
                existing_edges = await self.__repository.get_edges_by_pairs(
                    orbit_id, pairs, session
                )
                existing_pairs = {
                    (edge.source_node_id, edge.target_node_id)
                    for edge in existing_edges
                }
                for source, target in pairs:
                    if (source, target) in existing_pairs:
                        raise ApplicationError(
                            "Lineage connection already exists",
                            status.HTTP_409_CONFLICT,
                        )
                    if (target, source) in existing_pairs:
                        raise ApplicationError(
                            "Reverse lineage connection already exists",
                            status.HTTP_409_CONFLICT,
                        )

                created_models = await self.__repository.create_edges(
                    orbit_id,
                    pairs,
                    created_by_user,
                    via,
                    session,
                )
                created = [edge.to_edge() for edge in created_models]

            if changes.positions:
                positions = await self._resolve_positions(orbit_id, changes, session)
                await self.__repository.update_positions(orbit_id, positions, session)
            await self.__repository.delete_edgeless_nodes(orbit_id, session)

            return LineageBatchResult(created=created, deleted=deleted)

    async def apply_changes(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        changes: LineageBatchIn,
        via: LineageVia,
    ) -> LineageBatchResult:
        await self._check_access(user_id, organization_id, orbit_id, Action.UPDATE)
        return await self._apply_changes(user_id, orbit_id, changes, via)

    async def create_links(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        source_artifact_id: UUID,
        target_artifact_ids: list[UUID],
        via: LineageVia,
    ) -> list[LineageEdge]:
        changes = LineageBatchIn(
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=source_artifact_id),
                    target=LineageNodeRef(artifact_id=target_artifact_id),
                )
                for target_artifact_id in target_artifact_ids
            ]
        )
        result = await self.apply_changes(
            user_id, organization_id, orbit_id, changes, via
        )
        return result.created

    async def delete_link(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
        edge_id: UUID,
    ) -> LineageEdge:
        await self._check_access(user_id, organization_id, orbit_id, Action.UPDATE)
        artifacts = await self.__artifact_repository.get_artifacts_by_ids_in_orbit(
            orbit_id, [artifact_id]
        )
        if not artifacts:
            raise ArtifactNotFoundError()

        node = await self.__repository.get_node_by_artifact_id(orbit_id, artifact_id)
        edges = await self.__repository.get_edges_by_ids(orbit_id, [edge_id])
        if (
            node is None
            or not edges
            or node.id not in (edges[0].source_node_id, edges[0].target_node_id)
        ):
            raise NotFoundError("Lineage connection not found")

        result = await self._apply_changes(
            user_id,
            orbit_id,
            LineageBatchIn(delete=[edge_id]),
            LineageVia.UI,
        )
        return result.deleted[0]

    async def get_graph(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
        depth: int,
    ) -> LineageGraph:
        await self._check_access(user_id, organization_id, orbit_id, Action.READ)
        focal_artifacts = (
            await self.__artifact_repository.get_artifacts_by_ids_in_orbit(
                orbit_id, [artifact_id]
            )
        )
        if not focal_artifacts:
            raise ArtifactNotFoundError()

        focal_node = await self.__repository.get_node_by_artifact_id(
            orbit_id, artifact_id
        )
        if focal_node is None:
            return LineageGraph(
                nodes=[],
                edges=[],
                focal_artifact_id=artifact_id,
                depth=depth,
                truncated=False,
            )

        nodes, edge_models, truncated = await self.__repository.traverse(
            orbit_id, focal_node.id, depth
        )
        live_artifact_ids = [
            node.artifact_id for node in nodes if node.artifact_id is not None
        ]
        live_artifacts = await self.__artifact_repository.get_artifacts_by_ids_in_orbit(
            orbit_id, live_artifact_ids
        )
        artifacts_by_id = {artifact.id: artifact for artifact in live_artifacts}

        lineage_nodes: list[LineageNode] = []
        for node in nodes:
            data = (
                artifacts_by_id.get(node.artifact_id)
                if node.artifact_id is not None
                else None
            )
            lineage_nodes.append(
                LineageNode(
                    id=node.id,
                    artifact_id=node.artifact_id,
                    type=data.type.value if data else node.type,
                    name=(data.name or node.name) if data else node.name,
                    collection_name=(
                        data.collection_name if data else node.collection_name
                    ),
                    x=node.x,
                    y=node.y,
                    is_deleted=node.artifact_id is None,
                    data=data,
                )
            )

        return LineageGraph(
            nodes=lineage_nodes,
            edges=[edge.to_edge() for edge in edge_models],
            focal_artifact_id=artifact_id,
            depth=depth,
            truncated=truncated,
        )
