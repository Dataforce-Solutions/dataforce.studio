from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import delete, exists, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from luml.constants import LINEAGE_MAX_NODES
from luml.models.artifacts import ArtifactOrm
from luml.models.collection import CollectionOrm
from luml.models.lineage import LineageEdgeOrm, LineageNodeOrm
from luml.repositories.base import RepositoryBase
from luml.schemas.artifacts import ArtifactListed
from luml.schemas.lineage import LineageVia


class LineageRepository(RepositoryBase):
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        async with self._get_session() as session, session.begin():
            yield session

    @asynccontextmanager
    async def _session_scope(
        self, session: AsyncSession | None
    ) -> AsyncIterator[tuple[AsyncSession, bool]]:
        if session is not None:
            yield session, False
            return

        async with self._get_session() as owned_session:
            yield owned_session, True

    @staticmethod
    async def _finish_write(session: AsyncSession, owns_session: bool) -> None:
        if owns_session:
            await session.commit()
        else:
            await session.flush()

    async def get_or_create_node(
        self,
        orbit_id: UUID,
        artifact: ArtifactListed,
        session: AsyncSession | None = None,
    ) -> LineageNodeOrm:
        async with self._session_scope(session) as (db_session, owns_session):
            statement = (
                insert(LineageNodeOrm)
                .values(
                    orbit_id=orbit_id,
                    artifact_id=artifact.id,
                    name=artifact.name,
                    type=artifact.type.value,
                    collection_name=artifact.collection_name,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        LineageNodeOrm.orbit_id,
                        LineageNodeOrm.artifact_id,
                    ],
                    index_where=LineageNodeOrm.artifact_id.is_not(None),
                )
            )
            await db_session.execute(statement)
            node = await db_session.scalar(
                select(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    LineageNodeOrm.artifact_id == artifact.id,
                )
            )
            if node is None:
                raise RuntimeError("Lineage node was not created")

            await self._finish_write(db_session, owns_session)
            if owns_session:
                await db_session.refresh(node)
            return node

    async def get_node_by_artifact_id(
        self,
        orbit_id: UUID,
        artifact_id: UUID,
        session: AsyncSession | None = None,
    ) -> LineageNodeOrm | None:
        async with self._session_scope(session) as (db_session, _):
            result = await db_session.scalars(
                select(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    LineageNodeOrm.artifact_id == artifact_id,
                )
            )
            return result.one_or_none()

    async def get_nodes_by_ids(
        self,
        orbit_id: UUID,
        node_ids: Sequence[UUID],
        session: AsyncSession | None = None,
    ) -> list[LineageNodeOrm]:
        if not node_ids:
            return []

        async with self._session_scope(session) as (db_session, _):
            result = await db_session.scalars(
                select(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    LineageNodeOrm.id.in_(node_ids),
                )
            )
            return list(result.all())

    async def get_nodes_by_artifact_ids(
        self,
        orbit_id: UUID,
        artifact_ids: Sequence[UUID],
        session: AsyncSession | None = None,
    ) -> list[LineageNodeOrm]:
        if not artifact_ids:
            return []

        async with self._session_scope(session) as (db_session, _):
            result = await db_session.scalars(
                select(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    LineageNodeOrm.artifact_id.in_(artifact_ids),
                )
            )
            return list(result.all())

    async def create_edges(
        self,
        orbit_id: UUID,
        pairs: Sequence[tuple[UUID, UUID]],
        created_by_user: str,
        created_via: LineageVia,
        session: AsyncSession | None = None,
    ) -> list[LineageEdgeOrm]:
        if not pairs:
            return []

        async with self._session_scope(session) as (db_session, owns_session):
            edges = [
                LineageEdgeOrm(
                    orbit_id=orbit_id,
                    source_node_id=source,
                    target_node_id=target,
                    created_by_user=created_by_user,
                    created_via=created_via.value,
                )
                for source, target in pairs
            ]
            db_session.add_all(edges)
            await self._finish_write(db_session, owns_session)
            if owns_session:
                for edge in edges:
                    await db_session.refresh(edge)
            return edges

    async def get_edges_by_ids(
        self,
        orbit_id: UUID,
        edge_ids: Sequence[UUID],
        session: AsyncSession | None = None,
    ) -> list[LineageEdgeOrm]:
        if not edge_ids:
            return []

        async with self._session_scope(session) as (db_session, _):
            result = await db_session.scalars(
                select(LineageEdgeOrm)
                .where(
                    LineageEdgeOrm.orbit_id == orbit_id,
                    LineageEdgeOrm.id.in_(edge_ids),
                )
                .order_by(LineageEdgeOrm.created_at, LineageEdgeOrm.id)
            )
            return list(result.all())

    async def get_edges_by_pairs(
        self,
        orbit_id: UUID,
        pairs: Sequence[tuple[UUID, UUID]],
        session: AsyncSession | None = None,
    ) -> list[LineageEdgeOrm]:
        if not pairs:
            return []

        requested = list(
            dict.fromkeys([*pairs, *((target, source) for source, target in pairs)])
        )
        async with self._session_scope(session) as (db_session, _):
            result = await db_session.scalars(
                select(LineageEdgeOrm)
                .where(
                    LineageEdgeOrm.orbit_id == orbit_id,
                    tuple_(
                        LineageEdgeOrm.source_node_id,
                        LineageEdgeOrm.target_node_id,
                    ).in_(requested),
                )
                .order_by(LineageEdgeOrm.created_at, LineageEdgeOrm.id)
            )
            return list(result.all())

    async def delete_edges(
        self,
        orbit_id: UUID,
        edge_ids: Sequence[UUID],
        session: AsyncSession | None = None,
    ) -> None:
        if not edge_ids:
            return

        async with self._session_scope(session) as (db_session, owns_session):
            await db_session.execute(
                delete(LineageEdgeOrm).where(
                    LineageEdgeOrm.orbit_id == orbit_id,
                    LineageEdgeOrm.id.in_(edge_ids),
                )
            )
            await self._finish_write(db_session, owns_session)

    async def update_positions(
        self,
        orbit_id: UUID,
        positions: dict[UUID, tuple[float, float]],
        session: AsyncSession | None = None,
    ) -> None:
        if not positions:
            return

        async with self._session_scope(session) as (db_session, owns_session):
            for node_id, (x, y) in positions.items():
                await db_session.execute(
                    update(LineageNodeOrm)
                    .where(
                        LineageNodeOrm.orbit_id == orbit_id,
                        LineageNodeOrm.id == node_id,
                    )
                    .values(x=x, y=y)
                )
            await self._finish_write(db_session, owns_session)

    async def delete_edgeless_nodes(
        self,
        orbit_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session_scope(session) as (db_session, owns_session):
            has_edge = exists(
                select(LineageEdgeOrm.id).where(
                    or_(
                        LineageEdgeOrm.source_node_id == LineageNodeOrm.id,
                        LineageEdgeOrm.target_node_id == LineageNodeOrm.id,
                    )
                )
            )
            await db_session.execute(
                delete(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    ~has_edge,
                )
            )
            await self._finish_write(db_session, owns_session)

    async def refresh_node_copy(
        self,
        artifact_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session_scope(session) as (db_session, owns_session):
            artifact_copy = (
                await db_session.execute(
                    select(
                        ArtifactOrm.name,
                        ArtifactOrm.type,
                        CollectionOrm.name,
                    )
                    .join(
                        CollectionOrm,
                        ArtifactOrm.collection_id == CollectionOrm.id,
                    )
                    .where(ArtifactOrm.id == artifact_id)
                )
            ).one_or_none()
            if artifact_copy is None:
                return

            name, artifact_type, collection_name = artifact_copy
            await db_session.execute(
                update(LineageNodeOrm)
                .where(LineageNodeOrm.artifact_id == artifact_id)
                .values(
                    name=name,
                    type=artifact_type,
                    collection_name=collection_name,
                )
            )
            await self._finish_write(db_session, owns_session)

    async def traverse(
        self,
        orbit_id: UUID,
        focal_node_id: UUID,
        depth: int,
        session: AsyncSession | None = None,
    ) -> tuple[list[LineageNodeOrm], list[LineageEdgeOrm], bool]:
        if depth < 1:
            raise ValueError("Lineage depth must be positive")

        async with self._session_scope(session) as (db_session, _):
            focal_node = await db_session.scalar(
                select(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    LineageNodeOrm.id == focal_node_id,
                )
            )
            if focal_node is None:
                return [], [], False

            discovered_ids = [focal_node.id]
            seen_node_ids = {focal_node.id}
            seen_edges: dict[UUID, LineageEdgeOrm] = {}
            frontier = [focal_node.id]
            truncated = False

            for level in range(depth):
                result = await db_session.scalars(
                    select(LineageEdgeOrm)
                    .where(
                        LineageEdgeOrm.orbit_id == orbit_id,
                        or_(
                            LineageEdgeOrm.source_node_id.in_(frontier),
                            LineageEdgeOrm.target_node_id.in_(frontier),
                        ),
                    )
                    .order_by(LineageEdgeOrm.created_at, LineageEdgeOrm.id)
                )
                level_edges = [
                    edge for edge in result.all() if edge.id not in seen_edges
                ]
                next_frontier: list[UUID] = []
                next_ids: set[UUID] = set()
                for edge in level_edges:
                    for node_id in (edge.source_node_id, edge.target_node_id):
                        if node_id not in seen_node_ids and node_id not in next_ids:
                            next_ids.add(node_id)
                            next_frontier.append(node_id)

                resulting_node_count = len(seen_node_ids) + len(next_frontier)
                if level > 0 and resulting_node_count > LINEAGE_MAX_NODES:
                    truncated = True
                    break

                seen_edges.update((edge.id, edge) for edge in level_edges)
                discovered_ids.extend(next_frontier)
                seen_node_ids.update(next_frontier)
                frontier = next_frontier

                if resulting_node_count > LINEAGE_MAX_NODES:
                    truncated = True
                    break
                if not frontier:
                    break

            nodes_result = await db_session.scalars(
                select(LineageNodeOrm).where(
                    LineageNodeOrm.orbit_id == orbit_id,
                    LineageNodeOrm.id.in_(discovered_ids),
                )
            )
            nodes_by_id = {node.id: node for node in nodes_result.all()}
            nodes = [
                nodes_by_id[node_id]
                for node_id in discovered_ids
                if node_id in nodes_by_id
            ]
            edges = sorted(
                seen_edges.values(),
                key=lambda edge: (edge.created_at, edge.id),
            )
            return nodes, edges, truncated
