from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

from lumlflow.flow.dsl.accept import compute_lib_tree_hash
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.portable import export_projection
from lumlflow.flow.scheduler.planner import ExecutionResult, PlanNode, Scheduler
from lumlflow.flow.scheduler.queue import SerialPriorityQueue
from lumlflow.flow.scheduler.staleness import derive_all_staleness
from lumlflow.flow.store import branches
from lumlflow.flow.store.branches import get_branch
from lumlflow.flow.store.cas import _replace_with_retry, atomic_write
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import Branch, InputRecord, JsonValue

from .envs import EnvironmentManager
from .errors import DaemonRpcError
from .kernel_proc import KernelProcess
from .projections import (
    EditConflictError,
    ParamEditConflictError,
    ProjectionManager,
)
from .reconcile import Reconciler
from .stream import DaemonStreamServer, StreamHub
from .uploads import LumlUploadAPI, UploadQueue
from .watcher import FlowWatcher

_UPLOAD_RETRY_SECONDS = 5.0


class StoreOwnershipError(RuntimeError):
    pass


class ExclusiveStoreLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.file: BinaryIO | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if file.tell() == 0:
                    file.write(b"\0")
                    file.flush()
                file.seek(0)
                mode: Any = msvcrt.LK_NBLCK  # type: ignore[attr-defined]
                msvcrt.locking(  # type: ignore[attr-defined]
                    file.fileno(), mode, 1
                )
            else:
                import fcntl

                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            file.close()
            raise StoreOwnershipError("another daemon owns this flow store") from error
        self.file = file

    def release(self) -> None:
        if self.file is None:
            return
        if os.name == "nt":
            import msvcrt

            self.file.seek(0)
            mode = msvcrt.LK_UNLCK  # type: ignore[attr-defined]
            msvcrt.locking(  # type: ignore[attr-defined]
                self.file.fileno(), mode, 1
            )
        else:
            import fcntl

            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()
        self.file = None

    def __enter__(self) -> ExclusiveStoreLock:
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


class DaemonRuntime:
    def __init__(
        self,
        store: FlowStore,
        *,
        watch_worktree: bool = True,
        upload_api: LumlUploadAPI | None = None,
    ) -> None:
        self.store = store
        self.worktree_enabled = watch_worktree
        self.streams = StreamHub(store.journal)
        self._remove_stream_listener = store.add_commit_listener(
            self.streams.publish_transaction
        )
        self.kernel = KernelProcess(
            store.flow_dir, event_handler=self.streams.publish_kernel_event
        )
        self.envs = EnvironmentManager(store)
        self.projections = ProjectionManager(store)
        if watch_worktree:
            self.projections.recover_stale_session()
        self.reconciler = Reconciler(store, self.projections)
        self.watcher = FlowWatcher(self.reconciler) if watch_worktree else None
        if watch_worktree:
            self.reconciler.reconcile("cold")
        self.lib_tree_hash = compute_lib_tree_hash(store.flow_dir)
        self.lib_files = _lib_file_hashes(store.flow_dir)
        self.queue: SerialPriorityQueue[Any] = SerialPriorityQueue(
            active_branch=store.branch_id
        )
        self._run_lock = asyncio.Lock()
        self.uploads = UploadQueue(store, upload_api)
        self._upload_task: asyncio.Task[Any] | None = None
        self._upload_wakeup = asyncio.Event()
        self._closing = False
        self.projections.refresh_generated_docs()
        if any(item.state in {"queued", "failed"} for item in self.uploads.items()):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                self._schedule_uploads()

    async def dispatch(self, method: str, params: dict[str, JsonValue]) -> JsonValue:
        if method in {
            "status",
            "tree",
            "graph",
            "cells_list",
            "cells_show",
            "run",
            "asset_preview",
            "asset_page",
            "cells_edit",
            "cells_new",
            "params_edit",
            "sweep",
            "sweep_compare",
            "switch",
            "fork",
            "rewind",
            "preflight",
            "adopt",
            "diff",
            "rename",
            "context",
            "eval",
            "promote",
            "export",
        }:
            actor = params.get("actor")
            if actor is not None and not isinstance(actor, str):
                raise DaemonRpcError(-32602, "actor must be a string")
            self._quiesce(actor or self.projections.lock_holder)
        if method == "handshake":
            return {
                "protocol": 1,
                "pid": os.getpid(),
                "flow": self.store.flow_id,
            }
        if method == "status":
            return self._status()
        if method == "env_status":
            return await asyncio.to_thread(self.envs.status, include_packages=True)
        if method in {"env_add", "env_remove"}:
            package = params.get("package")
            if not isinstance(package, str) or not package.strip():
                raise DaemonRpcError(-32602, f"{method} requires a package")
            env_actor, env_intent = self._mutation_metadata(params)
            async with self._run_lock:
                operation = self.envs.add if method == "env_add" else self.envs.remove
                await operation(package, actor=env_actor, intent=env_intent)
                if self.kernel.running:
                    loaded = await self.kernel.loaded_packages()
                    await asyncio.to_thread(self.envs.compare_loaded_packages, loaded)
            return self.envs.status()
        if method == "tree":
            return self._tree(params)
        if method == "graph":
            return self._graph(params)
        if method == "cells_list":
            return self._cells_list(params)
        if method == "cells_show":
            return self._cells_show(params)
        if method == "run":
            target = params.get("target")
            if not isinstance(target, str) or not target:
                raise DaemonRpcError(-32602, "run requires a target")
            branch = params.get("branch")
            if branch is not None and not isinstance(branch, str):
                raise DaemonRpcError(-32602, "branch must be a string")
            actor = params.get("actor")
            intent = params.get("intent")
            force = params.get("force", False)
            if actor is not None and not isinstance(actor, str):
                raise DaemonRpcError(-32602, "actor must be a string")
            if intent is not None and not isinstance(intent, str):
                raise DaemonRpcError(-32602, "intent must be a string")
            if not isinstance(force, bool):
                raise DaemonRpcError(-32602, "force must be a boolean")
            if actor is None and intent is None:
                if force:
                    return await self._run(target, branch, force=True)
                return await self._run(target, branch)
            return await self._run(
                target,
                branch,
                actor=actor or "user",
                intent=intent,
                force=force,
            )
        if method == "asset_preview":
            target, branch = self._asset_request(params)
            output = self._resolve_output(branch, target)
            preview_ref = output.get("preview_ref")
            if not isinstance(preview_ref, str):
                raise DaemonRpcError(-32004, f"preview not found: {target}")
            return _json_value(json.loads(self.store.cas.get("previews", preview_ref)))
        if method == "asset_page":
            target, branch = self._asset_request(params)
            query = params.get("query", {})
            if not isinstance(query, dict):
                raise DaemonRpcError(-32602, "query must be an object")
            output = self._resolve_output(branch, target)
            value_ref = output.get("value_ref")
            kind = output.get("kind")
            if not isinstance(value_ref, str) or not isinstance(kind, str):
                raise DaemonRpcError(-32004, f"persisted asset not found: {target}")
            return _json_value(
                await self.kernel.request(
                    "page",
                    {"value_ref": value_ref, "kind": kind, "query": query},
                )
            )
        if method == "eval":
            code = params.get("code")
            if not isinstance(code, str):
                raise DaemonRpcError(-32602, "eval requires code")
            branch = params.get("branch")
            if branch is not None and not isinstance(branch, str):
                raise DaemonRpcError(-32602, "branch must be a string")
            paranoid = params.get("paranoid", self._paranoid_mode_enabled())
            if not isinstance(paranoid, bool):
                raise DaemonRpcError(-32602, "paranoid must be a boolean")
            selected_branch = get_branch(self.store, branch or self.store.branch_id)
            raw = await self.kernel.request(
                "eval",
                {
                    "branch_slice": self._eval_slice(selected_branch.branch_id),
                    "code": code,
                    "paranoid": paranoid,
                },
            )
            if not isinstance(raw, dict):
                raise DaemonRpcError(-32603, "kernel returned an invalid eval response")
            if raw.get("state") != "succeeded":
                error_type = raw.get("error_type", "EvaluationError")
                message = raw.get("error", "evaluation failed")
                raise DaemonRpcError(-32010, f"{error_type}: {message}")
            return _json_value(raw)
        if method == "promote":
            slug = params.get("slug")
            output_name = params.get("output")
            if not isinstance(slug, str) or not isinstance(output_name, str):
                raise DaemonRpcError(-32602, "promote requires a cell and output")
            promotion_branch = self._branch_param(params)
            actor, intent = self._mutation_metadata(params)
            try:
                item = self.uploads.promote(
                    promotion_branch.branch_id,
                    slug,
                    output_name,
                    actor=actor,
                    intent=intent,
                )
            except LookupError as error:
                raise DaemonRpcError(-32004, str(error)) from error
            self._schedule_uploads()
            return {
                "cell": slug,
                "output": output_name,
                "state": item.state,
            }
        if method == "cancel":
            run_id = params.get("run_id")
            if run_id is not None and not isinstance(run_id, str):
                raise DaemonRpcError(-32602, "run_id must be a string")
            result = await self.kernel.cancel(run_id)
            return {"cancelled": result.get("cancelled", False) is True}
        if method == "agent_begin":
            actor = params.get("actor") or params.get("label")
            if not isinstance(actor, str) or not actor:
                raise DaemonRpcError(-32602, "agent_begin requires an actor")
            intent = params.get("intent")
            if intent is not None and not isinstance(intent, str):
                raise DaemonRpcError(-32602, "intent must be a string")
            self.projections.agent_begin(actor, intent=intent)
            if self.watcher is not None:
                self.watcher.begin(actor, intent=intent)
            return {"actor": actor, "locked": True}
        if method == "agent_end":
            actor = params.get("actor") or params.get("label")
            if not isinstance(actor, str) or not actor:
                raise DaemonRpcError(-32602, "agent_end requires an actor")
            intent = params.get("intent")
            if intent is not None and not isinstance(intent, str):
                raise DaemonRpcError(-32602, "intent must be a string")
            if self.watcher is not None:
                self.watcher.end(actor)
            else:
                self.reconciler.reconcile("quiesce", actor=actor)
            self.projections.agent_end(actor, intent=intent)
            projected = self.projections.flush_pending()
            return {
                "actor": actor,
                "locked": False,
                "projected": _json_value(projected),
            }
        if method == "cells_edit":
            return self._cells_edit(params)
        if method == "cells_new":
            return self._cells_new(params)
        if method == "params_edit":
            return self._params_edit(params)
        if method == "sweep":
            return self._sweep(params)
        if method == "sweep_compare":
            return self._sweep_compare(params)
        if method == "fork":
            return self._fork(params)
        if method == "switch":
            branch = params.get("branch")
            if not isinstance(branch, str) or not branch:
                raise DaemonRpcError(-32602, "switch requires a branch")
            actor = params.get("actor")
            intent = params.get("intent")
            force = params.get("force", False)
            if actor is not None and not isinstance(actor, str):
                raise DaemonRpcError(-32602, "actor must be a string")
            if intent is not None and not isinstance(intent, str):
                raise DaemonRpcError(-32602, "intent must be a string")
            if not isinstance(force, bool):
                raise DaemonRpcError(-32602, "force must be a boolean")
            project = self._projection_requested(params)
            if project:
                try:
                    self.projections.switch(
                        branch,
                        actor=actor or "user",
                        intent=intent,
                        force=force,
                    )
                except branches.BranchNotFoundError as error:
                    raise DaemonRpcError(-32004, str(error)) from error
                except branches.WorktreeLockedError as error:
                    raise DaemonRpcError(-32009, str(error)) from error
            else:
                try:
                    branches.switch(
                        self.store,
                        branch,
                        actor=actor or "user",
                        intent=intent,
                        force=force,
                    )
                except branches.BranchNotFoundError as error:
                    raise DaemonRpcError(-32004, str(error)) from error
                except branches.WorktreeLockedError as error:
                    raise DaemonRpcError(-32009, str(error)) from error
            self.projections.refresh_generated_docs()
            return {"branch": get_branch(self.store, branch).name, "projected": project}
        if method == "rewind":
            return self._rewind(params)
        if method == "preflight":
            return self._preflight(params)
        if method == "adopt":
            return self._adopt(params)
        if method == "diff":
            return self._diff(params)
        if method == "rename":
            return self._rename(params)
        if method == "context":
            return self._context(params)
        if method == "export":
            export_branch = self._branch_param(params)
            projection = export_projection(self.store, export_branch.branch_id)
            return {
                "branch": projection.branch,
                "cells": len(projection.cells),
                "source": projection.source,
            }
        if method == "root":
            return {"root": str(self.store.flow_dir)}
        if method == "kernel_restart":
            handshake = await self.kernel.restart()
            self.envs.kernel_restarted()
            return {"restarted": True, "handshake": _json_value(handshake)}
        if method == "evict_lib":
            return {"evicted": await self.kernel.evict_lib()}
        if method == "shutdown":
            async with self._run_lock:
                return {"shutdown": True}
        raise DaemonRpcError(-32601, f"method not found: {method}")

    async def close(self) -> None:
        self._closing = True
        if self.watcher is not None:
            self.watcher.stop()
        if self._upload_task is not None:
            self._upload_wakeup.set()
            await asyncio.gather(self._upload_task, return_exceptions=True)
        await self.kernel.stop()
        self._remove_stream_listener()
        self.store.close()

    async def session_snapshot(self) -> JsonValue:
        branch = get_branch(self.store, self.store.branch_id)
        verdicts = derive_all_staleness(
            self.store,
            branch.branch_id,
            env_lock_hash=self.envs.live_lock_hash,
        )
        cells: list[dict[str, JsonValue]] = []
        for cell in self._cell_records(branch.branch_id):
            uid = str(cell["uid"])
            slug = str(cell["slug"])
            views = verdicts[uid]
            materialization_lock_hash = self._baseline_env_lock_hash(
                branch.branch_id, uid
            )
            cells.append(
                {
                    "uid": uid,
                    "slug": slug,
                    "version_id": str(cell["version_id"]),
                    "definition_hash": str(cell["definition_hash"]),
                    "source": self.store.cas.get(
                        "objects", str(cell["source_hash"])
                    ).decode("utf-8", errors="replace"),
                    "manifest": cell["manifest"],
                    "verdict": {
                        "direct": {
                            "state": views.direct.state,
                            "causes": list(views.direct.causes),
                        },
                        "transitive": {
                            "state": views.transitive.state,
                            "causes": list(views.transitive.causes),
                        },
                    },
                    "outputs": _json_value(
                        self._live_outputs(branch.branch_id, uid, cell)
                    ),
                    "logs": _json_value(
                        self._persistent_log_events(branch.branch_id, uid)
                    ),
                    "run_id": self.kernel.run_for_slug(slug),
                    "computed_under_older_env": (
                        materialization_lock_hash is not None
                        and self.envs.live_lock_hash is not None
                        and materialization_lock_hash != self.envs.live_lock_hash
                    ),
                }
            )
        first_transaction = next(self.store.journal.replay())
        first_operation = first_transaction.ops[0]
        flow_name = getattr(first_operation, "name", self.store.flow_dir.name)
        return {
            "flow_id": self.store.flow_id,
            "name": str(flow_name),
            "branch": branch.name,
            "step": self.store.last_step,
            "cells": _json_value(cells),
            "sweeps": _json_value(self._all_sweep_comparisons()),
        }

    async def asset_page(self, target: str, query: dict[str, JsonValue]) -> JsonValue:
        return await self.dispatch("asset_page", {"target": target, "query": query})

    async def edit_params(
        self, slug: str, payload: dict[str, JsonValue]
    ) -> JsonValue:
        return await self.dispatch("params_edit", {"slug": slug, **payload})

    def _live_outputs(
        self,
        branch_id: str,
        uid: str,
        cell: dict[str, JsonValue],
    ) -> list[dict[str, JsonValue]]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            """
            SELECT mats.outputs FROM baselines
            JOIN materializations AS mats USING(mat_id)
            WHERE baselines.branch_id = ? AND baselines.uid = ?
              AND mats.state = 'succeeded'
            """,
            (branch_id, uid),
        ).fetchone()
        materialized = json.loads(str(row["outputs"])) if row is not None else {}
        manifest = cell.get("manifest")
        declared = manifest.get("produces", {}) if isinstance(manifest, dict) else {}
        if not isinstance(declared, dict):
            declared = {}
        result: list[dict[str, JsonValue]] = []
        for name, declaration in declared.items():
            if not isinstance(name, str):
                continue
            output = materialized.get(name, {})
            if not isinstance(output, dict):
                output = {}
            preview_ref = output.get("preview_ref")
            preview: JsonValue = None
            if isinstance(preview_ref, str):
                try:
                    preview = _json_value(
                        json.loads(self.store.cas.get("previews", preview_ref))
                    )
                except (OSError, json.JSONDecodeError):
                    preview = None
            declared_kind = (
                declaration.get("kind")
                if isinstance(declaration, dict)
                else declaration
            )
            result.append(
                {
                    "name": name,
                    "kind": str(output.get("kind") or declared_kind or "asset"),
                    "content_hash": (
                        str(output["content_hash"])
                        if isinstance(output.get("content_hash"), str)
                        else None
                    ),
                    "preview": preview,
                }
            )
        return result

    def _persistent_log_events(
        self, branch_id: str, uid: str
    ) -> list[dict[str, JsonValue]]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            """
            SELECT mats.log_ref FROM baselines
            JOIN materializations AS mats USING(mat_id)
            WHERE baselines.branch_id = ? AND baselines.uid = ?
            """,
            (branch_id, uid),
        ).fetchone()
        if row is None or not isinstance(row["log_ref"], str):
            return []
        try:
            contents = self.store.cas.get("logs", str(row["log_ref"])).decode(
                "utf-8", errors="replace"
            )
        except OSError:
            return []
        events: list[dict[str, JsonValue]] = []
        for line in contents.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(
                    {str(key): _json_value(item) for key, item in value.items()}
                )
        return events

    def start_watcher(self) -> None:
        if self.watcher is not None:
            self.watcher.start()

    def _quiesce(self, actor: str | None) -> None:
        if self.watcher is not None:
            self.watcher.quiesce(actor=actor)

    def _projection_requested(self, params: dict[str, JsonValue]) -> bool:
        project = params.get("project", self.worktree_enabled)
        if not isinstance(project, bool):
            raise DaemonRpcError(-32602, "project must be a boolean")
        return project

    def _cells_edit(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        slug = params.get("slug")
        source = params.get("source")
        base = params.get("base_definition_hash")
        if not isinstance(slug, str) or not slug:
            raise DaemonRpcError(-32602, "cells_edit requires a slug")
        if not isinstance(source, str):
            raise DaemonRpcError(-32602, "cells_edit requires source")
        if not isinstance(base, str) or not base:
            raise DaemonRpcError(-32602, "cells_edit requires base_definition_hash")
        actor = params.get("actor")
        intent = params.get("intent")
        resolution = params.get("resolution")
        project = self._projection_requested(params)
        if actor is not None and not isinstance(actor, str):
            raise DaemonRpcError(-32602, "actor must be a string")
        if intent is not None and not isinstance(intent, str):
            raise DaemonRpcError(-32602, "intent must be a string")
        if resolution not in {None, "overwrite", "fork-my-edit"}:
            raise DaemonRpcError(-32602, "invalid edit resolution")
        try:
            result = self.projections.edit_cell(
                slug,
                source,
                base_definition_hash=base,
                actor=actor or "user",
                intent=intent,
                resolution=cast(
                    Literal["overwrite", "fork-my-edit"] | None, resolution
                ),
                project=project,
            )
        except EditConflictError as error:
            raise DaemonRpcError(
                -32009,
                str(error),
                {
                    "slug": error.slug,
                    "base_definition_hash": error.base_definition_hash,
                    "current_definition_hash": error.current_definition_hash,
                    "current_source": error.current_source,
                    "incoming_source": error.incoming_source,
                    "menu": _json_value(error.menu),
                },
            ) from error
        self.projections.refresh_generated_docs()
        return {
            "slug": result.slug,
            "definition_hash": result.definition_hash,
            "selected": result.selected,
            "flags": _json_value(result.flags),
        }

    def _cells_new(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        source = params.get("source")
        slug = params.get("slug")
        after = params.get("after")
        if slug is not None and not isinstance(slug, str):
            raise DaemonRpcError(-32602, "slug must be a string")
        if after is not None and not isinstance(after, str):
            raise DaemonRpcError(-32602, "after must be a string")
        if source is None and isinstance(slug, str):
            source = self.projections.scaffold_cell(slug, after)
        if not isinstance(source, str):
            raise DaemonRpcError(-32602, "cells_new requires source or slug")
        actor = params.get("actor")
        intent = params.get("intent")
        project = self._projection_requested(params)
        if actor is not None and not isinstance(actor, str):
            raise DaemonRpcError(-32602, "actor must be a string")
        if intent is not None and not isinstance(intent, str):
            raise DaemonRpcError(-32602, "intent must be a string")
        result = self.projections.new_cell(
            source,
            slug=slug,
            actor=actor or "user",
            intent=intent,
            project=project,
        )
        self.projections.refresh_generated_docs()
        return {
            "slug": result.accepted.slug,
            "suggested_slug": result.suggested_slug,
            "definition_hash": result.accepted.definition_hash,
            "flags": _json_value(result.accepted.flags),
        }

    def _params_edit(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        slug = params.get("slug")
        updated_params = params.get("params")
        base = params.get("base_definition_hash")
        branch = params.get("branch")
        resolution = params.get("resolution")
        if not isinstance(slug, str) or not slug:
            raise DaemonRpcError(-32602, "params_edit requires a cell name")
        if not isinstance(updated_params, dict) or not _is_json_object(updated_params):
            raise DaemonRpcError(-32602, "params must be a JSON object")
        if not isinstance(base, str) or not base:
            raise DaemonRpcError(
                -32602, "params_edit requires base_definition_hash"
            )
        if branch is not None and not isinstance(branch, str):
            raise DaemonRpcError(-32602, "branch must be a string")
        if resolution not in {None, "overwrite", "fork-my-edit"}:
            raise DaemonRpcError(-32602, "invalid edit resolution")
        actor, intent = self._mutation_metadata(params)
        try:
            result = self.projections.edit_params(
                slug,
                cast(dict[str, JsonValue], updated_params),
                base_definition_hash=base,
                branch=branch,
                actor=actor,
                intent=intent,
                resolution=cast(
                    Literal["overwrite", "fork-my-edit"] | None, resolution
                ),
            )
        except LookupError as error:
            raise DaemonRpcError(-32004, str(error)) from error
        except ParamEditConflictError as error:
            raise DaemonRpcError(
                -32009,
                str(error),
                {
                    "slug": error.slug,
                    "base_definition_hash": error.base_definition_hash,
                    "current_definition_hash": error.current_definition_hash,
                    "current_params": error.current_params,
                    "incoming_params": error.incoming_params,
                    "menu": _json_value(error.menu),
                },
            ) from error
        self.projections.refresh_generated_docs()
        selected_branch = get_branch(self.store, result.branch_id)
        return {
            "slug": result.slug,
            "branch": selected_branch.name,
            "definition_hash": result.definition_hash,
            "params": _json_value(result.params),
            "changed": result.transaction is not None,
        }

    def _sweep(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        slug = params.get("slug")
        overrides = params.get("overrides")
        group = params.get("group")
        parent_value = params.get("parent")
        prefix_value = params.get("branch_prefix")
        if not isinstance(slug, str) or not slug:
            raise DaemonRpcError(-32602, "sweep requires a cell name")
        if (
            not isinstance(overrides, list)
            or not overrides
            or any(
                not isinstance(item, dict) or not _is_json_object(item)
                for item in overrides
            )
        ):
            raise DaemonRpcError(
                -32602, "sweep overrides must be a non-empty list of JSON objects"
            )
        if group is not None and (not isinstance(group, str) or not group.strip()):
            raise DaemonRpcError(-32602, "sweep group must be a non-empty string")
        if parent_value is not None and not isinstance(parent_value, str):
            raise DaemonRpcError(-32602, "parent must be a branch name")
        if prefix_value is not None and (
            not isinstance(prefix_value, str) or not prefix_value.strip()
        ):
            raise DaemonRpcError(-32602, "branch_prefix must be a non-empty string")
        parent = get_branch(self.store, parent_value or self.store.branch_id)
        cell = next(
            (
                item
                for item in self._cell_records(parent.branch_id)
                if item["slug"] == slug
            ),
            None,
        )
        if cell is None:
            raise DaemonRpcError(-32004, f"cell not found on {parent.name}: {slug}")
        manifest = cell.get("manifest")
        base_params = manifest.get("params", {}) if isinstance(manifest, dict) else {}
        if not isinstance(base_params, dict):
            base_params = {}
        sweep_group = str(group or f"{slug}-{self.store.last_step + 1}")
        branch_prefix = str(prefix_value or f"sweep/{sweep_group}").rstrip("/")
        existing_names = {item.name for item in branches.list_branches(self.store)}
        names: list[str] = []
        for index in range(len(overrides)):
            candidate = f"{branch_prefix}/{index + 1}"
            suffix = 2
            while candidate in existing_names:
                candidate = f"{branch_prefix}/{index + 1}-{suffix}"
                suffix += 1
            existing_names.add(candidate)
            names.append(candidate)
        actor, intent = self._mutation_metadata(params)
        snapshot_step = self.store.last_step
        variants: list[dict[str, JsonValue]] = []
        for index, (name, override) in enumerate(zip(names, overrides, strict=True), 1):
            created = branches.fork(
                self.store,
                parent.branch_id,
                name,
                actor=actor,
                intent=f"{intent or f'sweep {slug}'}: fork variant {index}",
                sweep_group=sweep_group,
                fork_step=snapshot_step,
            )
            variant_params = {
                **cast(dict[str, JsonValue], base_params),
                **cast(dict[str, JsonValue], override),
            }
            edited = self.projections.edit_params(
                slug,
                variant_params,
                base_definition_hash=str(cell["definition_hash"]),
                branch=created.branch_id,
                actor=actor,
                intent=f"{intent or f'sweep {slug}'}: params variant {index}",
            )
            variants.append(
                {
                    "branch": created.name,
                    "branch_id": created.branch_id,
                    "params": _json_value(variant_params),
                    "definition_hash": edited.definition_hash,
                }
            )
        self.projections.refresh_generated_docs()
        return {
            "group": sweep_group,
            "parent": parent.name,
            "cell": slug,
            "fork_step": snapshot_step,
            "variants": _json_value(variants),
        }

    def _sweep_compare(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        group = params.get("group")
        if not isinstance(group, str) or not group:
            raise DaemonRpcError(-32602, "sweep_compare requires a group")
        variants = [
            item
            for item in branches.list_branches(self.store, include_archived=False)
            if item.sweep_group == group
        ]
        if not variants:
            raise DaemonRpcError(-32004, f"sweep group not found: {group}")
        parent = get_branch(self.store, variants[0].parent_branch_id or "")
        parent_cells = {
            str(cell["uid"]): cell for cell in self._cell_records(parent.branch_id)
        }
        compared: list[dict[str, JsonValue]] = []
        for variant in variants:
            changed_params: dict[str, JsonValue] = {}
            output_hashes: dict[str, JsonValue] = {}
            for cell in self._cell_records(variant.branch_id):
                uid = str(cell["uid"])
                manifest = cell.get("manifest")
                params_value = (
                    manifest.get("params", {})
                    if isinstance(manifest, dict)
                    else {}
                )
                parent_cell = parent_cells.get(uid)
                parent_manifest = parent_cell.get("manifest") if parent_cell else None
                parent_params = (
                    parent_manifest.get("params", {})
                    if isinstance(parent_manifest, dict)
                    else {}
                )
                if params_value != parent_params:
                    changed_params[str(cell["slug"])] = _json_value(params_value)
                outputs = self._baseline_outputs(variant.branch_id, uid)
                if isinstance(outputs, dict):
                    for output, content_hash in outputs.items():
                        output_hashes[f"{cell['slug']}.{output}"] = content_hash
            compared.append(
                {
                    "branch": variant.name,
                    "branch_id": variant.branch_id,
                    "params": changed_params,
                    "output_hashes": output_hashes,
                }
            )
        return {
            "group": group,
            "parent": parent.name,
            "fork_step": variants[0].fork_step,
            "variants": _json_value(compared),
        }

    def _all_sweep_comparisons(self) -> list[dict[str, JsonValue]]:
        groups = sorted(
            {
                branch.sweep_group
                for branch in branches.list_branches(
                    self.store, include_archived=False
                )
                if branch.sweep_group is not None
            }
        )
        return [self._sweep_compare({"group": group}) for group in groups]

    def _fork(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise DaemonRpcError(-32602, "fork requires a branch name")
        parent = params.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise DaemonRpcError(-32602, "parent must be a branch name")
        step = params.get("step")
        if step is not None and not isinstance(step, int):
            raise DaemonRpcError(-32602, "fork step must be an integer")
        actor, intent = self._mutation_metadata(params)
        try:
            created = branches.fork(
                self.store,
                parent or self.store.branch_id,
                name,
                actor=actor,
                intent=intent,
                fork_step=step,
            )
        except branches.BranchNotFoundError as error:
            raise DaemonRpcError(-32004, str(error)) from error
        except ValueError as error:
            raise DaemonRpcError(-32602, str(error)) from error
        self.projections.refresh_generated_docs()
        return {
            "branch": created.name,
            "branch_id": created.branch_id,
            "parent": get_branch(self.store, created.parent_branch_id or "").name,
            "fork_step": created.fork_step,
        }

    def _rewind(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        step = params.get("step")
        if not isinstance(step, int):
            raise DaemonRpcError(-32602, "rewind requires an integer step")
        branch = self._branch_param(params)
        actor, intent = self._mutation_metadata(params)
        try:
            transaction = branches.rewind(
                self.store,
                branch.branch_id,
                step,
                actor=actor,
                intent=intent,
            )
        except ValueError as error:
            raise DaemonRpcError(-32602, str(error)) from error
        if (
            self._projection_requested(params)
            and branch.branch_id == self.store.branch_id
        ):
            self.projections.project_slice(branch.branch_id)
        self.projections.refresh_generated_docs()
        return {"branch": branch.name, "to_step": step, "step": transaction.step}

    def _preflight(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        step = params.get("step")
        if not isinstance(step, int):
            raise DaemonRpcError(-32602, "preflight requires an integer step")
        branch = self._branch_param(params)
        try:
            result = branches.preflight(self.store, branch.branch_id, step)
        except ValueError as error:
            raise DaemonRpcError(-32602, str(error)) from error
        return {
            "branch": branch.name,
            "to_step": step,
            "recompute": _json_value(
                [
                    {"cell": slug, "cost_seconds": cost}
                    for slug, cost in result.recompute
                ]
            ),
            "irrecoverable": _json_value(result.irrecoverable),
        }

    def _adopt(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        slug = params.get("slug")
        from_branch = params.get("from_branch")
        resolution = params.get("resolution")
        if not isinstance(slug, str) or not slug:
            raise DaemonRpcError(-32602, "adopt requires a cell name")
        if not isinstance(from_branch, str) or not from_branch:
            raise DaemonRpcError(-32602, "adopt requires a source branch")
        if resolution not in {None, "incoming", "current"}:
            raise DaemonRpcError(-32602, "invalid adopt resolution")
        target = self._branch_param(params)
        try:
            source = get_branch(self.store, from_branch)
        except branches.BranchNotFoundError as error:
            raise DaemonRpcError(-32004, str(error)) from error
        incoming = next(
            (
                cell
                for cell in self._cell_records(source.branch_id)
                if cell["slug"] == slug
            ),
            None,
        )
        if incoming is None:
            raise DaemonRpcError(-32004, f"cell not found on {source.name}: {slug}")
        actor, intent = self._mutation_metadata(params)
        try:
            transaction = branches.adopt(
                self.store,
                target.branch_id,
                str(incoming["uid"]),
                str(incoming["version_id"]),
                from_branch=source.branch_id,
                actor=actor,
                intent=intent,
                resolution=cast(Literal["incoming", "current"] | None, resolution),
            )
        except branches.AdoptConflictError as error:
            raise DaemonRpcError(
                -32009,
                (
                    f"adopt conflict for {slug}: both branches edited it "
                    "since their fork point"
                ),
                {
                    "kind": "definition",
                    "cell": slug,
                    "base_definition_hash": error.base_definition,
                    "current_definition_hash": error.target_definition,
                    "incoming_definition_hash": error.incoming_definition,
                },
            ) from error
        except branches.NamespaceConflictError as error:
            raise DaemonRpcError(
                -32009,
                f"adopt conflict for {slug}: {error}",
                {
                    "kind": "namespace",
                    "cell": slug,
                    "conflicts": [
                        {
                            "slug": conflict.slug,
                            "expected_uid": conflict.expected_uid,
                            "actual_uid": conflict.actual_uid,
                        }
                        for conflict in error.conflicts
                    ],
                },
            ) from error
        if (
            transaction is not None
            and self._projection_requested(params)
            and target.branch_id == self.store.branch_id
        ):
            self.projections.project_slice(target.branch_id)
        self.projections.refresh_generated_docs()
        return {
            "cell": slug,
            "from": source.name,
            "branch": target.name,
            "adopted": transaction is not None,
        }

    def _diff(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        left_value = params.get("left")
        right_value = params.get("right")
        if not isinstance(left_value, str) or not isinstance(right_value, str):
            raise DaemonRpcError(-32602, "diff requires two branch names")
        try:
            left = get_branch(self.store, left_value)
            right = get_branch(self.store, right_value)
        except branches.BranchNotFoundError as error:
            raise DaemonRpcError(-32004, str(error)) from error
        left_cells = {
            str(cell["uid"]): cell for cell in self._cell_records(left.branch_id)
        }
        right_cells = {
            str(cell["uid"]): cell for cell in self._cell_records(right.branch_id)
        }
        rows: list[dict[str, JsonValue]] = []
        for uid in sorted(left_cells.keys() | right_cells.keys()):
            first = left_cells.get(uid)
            second = right_cells.get(uid)
            cell = first or second
            assert cell is not None
            left_outputs = (
                None if first is None else self._baseline_outputs(left.branch_id, uid)
            )
            right_outputs = (
                None if second is None else self._baseline_outputs(right.branch_id, uid)
            )
            if (
                first is None
                or second is None
                or (first["definition_hash"] != second["definition_hash"])
            ):
                divergence = "definition"
            elif left_outputs != right_outputs:
                divergence = "materialization"
            else:
                continue
            first_manifest = None if first is None else first.get("manifest")
            second_manifest = None if second is None else second.get("manifest")
            rows.append(
                {
                    "uid": uid,
                    "cell": cell["slug"],
                    "divergence": divergence,
                    "left_version": None if first is None else first["version_id"],
                    "right_version": None if second is None else second["version_id"],
                    "left_params": (
                        None
                        if not isinstance(first_manifest, dict)
                        else first_manifest.get("params", {})
                    ),
                    "right_params": (
                        None
                        if not isinstance(second_manifest, dict)
                        else second_manifest.get("params", {})
                    ),
                    "left_outputs": left_outputs,
                    "right_outputs": right_outputs,
                }
            )
        return {
            "left": left.name,
            "right": right.name,
            "differences": _json_value(rows),
        }

    def _rename(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        branch = params.get("branch")
        name = params.get("name")
        if branch is not None or name is not None:
            if not isinstance(branch, str) or not branch:
                raise DaemonRpcError(-32602, "branch rename requires a branch")
            if not isinstance(name, str) or not name.strip():
                raise DaemonRpcError(-32602, "branch rename requires a name")
            actor, intent = self._mutation_metadata(params)
            try:
                transaction = branches.rename_branch(
                    self.store,
                    branch,
                    name,
                    actor=actor,
                    intent=intent,
                )
            except branches.BranchNotFoundError as error:
                raise DaemonRpcError(-32004, str(error)) from error
            except ValueError as error:
                raise DaemonRpcError(-32602, str(error)) from error
            self.projections.refresh_generated_docs()
            return {
                "branch": branch,
                "name": branches.get_branch(self.store, branch).name,
                "step": transaction.step,
            }
        old = params.get("old")
        new = params.get("new")
        if not isinstance(old, str) or not isinstance(new, str):
            raise DaemonRpcError(-32602, "rename requires old and new cell names")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", new):
            raise DaemonRpcError(-32602, "new cell name must be lowercase snake_case")
        source = self.store.flow_dir / "cells" / f"{old}.py"
        destination = self.store.flow_dir / "cells" / f"{new}.py"
        if not source.is_file():
            raise DaemonRpcError(-32004, f"cell not found: {old}")
        if destination.exists():
            raise DaemonRpcError(-32009, f"cell already exists: {new}")
        actor, intent = self._mutation_metadata(params)
        with self.projections.operation_lock(actor=actor):
            _replace_with_retry(source, destination)
            result = self.reconciler.reconcile(
                "quiesce", actor=actor, intent=intent or f"rename {old} to {new}"
            )
        if not any(item.slug == new for item in result.accepted):
            raise DaemonRpcError(-32603, f"rename did not accept cell: {new}")
        self.projections.refresh_generated_docs()
        return {"old": old, "new": new, "rewired": True}

    def _context(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        branch = self._branch_param(params)
        cells = self._cells_list({"branch": branch.branch_id, "unsynced": True})[
            "cells"
        ]
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        failures = connection.execute(
            """
            SELECT versions.slug, mats.finished_step, mats.log_ref
            FROM materializations AS mats
            JOIN asset_versions AS versions USING(version_id)
            WHERE mats.branch_id = ? AND mats.state = 'failed'
            ORDER BY mats.rowid DESC LIMIT 5
            """,
            (branch.branch_id,),
        ).fetchall()
        recent = connection.execute(
            """
            SELECT step, actor, intent, settled FROM transactions
            WHERE branch_id = ? ORDER BY step DESC LIMIT 5
            """,
            (branch.branch_id,),
        ).fetchall()
        return {
            "branch": branch.name,
            "checkpoint": self.store.last_step,
            "unsynced": cells,
            "failures": _json_value(
                [
                    {
                        "cell": str(row["slug"]),
                        "step": row["finished_step"],
                        "traceback": self._read_log(row["log_ref"]),
                    }
                    for row in failures
                ]
            ),
            "recent": _json_value(
                [
                    {
                        "step": int(row["step"]),
                        "actor": str(row["actor"]),
                        "intent": str(row["intent"]),
                        "settled": bool(row["settled"]),
                    }
                    for row in recent
                ]
            ),
        }

    def _status(self) -> dict[str, JsonValue]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        branch = get_branch(self.store, self.store.branch_id)
        selected = int(
            connection.execute(
                "SELECT COUNT(*) FROM selections WHERE branch_id = ?",
                (branch.branch_id,),
            ).fetchone()[0]
        )
        cells = self._cell_records(branch.branch_id)
        live_lock_hash = self.envs.live_lock_hash
        verdicts = derive_all_staleness(
            self.store,
            branch.branch_id,
            env_lock_hash=live_lock_hash,
        )
        for cell in cells:
            uid = str(cell["uid"])
            views = verdicts[uid]
            cell["state"] = views.transitive.state
            cell["causes"] = _json_value(views.transitive.causes)
            if views.transitive.state == "failed":
                traceback_text = self._failure_traceback(branch.branch_id, uid)
                if traceback_text is not None:
                    cell["failure"] = {"traceback": traceback_text}
            materialization_lock_hash = self._baseline_env_lock_hash(
                branch.branch_id, uid
            )
            cell["computed_env_lock_hash"] = materialization_lock_hash
            cell["computed_under_older_env"] = (
                materialization_lock_hash is not None
                and live_lock_hash is not None
                and materialization_lock_hash != live_lock_hash
            )
        return {
            "running": True,
            "flow": self.store.flow_id,
            "branch": branch.name,
            "step": self.store.last_step,
            "cells": selected,
            "cell_status": _json_value(cells),
            "kernel": {
                "running": self.kernel.running,
                "pid": self.kernel.process.pid if self.kernel.process else None,
                "sandbox_profile": self.kernel.sandbox_profile,
            },
            "environment": self.envs.status(),
            "uploads": _json_value(
                [
                    {
                        "mat_id": item.mat_id,
                        "output": item.output,
                        "state": item.state,
                        "attempts": item.attempts,
                    }
                    for item in self.uploads.items()
                ]
            ),
        }

    def _failure_traceback(self, branch_id: str, uid: str) -> str | None:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            """
            SELECT mats.log_ref FROM baselines
            JOIN materializations AS mats USING(mat_id)
            WHERE baselines.branch_id = ? AND baselines.uid = ?
              AND mats.state = 'failed'
            """,
            (branch_id, uid),
        ).fetchone()
        return None if row is None else self._read_log(row["log_ref"])

    def _read_log(self, log_ref: object) -> str | None:
        if not isinstance(log_ref, str):
            return None
        try:
            payload = self.store.cas.get("logs", log_ref).decode(
                "utf-8", errors="replace"
            )
        except OSError:
            return None
        chunks: list[str] = []
        for line in payload.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("stream") == "stderr"
                and isinstance(event.get("bytes"), str)
            ):
                chunks.append(event["bytes"])
        traceback_text = "".join(chunks)
        return traceback_text[-4000:] or None

    def _tree(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        branch = self._branch_param(params)
        since = params.get("since")
        if since is not None and not isinstance(since, int):
            raise DaemonRpcError(-32602, "since must be an integer")
        cells = self._cell_records(branch.branch_id)
        verdicts = derive_all_staleness(
            self.store, branch.branch_id, env_lock_hash=self.envs.live_lock_hash
        )
        if since is not None:
            cells = [
                cell
                for cell in cells
                if isinstance(cell["created_step"], int)
                and cell["created_step"] > since
            ]
        for cell in cells:
            views = verdicts[str(cell["uid"])]
            cell["state"] = views.transitive.state
            cell["causes"] = _json_value(views.transitive.causes)
        branch_tree = [
            item.model_dump(mode="json") for item in branches.list_branches(self.store)
        ]
        return {
            "branch": branch.name,
            "branches": _json_value(branch_tree),
            "cells": _json_value(cells),
        }

    def _graph(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        branch = self._branch_param(params)
        around = params.get("around")
        depth = params.get("depth", 2)
        if around is not None and not isinstance(around, str):
            raise DaemonRpcError(-32602, "around must be a cell name")
        if not isinstance(depth, int) or depth < 0:
            raise DaemonRpcError(-32602, "depth must be a non-negative integer")
        cells = self._cell_records(branch.branch_id)
        by_uid = {str(cell["uid"]): cell for cell in cells}
        by_slug = {str(cell["slug"]): str(cell["uid"]) for cell in cells}
        edges: list[dict[str, JsonValue]] = []
        adjacency: dict[str, set[str]] = {uid: set() for uid in by_uid}
        for cell in cells:
            manifest = cell["manifest"]
            if not isinstance(manifest, dict):
                continue
            bound = manifest.get("bound_inputs", {})
            if not isinstance(bound, dict):
                continue
            for input_name, reference in bound.items():
                if not isinstance(reference, str) or not reference.startswith("uid:"):
                    continue
                parent, _, output = reference[4:].partition(".")
                if parent not in by_uid:
                    continue
                child = str(cell["uid"])
                adjacency[parent].add(child)
                adjacency[child].add(parent)
                edges.append(
                    {
                        "from_uid": parent,
                        "from": by_uid[parent]["slug"],
                        "output": output,
                        "to_uid": child,
                        "to": cell["slug"],
                        "input": str(input_name),
                    }
                )
        visible = set(by_uid)
        if around is not None:
            start = by_slug.get(around)
            if start is None:
                raise DaemonRpcError(-32004, f"cell not found: {around}")
            visible = {start}
            frontier = {start}
            for _ in range(depth):
                frontier = {
                    neighbor
                    for uid in frontier
                    for neighbor in adjacency[uid]
                    if neighbor not in visible
                }
                visible.update(frontier)
        nodes = [cell for cell in cells if str(cell["uid"]) in visible]
        visible_edges = [
            edge
            for edge in edges
            if str(edge["from_uid"]) in visible and str(edge["to_uid"]) in visible
        ]
        return {
            "branch": branch.name,
            "nodes": _json_value(nodes),
            "edges": _json_value(visible_edges),
        }

    def _cells_list(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        branch = self._branch_param(params)
        unsynced = params.get("unsynced", False)
        if not isinstance(unsynced, bool):
            raise DaemonRpcError(-32602, "unsynced must be a boolean")
        cells = self._cell_records(branch.branch_id)
        verdicts = derive_all_staleness(
            self.store, branch.branch_id, env_lock_hash=self.envs.live_lock_hash
        )
        result: list[dict[str, JsonValue]] = []
        for cell in cells:
            views = verdicts[str(cell["uid"])]
            if unsynced and views.transitive.state == "synced":
                continue
            cell["state"] = views.transitive.state
            cell["causes"] = _json_value(views.transitive.causes)
            result.append(cell)
        return {"branch": branch.name, "cells": _json_value(result)}

    def _cells_show(self, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        slug = params.get("slug")
        if not isinstance(slug, str) or not slug:
            raise DaemonRpcError(-32602, "cells_show requires a cell name")
        branch = self._branch_param(params)
        cell = next(
            (
                item
                for item in self._cell_records(branch.branch_id)
                if item["slug"] == slug
            ),
            None,
        )
        if cell is None:
            raise DaemonRpcError(-32004, f"cell not found: {slug}")
        source_hash = cell.get("source_hash")
        assert isinstance(source_hash, str)
        cell["source"] = self.store.cas.get("objects", source_hash).decode()
        verdict = derive_all_staleness(
            self.store, branch.branch_id, env_lock_hash=self.envs.live_lock_hash
        )[str(cell["uid"])]
        cell["state"] = verdict.transitive.state
        cell["causes"] = list(verdict.transitive.causes)
        return cell

    async def _run(
        self,
        target: str,
        branch: str | None,
        *,
        actor: str = "system:scheduler",
        intent: str | None = None,
        force: bool = False,
    ) -> dict[str, JsonValue]:
        async with self._run_lock:
            selected_branch = get_branch(self.store, branch or self.store.branch_id)
            if self.envs.branch_lock_mismatch and not force:
                raise DaemonRpcError(
                    -32012,
                    "env mismatch — restart under this branch's lock to clear",
                    {"branch": selected_branch.name, "force_available": True},
                )
            if (
                self.envs.live_lock_hash is None
                and self.envs.branch_lock_hash is None
                and self._branch_has_env_sensitive_cells(selected_branch.branch_id)
            ):
                await asyncio.to_thread(self.envs.ensure_environment)
            target_uid, target_slug = self._resolve_target(
                selected_branch.branch_id, target
            )
            current_lib_hash = compute_lib_tree_hash(self.store.flow_dir)
            current_lib_files = _lib_file_hashes(self.store.flow_dir)
            changed_lib_files = sorted(
                path
                for path in self.lib_files.keys() | current_lib_files.keys()
                if self.lib_files.get(path) != current_lib_files.get(path)
            )
            if current_lib_hash != self.lib_tree_hash:
                if self.kernel.running:
                    await self.kernel.evict_lib()
                self.lib_tree_hash = current_lib_hash
                self.lib_files = current_lib_files

            async def execute(
                node: PlanNode, inputs: dict[str, InputRecord]
            ) -> ExecutionResult:
                if self.envs.live_lock_hash is None:
                    await asyncio.to_thread(self.envs.ensure_environment)
                return await self.kernel.execute(
                    self.store,
                    node,
                    inputs,
                    branch_id=selected_branch.branch_id,
                )

            scheduler = Scheduler(
                self.store,
                execute,
                lib_tree_hash=self.lib_tree_hash,
                lib_changed_files=changed_lib_files,
                queue=self.queue,
                env_lock_hash=self.envs.live_lock_hash or self.envs.branch_lock_hash,
                env_lock_hash_provider=lambda: (
                    self.envs.live_lock_hash or self.envs.branch_lock_hash
                ),
                actor=actor,
                intent=intent,
            )
            summary = await scheduler.run(selected_branch.branch_id, target_uid)
            self.uploads.enqueue_successful(
                selected_branch.branch_id,
                summary.executed,
                actor=actor,
            )
            self._schedule_uploads()
            self.projections.refresh_generated_docs()
            return {
                "target": target_slug,
                "branch": selected_branch.name,
                "executed": list(summary.executed),
                "memo_hits": list(summary.memo_hits),
                "pruned": list(summary.pruned),
                "step": self.store.last_step,
            }

    def _baseline_env_lock_hash(self, branch_id: str, uid: str) -> str | None:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            """
            SELECT mats.env_lock_hash FROM baselines
            JOIN materializations AS mats USING(mat_id)
            WHERE baselines.branch_id = ? AND baselines.uid = ?
            """,
            (branch_id, uid),
        ).fetchone()
        if row is None or row["env_lock_hash"] is None:
            return None
        return str(row["env_lock_hash"])

    def _branch_has_env_sensitive_cells(self, branch_id: str) -> bool:
        for cell in self._cell_records(branch_id):
            manifest = cell.get("manifest")
            if isinstance(manifest, dict) and manifest.get("env_sensitive") is True:
                return True
        return False

    def _schedule_uploads(self) -> None:
        if self._closing:
            return
        if self._upload_task is None or self._upload_task.done():
            self._upload_task = asyncio.create_task(self._upload_worker())
        self._upload_wakeup.set()

    async def _upload_worker(self) -> None:
        while not self._closing:
            self._upload_wakeup.clear()
            await self.uploads.process_pending()
            if self._closing:
                return
            pending = any(
                item.state in {"queued", "failed"} for item in self.uploads.items()
            )
            if not pending:
                if self._upload_wakeup.is_set():
                    continue
                return
            try:
                await asyncio.wait_for(
                    self._upload_wakeup.wait(), timeout=_UPLOAD_RETRY_SECONDS
                )
            except TimeoutError:
                pass

    def _resolve_target(self, branch_id: str, target: str) -> tuple[str, str]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        name = target.split(".", 1)[0]
        row = connection.execute(
            """
            SELECT selections.uid, versions.slug
            FROM selections JOIN asset_versions AS versions USING(version_id)
            WHERE selections.branch_id = ?
              AND (selections.uid = ? OR versions.slug = ?)
            """,
            (branch_id, name, name),
        ).fetchone()
        if row is None:
            raise DaemonRpcError(-32004, f"cell not found: {name}")
        return str(row["uid"]), str(row["slug"])

    def _branch_param(self, params: dict[str, JsonValue]) -> Branch:
        value = params.get("branch")
        if value is not None and not isinstance(value, str):
            raise DaemonRpcError(-32602, "branch must be a string")
        try:
            return get_branch(self.store, value or self.store.branch_id)
        except branches.BranchNotFoundError as error:
            raise DaemonRpcError(-32004, str(error)) from error

    def _mutation_metadata(
        self, params: dict[str, JsonValue]
    ) -> tuple[str, str | None]:
        actor = params.get("actor", "user")
        intent = params.get("intent")
        if not isinstance(actor, str):
            raise DaemonRpcError(-32602, "actor must be a string")
        if intent is not None and not isinstance(intent, str):
            raise DaemonRpcError(-32602, "intent must be a string")
        return actor, intent

    def _cell_records(self, branch_id: str) -> list[dict[str, JsonValue]]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        rows = connection.execute(
            """
            SELECT selections.uid, selections.version_id, versions.slug,
                   versions.source_hash, versions.definition_hash,
                   versions.manifest, versions.created_step
            FROM selections
            JOIN asset_versions AS versions USING(version_id)
            WHERE selections.branch_id = ? ORDER BY versions.slug
            """,
            (branch_id,),
        ).fetchall()
        result: list[dict[str, JsonValue]] = []
        for row in rows:
            manifest = json.loads(str(row["manifest"]))
            result.append(
                {
                    "uid": str(row["uid"]),
                    "version_id": str(row["version_id"]),
                    "slug": str(row["slug"]),
                    "source_hash": str(row["source_hash"]),
                    "definition_hash": str(row["definition_hash"]),
                    "manifest": _json_value(manifest),
                    "created_step": int(row["created_step"]),
                }
            )
        return result

    def _baseline_outputs(self, branch_id: str, uid: str) -> JsonValue:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            """
            SELECT mats.outputs FROM baselines
            JOIN materializations AS mats USING(mat_id)
            WHERE baselines.branch_id = ? AND baselines.uid = ?
            """,
            (branch_id, uid),
        ).fetchone()
        if row is None:
            return None
        outputs = json.loads(str(row[0]))
        if not isinstance(outputs, dict):
            return None
        return {
            str(name): value.get("content_hash")
            for name, value in outputs.items()
            if isinstance(value, dict)
        }

    def _asset_request(self, params: dict[str, JsonValue]) -> tuple[str, str]:
        target = params.get("target")
        if not isinstance(target, str) or "." not in target:
            raise DaemonRpcError(-32602, "asset target must be slug.output")
        branch = params.get("branch")
        if branch is not None and not isinstance(branch, str):
            raise DaemonRpcError(-32602, "branch must be a string")
        return target, get_branch(self.store, branch or self.store.branch_id).branch_id

    def _resolve_output(self, branch_id: str, target: str) -> dict[str, JsonValue]:
        slug, output_name = target.split(".", 1)
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            """
            SELECT materializations.outputs
            FROM selections
            JOIN asset_versions AS versions USING(version_id)
            JOIN baselines
              ON baselines.branch_id = selections.branch_id
             AND baselines.uid = selections.uid
            JOIN materializations USING(mat_id)
            WHERE selections.branch_id = ? AND versions.slug = ?
              AND materializations.state = 'succeeded'
            """,
            (branch_id, slug),
        ).fetchone()
        if row is None:
            raise DaemonRpcError(-32004, f"asset not found: {target}")
        outputs = json.loads(str(row["outputs"]))
        output = outputs.get(output_name)
        if not isinstance(output, dict):
            raise DaemonRpcError(-32004, f"asset not found: {target}")
        return {str(key): _json_value(value) for key, value in output.items()}

    def _eval_slice(self, branch_id: str) -> dict[str, JsonValue]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        rows = connection.execute(
            """
            SELECT versions.slug, materializations.outputs
            FROM selections
            JOIN asset_versions AS versions USING(version_id)
            JOIN baselines
              ON baselines.branch_id = selections.branch_id
             AND baselines.uid = selections.uid
            JOIN materializations USING(mat_id)
            WHERE selections.branch_id = ?
              AND materializations.state = 'succeeded'
            ORDER BY versions.slug
            """,
            (branch_id,),
        ).fetchall()
        result: dict[str, JsonValue] = {}
        for row in rows:
            outputs = json.loads(str(row["outputs"]))
            if not isinstance(outputs, dict):
                continue
            slug = str(row["slug"])
            for output_name, output in outputs.items():
                if not isinstance(output_name, str) or not isinstance(output, dict):
                    continue
                value_ref = output.get("value_ref")
                content_hash = output.get("content_hash")
                kind = output.get("kind")
                if not all(
                    isinstance(value, str) for value in (value_ref, content_hash, kind)
                ):
                    continue
                result[f"{slug}.{output_name}"] = {
                    "value_ref": value_ref,
                    "content_hash": content_hash,
                    "kind": kind,
                }
        return result

    def _paranoid_mode_enabled(self) -> bool:
        contents = (self.store.flow_dir / "flow.yaml").read_text(encoding="utf-8")
        return bool(
            re.search(
                r"^\s{2}paranoid:\s*(?:true|yes|on)\s*$",
                contents,
                re.MULTILINE | re.IGNORECASE,
            )
        )


class DaemonServer:
    def __init__(self, flow_dir: str | Path, *, watch_worktree: bool = True) -> None:
        self.flow_dir = Path(flow_dir).resolve()
        self.watch_worktree = watch_worktree
        self.store_dir = self.flow_dir / ".lumlflow"
        self.socket_path = self.store_dir / "daemon.sock"
        self.port_path = self.store_dir / "daemon.port"
        self.rpc_port_path = self.store_dir / "daemon.rpc.port"
        self.token_path = self.store_dir / "daemon.token"
        self.pid_path = self.store_dir / "daemon.pid"
        self.lock = ExclusiveStoreLock(self.store_dir / "daemon.lock")
        self.runtime: DaemonRuntime | None = None
        self.stream_server: DaemonStreamServer | None = None
        self.server: asyncio.AbstractServer | None = None
        self.token: str | None = None
        self._shutdown = asyncio.Event()
        self._closed = False

    async def start(self) -> None:
        self.lock.acquire()
        try:
            self.runtime = DaemonRuntime(
                FlowStore.open(self.flow_dir), watch_worktree=self.watch_worktree
            )
            self.token = secrets.token_urlsafe(32)
            self.stream_server = DaemonStreamServer(
                self.store_dir,
                self.runtime.streams,
                self.runtime.session_snapshot,
                asset_page_provider=self.runtime.asset_page,
                param_edit_provider=self.runtime.edit_params,
                rpc_provider=self.runtime.dispatch,
                token=self.token,
            )
            await self.stream_server.start()
            if _use_tcp_transport():
                self.server = await asyncio.start_server(
                    self._handle_client, "127.0.0.1", 0
                )
                sockets: list[Any] = list(self.server.sockets or [])
                if not sockets:
                    raise RuntimeError("daemon TCP server did not bind")
                port = int(sockets[0].getsockname()[1])
                atomic_write(self.rpc_port_path, f"{port}\n".encode())
            else:
                self.socket_path.unlink(missing_ok=True)
                self.server = await asyncio.start_unix_server(
                    self._handle_client, self.socket_path
                )
            atomic_write(self.pid_path, f"{os.getpid()}\n".encode())
            self.runtime.start_watcher()
        except BaseException:
            await self.close()
            raise

    async def serve(self) -> None:
        await self.start()
        await self._shutdown.wait()
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        if self.stream_server is not None:
            await self.stream_server.close()
        if self.runtime is not None:
            await self.runtime.close()
        for path in (
            self.socket_path,
            self.rpc_port_path,
            self.pid_path,
        ):
            path.unlink(missing_ok=True)
        self.lock.release()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while line := await reader.readline():
                response, should_shutdown = await self._handle_message(line)
                writer.write(
                    json.dumps(response, separators=(",", ":")).encode() + b"\n"
                )
                await writer.drain()
                if should_shutdown:
                    self._shutdown.set()
                    break
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def _handle_message(self, line: bytes) -> tuple[dict[str, Any], bool]:
        request_id: JsonValue = None
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise DaemonRpcError(-32600, "request must be an object")
            request_id = _json_value(message.get("id"))
            if message.get("jsonrpc") != "2.0":
                raise DaemonRpcError(-32600, "jsonrpc must be '2.0'")
            if (
                _use_tcp_transport()
                and self.token is not None
                and message.get("token") != self.token
            ):
                raise DaemonRpcError(-32001, "invalid daemon token")
            method = message.get("method")
            params = message.get("params", {})
            if not isinstance(method, str) or not isinstance(params, dict):
                raise DaemonRpcError(-32600, "invalid request")
            if self.runtime is None:
                raise RuntimeError("daemon runtime is not started")
            result = await self.runtime.dispatch(method, params)
            return (
                {"jsonrpc": "2.0", "id": request_id, "result": result},
                method == "shutdown",
            )
        except json.JSONDecodeError as error:
            fault = DaemonRpcError(-32700, str(error))
        except DaemonRpcError as error:
            fault = error
        except (KeyError, TypeError, ValueError) as error:
            fault = DaemonRpcError(-32602, str(error))
        except Exception as error:
            fault = DaemonRpcError(-32603, str(error))
        body: dict[str, JsonValue] = {
            "code": fault.code,
            "message": str(fault),
        }
        if fault.data is not None:
            body["data"] = fault.data
        return (
            {"jsonrpc": "2.0", "id": request_id, "error": body},
            False,
        )


class DaemonClient:
    def __init__(self, flow_dir: str | Path, *, timeout: float = 5.0) -> None:
        self.flow_dir = Path(flow_dir).resolve()
        self.store_dir = self.flow_dir / ".lumlflow"
        self.timeout = timeout
        self._next_id = 1

    def request(
        self, method: str, params: dict[str, JsonValue] | None = None
    ) -> JsonValue:
        request_id = self._next_id
        self._next_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        client, token = self._connect()
        if token is not None:
            message["token"] = token
        with client, client.makefile("rwb", buffering=0) as file:
            file.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
            response_line = file.readline()
        if not response_line:
            raise ConnectionError("daemon closed the connection without a response")
        response = json.loads(response_line)
        if not isinstance(response, dict):
            raise ConnectionError("daemon returned an invalid response")
        error = response.get("error")
        if isinstance(error, dict):
            raise DaemonRpcError(
                int(error.get("code", -32603)),
                str(error.get("message", "daemon request failed")),
                _json_value(error.get("data")),
            )
        return _json_value(response.get("result"))

    def _connect(self) -> tuple[socket.socket, str | None]:
        if _use_tcp_transport():
            port = int((self.store_dir / "daemon.rpc.port").read_text().strip())
            token = (self.store_dir / "daemon.token").read_text().strip()
            client = socket.create_connection(("127.0.0.1", port), timeout=self.timeout)
            return client, token
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.timeout)
        client.connect(os.fspath(self.store_dir / "daemon.sock"))
        return client, None


def start_daemon(
    flow_dir: str | Path, *, watch_worktree: bool = True
) -> subprocess.Popen[bytes]:
    command = [
        sys.executable,
        "-m",
        "lumlflow.flow.daemon.main",
        "--flow-dir",
        os.fspath(Path(flow_dir).resolve()),
    ]
    if not watch_worktree:
        command.append("--headless")
    options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": Path(flow_dir).resolve(),
    }
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def connect_or_start(
    flow_dir: str | Path,
    *,
    timeout: float = 10.0,
    watch_worktree: bool = True,
) -> DaemonClient:
    client = DaemonClient(flow_dir, timeout=min(timeout, 1.0))
    try:
        client.request("handshake")
        return client
    except (ConnectionError, FileNotFoundError, OSError, ValueError):
        pass
    process = start_daemon(flow_dir, watch_worktree=watch_worktree)
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            client.request("handshake")
            return client
        except (ConnectionError, FileNotFoundError, OSError, ValueError) as error:
            last_error = error
            if process.poll() is not None:
                break
            time.sleep(0.02)
    raise RuntimeError("daemon did not become ready") from last_error


def _use_tcp_transport() -> bool:
    return os.name == "nt" or not hasattr(socket, "AF_UNIX")


def _lib_file_hashes(flow_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in flow_dir.rglob("*.py"):
        relative = path.relative_to(flow_dir)
        if relative.parts[0] in {"cells", ".lumlflow", ".venv"}:
            continue
        files[relative.as_posix()] = sha256_bytes(path.read_bytes())
    return files


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


def _is_json_object(value: dict[str, JsonValue]) -> bool:
    def valid(item: object) -> bool:
        if item is None or isinstance(item, (bool, int, str)):
            return True
        if isinstance(item, float):
            return item == item and item not in {float("inf"), float("-inf")}
        if isinstance(item, list):
            return all(valid(entry) for entry in item)
        if isinstance(item, dict):
            return all(
                isinstance(key, str) and valid(entry)
                for key, entry in item.items()
            )
        return False

    return all(isinstance(key, str) and valid(item) for key, item in value.items())
