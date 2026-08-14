import json
import re
import sqlite3
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import cast

from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.branches import get_branch
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    InputRecord,
    JsonValue,
    Materialization,
    OutputRecord,
    RunRecordedOp,
)

from .memo import find_memo_hit, memo_key_for, record_memo_hit
from .queue import SerialPriorityQueue
from .staleness import StalenessVerdict, derive_staleness


@dataclass(frozen=True)
class Dependency:
    input_name: str
    uid: str
    output: str


@dataclass(frozen=True)
class PlanNode:
    uid: str
    version_id: str
    slug: str
    definition_hash: str
    dependencies: tuple[Dependency, ...]
    manifest: dict[str, JsonValue]
    direct: StalenessVerdict
    transitive: StalenessVerdict


@dataclass
class ExecutionPlan:
    branch_id: str
    target_uid: str
    nodes: list[PlanNode]
    previous_outputs: dict[str, dict[str, str]]
    changed_outputs: dict[str, frozenset[str]] = field(default_factory=dict)
    pruned: list[str] = field(default_factory=list)

    def should_run(self, node: PlanNode) -> bool:
        if node.direct.state != "synced":
            return True
        return any(
            dependency.output in self.changed_outputs.get(dependency.uid, frozenset())
            for dependency in node.dependencies
        )

    def complete(self, uid: str, outputs: dict[str, OutputRecord]) -> None:
        previous = self.previous_outputs.get(uid, {})
        changed = {
            name
            for name, output in outputs.items()
            if previous.get(name) != output.content_hash
        }
        changed.update(set(previous) - set(outputs))
        self.changed_outputs[uid] = frozenset(changed)

    def prune(self, uid: str) -> None:
        self.pruned.append(uid)
        self.changed_outputs[uid] = frozenset()


@dataclass(frozen=True)
class ExecutionResult:
    outputs: dict[str, OutputRecord]
    cost_seconds: float
    identity_dependent: bool = False
    log_ref: str | None = None


@dataclass(frozen=True)
class RunSummary:
    executed: tuple[str, ...]
    memo_hits: tuple[str, ...]
    pruned: tuple[str, ...]


@dataclass(frozen=True)
class _RunOutcome:
    materialization: Materialization
    origin_branch: str


Executor = Callable[[PlanNode, dict[str, InputRecord]], Awaitable[ExecutionResult]]


class ExecutionCancelledError(Exception):
    pass


class Planner:
    def __init__(
        self,
        store: FlowStore,
        *,
        lib_changed_files: Iterable[str] = (),
        env_lock_hash: str | None = None,
    ) -> None:
        self.store = store
        self.lib_changed_files = tuple(lib_changed_files)
        self.env_lock_hash = env_lock_hash

    def plan(self, branch: str, target_uid: str) -> ExecutionPlan:
        branch_id = get_branch(self.store, branch).branch_id
        cells = _load_cells(self.store, branch_id)
        if target_uid not in cells:
            raise LookupError(f"cell {target_uid} is not selected on branch {branch}")
        views = {
            uid: derive_staleness(
                self.store,
                branch_id,
                uid,
                lib_changed_files=self.lib_changed_files,
                env_lock_hash=self.env_lock_hash,
            )
            for uid in cells
        }
        ordered: list[PlanNode] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(uid: str) -> None:
            if uid in visited:
                return
            if uid in visiting:
                raise ValueError("cell dependency graph contains a cycle")
            visiting.add(uid)
            cell = cells[uid]
            for dependency in cell.dependencies:
                if dependency.uid in cells:
                    visit(dependency.uid)
            visiting.remove(uid)
            visited.add(uid)
            state = views[uid]
            if state.transitive.state != "synced":
                ordered.append(
                    PlanNode(
                        uid=cell.uid,
                        version_id=cell.version_id,
                        slug=cell.slug,
                        definition_hash=cell.definition_hash,
                        dependencies=cell.dependencies,
                        manifest=cell.manifest,
                        direct=state.direct,
                        transitive=state.transitive,
                    )
                )

        visit(target_uid)
        return ExecutionPlan(
            branch_id=branch_id,
            target_uid=target_uid,
            nodes=ordered,
            previous_outputs=_baseline_outputs(self.store, branch_id),
        )

    def eager_candidates(
        self,
        branch: str,
        changed_uids: Iterable[str],
        *,
        threshold_seconds: float | None = None,
    ) -> list[str]:
        branch_id = get_branch(self.store, branch).branch_id
        cells = _load_cells(self.store, branch_id)
        threshold = (
            _configured_eager_threshold(self.store)
            if threshold_seconds is None
            else threshold_seconds
        )
        downstream: dict[str, set[str]] = {}
        for cell in cells.values():
            for dependency in cell.dependencies:
                downstream.setdefault(dependency.uid, set()).add(cell.uid)
        candidates: list[str] = []
        seen = set(changed_uids)
        pending = list(seen)
        while pending:
            parent = pending.pop(0)
            for uid in sorted(downstream.get(parent, set())):
                if uid in seen:
                    continue
                seen.add(uid)
                pending.append(uid)
                cost = _latest_cost(self.store, uid)
                if _eager_opt_in(cells[uid].manifest) or (
                    cost is not None and cost < threshold
                ):
                    candidates.append(uid)
        return candidates


@dataclass(frozen=True)
class _Cell:
    uid: str
    version_id: str
    slug: str
    definition_hash: str
    dependencies: tuple[Dependency, ...]
    manifest: dict[str, JsonValue]


class Scheduler:
    def __init__(
        self,
        store: FlowStore,
        executor: Executor,
        *,
        lib_tree_hash: str,
        lib_changed_files: Iterable[str] = (),
        env_lock_hash: str | None = None,
        env_lock_hash_provider: Callable[[], str | None] | None = None,
        queue: SerialPriorityQueue[_RunOutcome] | None = None,
        actor: str = "system:scheduler",
        intent: str | None = None,
    ) -> None:
        self.store = store
        self.executor = executor
        self.lib_tree_hash = lib_tree_hash
        self.lib_changed_files = tuple(lib_changed_files)
        self.env_lock_hash = env_lock_hash
        self.env_lock_hash_provider = env_lock_hash_provider
        self.queue = queue or SerialPriorityQueue(active_branch=store.branch_id)
        self.actor = actor
        self.intent = intent

    async def run(self, branch: str, target_uid: str) -> RunSummary:
        target_branch = get_branch(self.store, branch)
        current_env_lock_hash = self._current_env_lock_hash()
        plan = Planner(
            self.store,
            lib_changed_files=self.lib_changed_files,
            env_lock_hash=current_env_lock_hash,
        ).plan(target_branch.branch_id, target_uid)
        executed: list[str] = []
        memo_hits: list[str] = []
        for node in plan.nodes:
            if not plan.should_run(node):
                plan.prune(node.uid)
                continue
            inputs = _resolve_inputs(self.store, plan.branch_id, node.dependencies)
            volatility = str(node.manifest.get("volatility", "pure"))
            env_sensitive = node.manifest.get("env_sensitive", False) is True
            key = memo_key_for(
                node.definition_hash,
                self.lib_tree_hash,
                {name: record.content_hash for name, record in inputs.items()},
                env_sensitive=env_sensitive,
                env_lock_hash=current_env_lock_hash,
            )
            hit = find_memo_hit(
                self.store,
                plan.branch_id,
                key,
                volatility=volatility,
            )
            if hit is not None:
                record_memo_hit(
                    self.store,
                    plan.branch_id,
                    node.uid,
                    node.version_id,
                    key,
                    hit.mat_id,
                    actor=self.actor,
                    intent=self.intent,
                )
                memo_hits.append(node.uid)
                plan.complete(node.uid, hit.outputs)
                continue

            queue_key = key
            if volatility in {"nondeterministic", "external"}:
                queue_key = f"{key}:{mint_ulid()}"
            outcome = await self.queue.run(
                queue_key,
                plan.branch_id,
                self._execution(plan.branch_id, node, inputs, key),
            )
            if outcome.origin_branch != plan.branch_id:
                if outcome.materialization.identity_dependent:
                    outcome = await self.queue.run(
                        f"{key}:{plan.branch_id}:identity",
                        plan.branch_id,
                        self._execution(plan.branch_id, node, inputs, key),
                    )
                    executed.append(node.uid)
                else:
                    record_memo_hit(
                        self.store,
                        plan.branch_id,
                        node.uid,
                        node.version_id,
                        key,
                        outcome.materialization.mat_id,
                        actor=self.actor,
                        intent=self.intent,
                    )
                    memo_hits.append(node.uid)
            else:
                executed.append(node.uid)
            plan.complete(node.uid, outcome.materialization.outputs)
        return RunSummary(
            executed=tuple(executed),
            memo_hits=tuple(memo_hits),
            pruned=tuple(plan.pruned),
        )

    async def eager_after_change(
        self, branch: str, changed_uids: Iterable[str]
    ) -> dict[str, RunSummary]:
        candidates = Planner(self.store).eager_candidates(branch, changed_uids)
        results: dict[str, RunSummary] = {}
        for uid in candidates:
            results[uid] = await self.run(branch, uid)
        return results

    async def _execute(
        self,
        branch_id: str,
        node: PlanNode,
        inputs: dict[str, InputRecord],
        key: str,
    ) -> _RunOutcome:
        mat_id = mint_ulid()
        started_step = self.store.last_step + 1
        try:
            result = await self.executor(node, inputs)
        except ExecutionCancelledError:
            self.store.commit(
                actor=self.actor,
                intent=self.intent or f"cancel {node.slug}",
                branch=branch_id,
                ops=[
                    RunRecordedOp(
                        mat_id=mat_id,
                        version_id=node.version_id,
                        memo_key=key,
                        state="cancelled",
                        inputs=inputs,
                        env_lock_hash=self._current_env_lock_hash(),
                        started_step=started_step,
                        finished_step=self.store.last_step + 1,
                    )
                ],
            )
            raise
        except Exception as error:
            log_ref = getattr(error, "log_ref", None)
            if not isinstance(log_ref, str):
                log_ref = None
            self.store.commit(
                actor=self.actor,
                intent=self.intent or f"run {node.slug}",
                branch=branch_id,
                ops=[
                    RunRecordedOp(
                        mat_id=mat_id,
                        version_id=node.version_id,
                        memo_key=key,
                        state="failed",
                        inputs=inputs,
                        env_lock_hash=self._current_env_lock_hash(),
                        log_ref=log_ref,
                        started_step=started_step,
                        finished_step=self.store.last_step + 1,
                    )
                ],
            )
            raise
        finished_step = self.store.last_step + 1
        env_lock_hash = self._current_env_lock_hash()
        operation = RunRecordedOp(
            mat_id=mat_id,
            version_id=node.version_id,
            memo_key=key,
            state="succeeded",
            inputs=inputs,
            outputs=result.outputs,
            identity_dependent=result.identity_dependent,
            env_lock_hash=env_lock_hash,
            cost_seconds=result.cost_seconds,
            log_ref=result.log_ref,
            started_step=started_step,
            finished_step=finished_step,
        )
        self.store.commit(
            actor=self.actor,
            intent=self.intent or f"run {node.slug}",
            branch=branch_id,
            ops=[operation],
        )
        materialization = Materialization(
            mat_id=mat_id,
            version_id=node.version_id,
            memo_key=key,
            state="succeeded",
            branch_id=branch_id,
            inputs=inputs,
            outputs=result.outputs,
            identity_dependent=result.identity_dependent,
            env_lock_hash=env_lock_hash,
            cost_seconds=result.cost_seconds,
            log_ref=result.log_ref,
            started_step=started_step,
            finished_step=finished_step,
        )
        return _RunOutcome(materialization=materialization, origin_branch=branch_id)

    def _current_env_lock_hash(self) -> str | None:
        if self.env_lock_hash_provider is not None:
            return self.env_lock_hash_provider()
        return self.env_lock_hash

    def _execution(
        self,
        branch_id: str,
        node: PlanNode,
        inputs: dict[str, InputRecord],
        key: str,
    ) -> Callable[[], Awaitable[_RunOutcome]]:
        async def execute() -> _RunOutcome:
            return await self._execute(branch_id, node, inputs, key)

        return execute


def _load_cells(store: FlowStore, branch_id: str) -> dict[str, _Cell]:
    rows = (
        _connection(store)
        .execute(
            """
        SELECT selections.uid, versions.version_id, versions.slug,
               versions.definition_hash, versions.manifest
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ?
        """,
            (branch_id,),
        )
        .fetchall()
    )
    cells: dict[str, _Cell] = {}
    for row in rows:
        manifest = cast(dict[str, JsonValue], json.loads(row["manifest"]))
        raw_inputs = manifest.get("bound_inputs", manifest.get("consumes", {}))
        dependencies: list[Dependency] = []
        if isinstance(raw_inputs, dict):
            for name, reference in raw_inputs.items():
                if not isinstance(name, str) or not isinstance(reference, str):
                    continue
                parsed = _parse_bound_reference(reference)
                if parsed is not None:
                    dependencies.append(Dependency(name, parsed[0], parsed[1]))
        uid = str(row["uid"])
        cells[uid] = _Cell(
            uid=uid,
            version_id=str(row["version_id"]),
            slug=str(row["slug"]),
            definition_hash=str(row["definition_hash"]),
            dependencies=tuple(dependencies),
            manifest=manifest,
        )
    return cells


def _resolve_inputs(
    store: FlowStore, branch_id: str, dependencies: tuple[Dependency, ...]
) -> dict[str, InputRecord]:
    connection = _connection(store)
    inputs: dict[str, InputRecord] = {}
    for dependency in dependencies:
        row = connection.execute(
            """
            SELECT baselines.mat_id, materializations.outputs
            FROM baselines
            JOIN materializations USING(mat_id)
            WHERE baselines.branch_id = ? AND baselines.uid = ?
              AND materializations.state = 'succeeded'
            """,
            (branch_id, dependency.uid),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"input {dependency.input_name} is not materialized")
        outputs = cast(dict[str, dict[str, object]], json.loads(row["outputs"]))
        output = outputs.get(dependency.output)
        if output is None:
            raise RuntimeError(
                f"input {dependency.input_name} references missing output "
                f"{dependency.output}"
            )
        inputs[dependency.input_name] = InputRecord(
            uid=dependency.uid,
            output=dependency.output,
            content_hash=str(output["content_hash"]),
            mat_id=str(row["mat_id"]),
        )
    return inputs


def _baseline_outputs(store: FlowStore, branch_id: str) -> dict[str, dict[str, str]]:
    rows = (
        _connection(store)
        .execute(
            """
        SELECT baselines.uid, materializations.outputs
        FROM baselines JOIN materializations USING(mat_id)
        WHERE baselines.branch_id = ? AND materializations.state = 'succeeded'
        """,
            (branch_id,),
        )
        .fetchall()
    )
    return {
        str(row["uid"]): {
            name: str(record["content_hash"])
            for name, record in cast(
                dict[str, dict[str, object]], json.loads(row["outputs"])
            ).items()
        }
        for row in rows
    }


def _latest_cost(store: FlowStore, uid: str) -> float | None:
    row = (
        _connection(store)
        .execute(
            """
        SELECT materializations.cost_seconds
        FROM materializations
        JOIN asset_versions USING(version_id)
        WHERE asset_versions.uid = ? AND materializations.state = 'succeeded'
          AND materializations.cost_seconds IS NOT NULL
        ORDER BY materializations.rowid DESC LIMIT 1
        """,
            (uid,),
        )
        .fetchone()
    )
    return None if row is None else float(row[0])


def _configured_eager_threshold(store: FlowStore) -> float:
    match = re.search(
        r"^\s*eager_cost_threshold_s:\s*([0-9]+(?:\.[0-9]+)?)\s*$",
        (store.flow_dir / "flow.yaml").read_text(),
        re.MULTILINE,
    )
    return 5.0 if match is None else float(match.group(1))


def _eager_opt_in(manifest: dict[str, JsonValue]) -> bool:
    if manifest.get("eager") is True:
        return True
    produces = manifest.get("produces", {})
    return isinstance(produces, dict) and any(
        isinstance(value, dict) and value.get("eager") is True
        for value in produces.values()
    )


def _parse_bound_reference(reference: str) -> tuple[str, str] | None:
    if not reference.startswith("uid:") or "." not in reference[4:]:
        return None
    return cast(tuple[str, str], tuple(reference[4:].split(".", 1)))


def _connection(store: FlowStore) -> sqlite3.Connection:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    return connection
