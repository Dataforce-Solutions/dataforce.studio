# Proposals

## Problem

An audit of the lumlflow flow workbench — the `lumlflow/lumlflow/flow` daemon, `lumlflow_kernel`, and `lumlflow/frontend/src/flow` — against its brief *"reactive, agent-native and git friendly jupyter notebooks with infinite canvas + branches/lanes that can double as pipelines (structurally) and a native integration with lumlflow experiment tracker."* found:

- **Silent data loss and wrong attribution.** A cell added from the UI while an agent holds the files is deleted by the next reconcile and journaled as the agent's deletion; a deferred UI edit is superseded by an agent's `mv`; an empty-source edit is accepted and wipes the file; moving the workspace directory folds a lane's cells into `main`; a failed journal append corrupts the store.
- **The brief's one named integration does not exist.** `experiment` outputs never reach the Experiments tracker: `ctx.tracker` is an in-memory dict, the value is a JSON blob in the flow store, and declaring `experiment`/`model` silently queues *cloud* uploads and rewrites the user's lockfile. The user guide promises otherwise.
- **Reactivity is silent where it matters.** Only the checked-out lane is ever swept, while the card's "why not" verdict is computed for the viewed lane, so a stale cell on a forked lane says nothing; one failing target aborts the whole sweep; sweep failures go to stderr only.
- **New cells land in the wrong place with the wrong wiring** because the store has no notion of order and both views recompute placement from scratch.
- **Some fifty further robustness findings** across kernel link limits, the file plane, lanes, the scheduler, the daemon doors, and the frontend's live layer.
- **Not shippable**: a platform-dependent sandbox that breaks `pd.read_csv("https://…")` with no hint, zero frontend CI, undeclared/superfluous dependencies, a removed `--host`, no store version-skew handling, dev-only pages in the production bundle, no logs/diagnostics/disk reclaim.
- **Over-built against the brief**: a legacy prototype layer, fixture pages reachable by URL, a cloud upload queue, secrets, package-manager writes, safety modes, retired aliases — roughly 2,000 Python and 11,000 frontend lines that add surface without earning it.
- **Agent pairing has the right primitives and the wrong ceremony**: a pasted prompt that asks the agent to do the human's step, generated `AGENTS.md`/`CHECKOUT.md` files in the user's repository, and an ownership model (the worktree lock) that is the source of the data-loss bugs.

## Solution

One coordinated pass over the feature, in this order:

1. **Prune to the MVP** agreed for this release: remove the legacy prototype, fixture pages and the `?state=`/`?source=` switch, the sandbox and safety modes, the cloud upload queue and SDK scaffolding, secrets, package-manager writes and `env_policy`, retired aliases, `set_focus`, `asset diff`, the dev web-app shim and `CHECKOUT.md`, and shrink handoff to one gesture.
2. **Replace the ownership model**: drop the worktree lock and deferred projections. A UI edit lands on disk at once; `agent.begin`/`agent.end` remain for attribution only. This removes the two data-loss paths by construction.
3. **Fix the workspace model** to the owner's intent: one daemon per user serves every flow, addressed by its path; `lumlflow ui` is a view over the flows beneath the directory it was launched in; a flow's workspace is the directory that contains it.
4. **Fix the engine's robustness findings** in order of blast radius: the 64 KiB link limits, the silent data-loss paths, every-verb robustness, slug/download paths, lane semantics, frontend state, paging/previews, then the rest.
5. **Build the under-served pillars**: the tracker integration (the kernel writes the tracker through the SDK; experiments live only in the tracker; the flow store keeps a reference and a snapshot), a persisted order key shared by notebook and canvas, reactivity on every lane, and `lumlflow run` with no target for pipelines.
6. **Rework agent pairing**: lumlflow detects the harnesses on the machine and installs one user-level MCP entry each on consent; everything an agent needs is served (MCP `instructions`, a `lumlflow://guide` resource, `lumlflow guide`), never written into the repository.
7. **Ship-readiness**: frontend CI, correct dependencies, `--host` restored, minimal store version tolerance, dev surfaces gated, `lumlflow doctor` / rotated logs / `lumlflow gc`, the interpreter shown in the UI, and the docs made true.

**No backward compatibility.** The flow workbench has never shipped, so no store, manifest or journal written by a pre-release build needs to open, and nothing in this spec is carried for one: removed ops and fields go outright, the journal schema version is bumped once, and nothing is converted. Where a store cannot be read, the user deletes `<name>.flow/.lumlflow/` and the flow re-initialises from `cells/` and `flow.yaml` — the committed surface (D11.4, D12).

## Why this approach

- **Prune first** so no fix is spent on code that is about to go, and so the tracker design is built on a flow store with no cloud path competing for the same `experiment` word.
- **Remove the lock rather than patch it.** Patching the two deferral bugs inside reconcile would keep a mechanism whose only purpose — "the daemon must not rewrite `cells/` under an agent" — is the opposite of what a file-editing agent needs (it *should* see the user's edit). Per-cell optimistic locking (`base` → `EditConflict`) already covers the one collision that matters.
- **The kernel writes the tracker directly.** The kernel is the natural writer — it is the process holding the cell's `log_metric` calls — so a thin wrapper over the SDK's tracker, opened on the store the daemon names, is the whole integration: no proxy, no request channel, no daemon-side writer. The sandbox whose write confinement once argued for daemon-side writes goes with D1; SQLite serialises two processes on one file at this write rate (D6.6); the only cost is that a workspace venv must hold `luml-sdk`, the rule `pyarrow` already follows (D11.2).
- **One persisted order key** instead of client-side placement heuristics: heuristics fix the jump and lose it on reload; the key survives reload, rename and lanes, and lets notebook and canvas agree.
- **Sweep every lane** rather than explain why a lane is not swept: runs on a non-checked-out lane are pure store operations, so there is no reason to withhold them.

## Decisions where the alternatives were weighed

Each entry names the alternatives that were on the table and the one this spec builds, with the reason. Each is marked **[Rn]** where it lands in Design.

- **[R1]** Fix the two deferral bugs inside reconcile (a deferred add deleted by the next reconcile; a deferred edit superseded by an agent's `mv`), or drop the worktree lock and deferred projections altogether. → Drop them; both bugs vanish. Keep `agent.begin`/`agent.end` for attribution.
- **[R2]** Agent sessions stay for attribution, and the MCP entry is what carries attribution for shell agents, who edit `cells/*.py` directly — but the only thing that ever attributed a file edit to an agent was the worktree holder, which [R1] removes (`hub.quiesce` passes no actor, so today the holder gets every reconcile-detected change), while journaling under a holder that is not on the file plane is exactly the wrong attribution being fixed. → A reconcile-detected change is attributed to the verb's caller only when that caller is not `user` (an MCP session, `LUMLFLOW_ACTOR`, a harness marker, `agent exec`); otherwise — the watcher, or a verb the UI or a bare shell issued — to the one agent session registered on the flow when exactly one is, else `user`. The caller is never the tiebreak for a `user` verb: the workbench reads on every revision and every click, so "whoever quiesced first" would attribute an agent's file edit by timing (the watcher's two-second debounce) — wrong attribution again. Today's behaviour for one paired agent; `user` when nothing says otherwise.
- **[R3]** Keep the cloud upload queue with `promote` re-pointed at tracker experiments and model/dataset uploads opt-in, or defer the whole cloud path. → Deferred; no cloud path in the MVP. The four declared type words (`model`, `dataset`, `experiment`, `asset`) stay.
- **[R4]** Dropping deleted slugs from `flow.yaml` and numbering placeholders from the largest N in the manifest would reuse numbers again once the slug is dropped. → The placeholder number is one greater than the largest ever minted in the flow (all lanes, deleted included), which the store's version history already knows; the manifest index lists live slugs only.
- **[R5]** Either sweep every lane, or keep sweeping only the checked-out lane and make the card's verdict say so; the second option's "at least sweep the browser's focused lane" variant would need `session.focus`, which is pruned. → Sweep every non-archived lane; the verdict is computed for the lane it is shown on, so card and reactor always agree; no `set_focus`.
- **[R6]** The GC pin-ordering race is latent only because `gc.sweep` has no caller; wiring `lumlflow gc` to it makes it real. → The gc task must make a sweep unable to unlink bytes of a run in flight.
- **[R7]** The design gallery: DEV-only, or gone with the fixtures. → DEV-only — its import is already dynamic, the `DEV` gate is what changes (reversible; the fixture *pages* and the URL switch go).
- **[R8]** Declare `pyarrow`/`pandas` as runtime dependencies, or make `FrameKind` raise a sentence naming the missing package. → `pyarrow` becomes a runtime dependency (the fall-back-to-own-interpreter design stays); `pandas` is not (the user brings it to make a DataFrame); a workspace env without `pyarrow` fails a frame output with a sentence naming the package. Because the documented install is `uv tool install` / `pipx`, whose isolated environment holds no `pandas`, the quickstart creates a project first — `uv init`, then `pandas` and `pyarrow` added — so the D3 walk-up runs the flow on that project's venv (D11.2); "first run in an empty directory" is then a `pip install` into an environment that already holds `pandas`, not the tool install.
- **[R9]** Who writes the tracker experiment. On the table: the daemon as the writer, with the kernel talking to it over the kernel→daemon request channel (a proxy `ctx.tracker`, metric batching, named handlers dispatched off the daemon's loop, the daemon owning start/end/fail); the kernel writing the SQLite store with the stdlib against the tracker's schema; the kernel importing the SDK path-injected like `lumlflow_kernel`; or the kernel importing the SDK from the environment it runs in. → The last. `ctx.tracker` is a thin wrapper over the SDK's tracker opened on the store the daemon names, and the kernel executor owns start/end/fail (D6.2, D6.3). The channel design was over-engineering — a second writer, a batching layer and a dispatch table to carry a handful of SQLite writes; the stdlib rewrite duplicates the tracker's schema in a second place; path injection works for `lumlflow_kernel` only because it is stdlib-only, while the SDK brings pydantic, cloudpickle, fnnx, pyfnx-utils and sqlparse, which would clash with the versions a workspace venv holds. The cost is `luml-sdk` in a workspace venv, on the `pyarrow` rule (D11.2); two processes on one SQLite store is accepted (D6.6, D13). The flow subsystem keeps exactly one daemon-side write — failing the experiment of a run whose kernel died — beside the Experiments API's own writes, which stay where they are (D6.1); and because the venv's SDK and lumlflow's own now open one store — a situation the daemon-writer shape did not have — store compatibility across SDK versions is the SDK's own responsibility: lumlflow hands the kernel the version it serves and warns on a mismatch, and pins or blocks nothing (D6.6, D13).
- **[R10]** A cancelled run's experiment: fail it, delete it, or make that a setting. → Fail; no setting.
- **[R11]** The Experiments screen could refuse or warn on deleting a flow-produced experiment, and could link to the cell. → Warn, naming the flow, cell and lane; the link is not built because the confirmation is a modal there, not a navigation — that reason stands alone. The experiment's metadata does carry the flow's absolute path (D6.3): the identity fields already reach the executor, the path is D3's address for a flow, and it is what `doctor` and a support thread want to see; a link would therefore be routable, and is simply not built in this release.
- **[R12]** Today `ExperimentKind` infers by shape. → After this spec an experiment output must be what `ctx.tracker.record` returns; a plain `{params, metrics}` dict is no longer an experiment.
- **[R13]** `daemon status/stop` were to stay hidden until a `doctor` verb exists; this spec adds `doctor`. → `daemon stop` and `daemon status` come out of hiding (`daemon start` stays hidden): every failure sentence of D3, D6.5 and D11.6 sends the user to `daemon stop` — a hung daemon, or one running with a store or host a `ui` did not ask for — and a user is never sent to a verb `--help` does not show; `doctor` is the diagnostic surface and names them.
- **[R14]** Restrict daemon-side file writes for browser callers, while keeping `asset.download --to` for the CLI. → The browser gets a new authenticated HTTP route for bytes, and the HTTP door refuses the `asset.download` method outright, with or without `to` — without `to` the verb still copies `<slug>.<output>` into the daemon's working directory, which is the download-lands-in-the-workspace symptom — so a browser token holder can no longer write the daemon's filesystem at all. The RPC stays for the CLI over the socket and refuses to overwrite an existing file without `--force`.
- **[R15]** Restoring `--host` exposes the pre-existing CORS `*`, query-token-on-HTTP and unauthenticated-tracker-API weaknesses on the network. → Out of scope, pre-existing on `main`; recorded as a known limitation.
- **[R16]** Streaming bytes to the CLI client instead of the daemon-side copy was also on the table. → Not adopted: the CLI and the daemon share a filesystem, so the socket verb keeps its server-side copy, refusing to overwrite without `--force` (D4.4); streaming would be a second transport for one verb, and the browser — the caller that has no shared filesystem — gets D6.9's route instead.
- **[R17]** `lumlflow run` with no target plus a non-daemon exit path is a pipelines investment, not a bug fix. → In scope: no target runs the lane's leaves, exits non-zero on any failure, and a daemon that `run` itself started is stopped on exit — unless something else attached to it meanwhile (a leased agent session, a stream subscriber, another open flow), because under one daemon per user [R18] stopping it would pull it out from under them; then `run` leaves it running and says so in one line. The exit path belongs to `run` alone: every other verb — `agent begin` above all, whose leased session must outlive the process — leaves a daemon it started running.
- **[R18]** The intended workspace model says the launch directory is the workspace, full stop; the pairing design wants one static MCP entry that needs no workspace argument; a verb run in a subdirectory of the UI's directory must not start a second daemon over the same flows; and stale daemon records must stop deciding anything. Three shapes were weighed: one daemon per workspace root, discovered by walking up from the cwd to the nearest live record and taken over by a `lumlflow ui` launched above it, with dead records unlinked on sight (the previous design); one daemon per root with a global registry of served roots; or one daemon per user. → One daemon per user (D3). The MCP server, the verbs and the UI only ever needed two answers — *which daemon* and *which flows* — and one daemon gives both with one record and one OS lock, every flow addressed by its path; the per-root shapes needed root resolution, record walk-ups, a stand-down handshake and a bind-then-take-over ordering to give the same two answers, and carried the record-staleness and double-daemon classes of bug that one lock removes by construction. The lock is the daemon process's alone: a caller that must return — a verb, `lumlflow mcp` — spawns the daemon and attaches through the handshake rather than taking the lock itself, and whoever starts the daemon fixes its store and host for its life (D3, D13). `lumlflow ui` becomes a view: it lists the flows beneath its launch directory and serves nothing else; the "nearest ancestor holding a flow" rule goes.
- **[R19]** An *export from tracker* gesture on the experiment card: the tracker's `export` writes an archive to a path on the daemon's side — the server-side-copy problem again — and the gesture belongs beside the experiment in the Experiments screen, which owns it. → The card offers *open in Experiments* only.
- **[R20]** The order key makes notebook *move up / move down* and drag-to-reorder possible. → In scope (it is what makes the key controllable); drag-to-reorder and free canvas dragging are not.
- **[R21]** The agreed copy-context payload says *traceback if failed*; the original reason for trimming it — a secret value reaching an exception message — is moot once secrets are pruned (D1). → The trim stays, for size and noise: the payload carries the traceback's frames and the exception's final line (its type and message), never the full text, which runs to pages for a pandas or numpy error (D1, D4.11).
- **[R22]** The cross-lane projection-completion fix depends on a reconcile path that the lock removal might delete. → The path's unlocked arm ("the store beats a hand revert to a known older version") survives and is made lane-scoped.
- **[R23]** The committed `lumlflow/AGENTS.md` is a wholly generated, stale block. → Deleted with its generator.
- **[R24]** *Add downstream* pulls the experiment record into a cell that most likely only wants the model; the obvious fix is to wire only the **primary** output as `queries.primary_output` defines it — but that ranking (`queries._KIND_ORDER`, the workbench's `model/registry.ts` `PRIMARY_RANKING`) puts `experiment` first, so that fix reproduces the complaint, and after D6 it would hand every new downstream cell a tracker handle. → Downstream wiring uses the first output by the primary ranking that is **not** an `experiment`; a producer whose only output is an experiment wires that one. `primary_output` stays the *display* ranking, unchanged.
- **[R25]** A removed experiment and the refreshing state each need a push to open cards; the stream has two channels, `journal` and `logs`, `kernel` is a frame *type* on the journal channel, and every replayable journal frame's `step` feeds the client's replay cursor (`lagged` carries none). → An ephemeral **state** frame on the journal channel (D6.5): stamped with the flow's current step so the cursor is unmoved, never journaled, never replayed; a client that missed it re-derives the state on its next read.
- **[R26]** A sweep failure could be journaled as a `system` transaction or pushed as a stream frame; either way the activity feed must record it. → A `system`-actor transaction (D7): the feed is the journal, the planner reads the store, and the reason survives a restart; the reactor never arms on transactions, so there is no loop.
- **[R27]** The natural home for `order` is beside `eager`, which lives inside `settings`; this spec departs from that deliberately. → A top-level `order` map in `flow.yaml`: ordering is presentation, not a setting, and `settings` stays what `settings.set` and the brief's `settings` block serve.
- **[R28]** Shipping the churn demo with a `pyproject.toml` inside `churn.flow/` conflicts with the interpreter walk-up, which starts at the directory *containing* `<name>.flow`, so a file inside `churn.flow/` is never found and the walk from `lumlflow/churn.flow` reaches lumlflow's own `pyproject.toml`; the demo is also a repository fixture, not part of the wheel (`[tool.hatch.build.targets.wheel]` lists three packages). → The demo moves to its own directory beside its `pyproject.toml` (D11.2); "bundled" is dropped.
- **[R29]** A storage-free tiebreak — among ready cells prefer the child of the most recently emitted parent (DFS) — was considered beside the key, but on the churn demo it reorders existing cells (`prediction_diagnostics` ahead of `feature_distributions`), which breaks the *insertion, never reflow* goal. → Rejected; the key alone carries placement (D5.2).
- **[R30]** The interpreter shown in the Packages header could come from `_kernel()`, but the kernel handshake's `python` is only a version string, while the environment description `status` and the env report already carry the path and its source. → The header reads the environment description (D11.7).
- **[R31]** Read-side tolerance could be `extra="ignore"` on the models read back, but the daemon rewrites `flow.yaml` on every accept, so ignoring would strip what a newer lumlflow wrote. → Journal ops ignore unknown fields; the manifest and settings preserve unknown keys and write them back (D11.4).
- **Made moot by the cuts**, so no fix is specified: the deferred-add deletion and the deferred edit superseded by `mv` (D2); the `env_policy: auto` restart race (D1); the `AGENTS.md` merge that could eat user content (D1/D4.7); `uv` argument injection through `env.add/remove` (D1); a project `.env` switching on cloud publishing of flow outputs, and `uploads.py`'s private `luml_api._client` import (D1 removes the upload path).
- **Docs.** The decisions above make several documented claims false (the tracker promise, params editing, `--host`, the workspace paragraph, the pairing section) and the git-friendly pillar needs a *what to commit / what a clone sees* story; this spec includes the documentation fixes as one task, scoped to exactly those (D12).

Out of scope, recorded so they are not lost: the optional Compare-lite / lane-graph removal and the other over-built-but-serving candidates that have no decision yet (the preflight popover, queue coalescing / preemption / `awaiting`, the `ExpandDrawer`, the console ring buffer for late joiners, the two frontend type layers); the post-MVP items (mtime-cached workspace hash, Windows coverage, lane/branch vocabulary unification, stop-during-C-call, the two undocumented state directories, a keyboard path through the canvas, `flow.yaml`'s daemon-rewritten `cells:` index as a team merge-conflict source, `lumlflow/uv.lock` being gitignored); archive beyond D7 (an `unarchive` verb, and gating runs, edits or lane operations on `archived`); `log_model` linking a model to its experiment — and with it `ModelRenderer`, which stays reachable only from fixtures (the kernel has no `model` stored kind, a `model` being a declared type over `checkpoint`/`pickle` bytes, and the renderer's headline metric and experiment reference are exactly the linkage `log_model` would supply; D6.7 wires the experiment renderer only); scheduling of pipeline runs; per-cell free canvas positions; journaling card order; kind plugin registration in `kinds/registry.py` (deferred; left as it is). Kept as it is: the scratch REPL panel, `lumlflow eval` and the `kernel.eval` path — with no scratch-to-cell promotion; nothing in the tree claims that gesture exists, so no string needs to change.

# Design

Conventions used below: *lane* is the user-facing word, *branch* the wire word (`branch` params, `?branch=` URL); *the daemon* is `lumlflow/lumlflow/flow/daemon`; *the kernel* is `lumlflow/lumlflow_kernel`; *the workbench* is `lumlflow/frontend/src/flow/workbench`. Python tests live under `lumlflow/tests/{daemon,flow,kernel}` and use the existing helpers (`tests/daemon/helpers.py::daemon_api`, `tests/kernel/helpers.py::make_kernel/run`); frontend specs live under `lumlflow/frontend/tests/*.spec.ts` and use `tests/fakes.ts::attach/settle`. Every task ends with `ruff format --check`, `ruff check`, `mypy lumlflow/flow lumlflow_kernel lumlflow_typing` and `pytest` green in `lumlflow/`, and — for tasks touching the frontend — `vue-tsc --build`, `eslint`, `vitest run` and `vite build` green in `lumlflow/frontend`.

## D1. Scope cuts

Everything below is removed together with its tests, CLI verbs, MCP tools, API methods, journal ops, UI items and docs strings. Removed ops and fields go outright — nothing written by a pre-release build needs to open (Proposals) — and a pruned settings key needs no treatment of its own: to the new reader it is an unknown key, and D11.4's general rule applies.

| Cut | What goes | What stays |
|---|---|---|
| Legacy frontend prototype | `src/flow/{engine,types}.ts`, `src/flow/fixtures/`, `src/flow/components/`, `src/flow/composables/`, `src/flow/concepts/` (incl. `RailroadConcept.vue`), the `flow-railroad` route, `FlowShell.vue`'s fixture `Select`, `FlowTabs`' railroad entry, `tests/flow-concepts.spec.ts` | `concepts/railroad/CONCEPT.md` moves to `lumlflow/docs/` |
| Fixture pages and switch | `pages/{FixtureWorkbench,FixtureCompare}.vue`, `pages/useWorkbenchState.ts`, `live/source.ts`'s `?state=`/`?source=` arms, the fixture branches in `WorkbenchPage.vue`/`ComparePage.vue` | `workbench/fixtures/` and `workbench/gallery/` stay for the design gallery, which is registered only under `import.meta.env.DEV` — its import is already dynamic; the gate is what is new — so neither ships in a production chunk **[R7]**; the *design system gallery* block of `flow-workbench-ui.spec.ts` stays; the file's other blocks are kept or dropped with what they mount — its fixture-page cases go with this table, its *pairing hands over a prompt* block goes with the pairing cut below, when the prompt itself goes, not before |
| Sandbox | `daemon/sandbox.py`, `_resolve_sandbox` and the `sandbox-exec`/`unshare` spawn wrapping in `kernel_proc.py`, the `sandbox` field of `FlowSettings`, the `sandboxed · …` line in `render.py`, the sandbox half of `_kernel()`, `tests/daemon/test_safety.py` and every other reference | — |
| Safety modes | `paranoid` and `strict` in `FlowSettings`, their threading through `kernel_proc` → executor → REPL (`_digests`, `_assert_untouched`, `copy_of` for shared inputs, REPL `mutated()` re-hash) | the default post-run restore (`executor._restored`) |
| Cloud upload queue | `daemon/uploads.py`, `NATIVE_TYPES`, `api.promote`, `uploads.sync()` on `run`, `hub._scaffold_sdk` / `envs.ensure_sdk` / `FlowSession.declares_native`, `LumlUploader` injection in `main.py`, the `UploadStateChanged`/`UploadRecorded` ops and the `upload_queue` index rows, `OutputRecord.luml_ref`, the `uploaded` output field `queries` derives from it and the workbench badge that reads it, the UI "promote to LUML" item, the `uploaded` chips `compare/ArtifactLinks.vue` renders from `useCompare` (`ExpandDrawer` holds no cloud link; its inert `href="#"` goes in D6.7), `tests/daemon/test_uploads.py` and the 5 `ensure_sdk` tests in `test_envs.py` | the declared type vocabulary `model` / `dataset` / `experiment` / `asset`; `compare/ArtifactLinks.vue` stays in place, rendering its rows without chips, and is rewritten as tracker links in D6.8 |
| Secrets | `daemon/secrets.py`, `api.secrets_*`, `lumlflow secrets`, `ctx.secret`, the `secret_get` reverse RPC and with it the kernel→daemon request channel it rode on — nothing uses the channel once secrets are gone, the tracker being written by the kernel itself (D6.2) — `SecretRefAdded`, `Ctx.secret` in `lumlflow_typing` | the `keyring` dependency (the tracker's auth handler uses it) |
| Package-manager writes | `envs.add/remove`, `api.env_add/env_remove`, `lumlflow env add/remove`, the Packages panel's add/remove rows | `env.status`, `lumlflow env status`, the read-only Packages header (D11.7) |
| `env_policy` | the setting, `settings.set` support, `PanelSettings` control, the `auto` restart path (this also removes the `auto` restart race) | the `ask` behaviour hard-coded: the "restart kernel to apply" banner and button |
| Retired aliases | CLI `fork/switch/tree/archive`, the `variant` group, `--variant/--branch/--unsynced` options, `mcp._RETIRED_NAMES`, the wire aliases `variant`/`from_variant`/`variants` | the `daemon` group; `stop` and `status` come out of hiding with the one-daemon task **[R13]** |
| Focus, asset diff, dev shim, sidecar | `api.set_focus`, `session.focus`, MCP `session://focus`, the frontend `set_focus` reporter in `useSelection.ts`; `asset.diff` RPC and `lumlflow asset diff`; `_refresh_web_app` and its helpers in `lumlflow/cli.py`; `.lumlflow/CHECKOUT.md` (`docs.refresh_checkout`) | — |
| Handoff | the four gestures, `HandoffPopover`/`HandoffDialog`, `agent.payload`'s gesture parameter | one **copy context** per card: lane · slug · step · if failed, the traceback's frames (file, line, function) and the exception's final line — never the exception's full text (D4.11) · the cell's docstring, produced by `agent.payload` and copied to the clipboard |
| Browse-up workspace page | `WorkspacePage.vue`'s "up"/`browse()` navigation and `outside` listing, `workspace.listing/_within/_flow_crossed`, the *outside the launch directory* special case in `hub._workspace_of`, `tests/flow-workspace-browser.spec.ts` (replaced) | `hub._workspace_of` itself (it becomes *the flow's containing directory* for every flow), the refcounted `Watches` registry and per-session env scoping — D3 generalises them to every flow rather than removing them |
| Per-root daemons | the per-root daemon records under the state directory's `daemons/` and `registered_roots`, `resolve_root` (its daemon-discovery walk-up and its nearest-flow-ancestor rule alike) and the `lumlflow root` verb, `client.live_record` / `stand_down` and the record's `foreground` flag, the daemon module's and `lumlflow mcp`'s `--workspace` options and the `--workspace` sentence of `docs.CHEATSHEET`, the served-workspace record and `lumlflow-<workspace>` naming behind desktop MCP entries, and the tests that only the per-root model needed: in `tests/daemon/test_supervisor.py` a second daemon for one workspace stepping aside and a daemon deferring to a live record when the lock does not hold; in `tests/daemon/test_ui.py` two workspaces on their own ports, `ui` taking over a background server, and a server carrying a run or watched by a person keeping its workspace; in `tests/daemon/test_workspace.py` root resolution and the per-root record | one daemon per user (D3): today's auto-start and stale-record cleanup, and — new with it — one record, one OS lock held for the daemon's life and the ping handshake echoing the instance id; the supervisor tests that describe that model survive reworked to one record — a verb that finds no daemon starts one, two verbs starting at once reach one daemon, a verb waits out a briefly held lock, a second verb reuses the daemon, the lock has one holder at a time, a record whose daemon died is replaced, shutdown deregisters and a restart carries the store forward, shutdown lets go with a client or a browser still attached, a killed MCP client leaves no session |
| Pairing prompt and generated files | `daemon/connect.py`'s prompt builder, `api.agent_connect`, `connectPrompt.ts`, the `PairLink` copy block, `docs.refresh_workspace` (`AGENTS.md`), the `hub.document` calls (nine call sites, in the hub's quiesce paths and the API's verbs), `lumlflow/AGENTS.md` **[R23]**, and the *pairing hands over a prompt* block of `flow-workbench-ui.spec.ts` | `docs.CHEATSHEET` as the text behind the served guide (D9.4) |

Dependencies dropped from `pyproject.toml`: `scikit-learn`, `matplotlib`, `luml-sdk`'s use for uploads (the SDK stays for the tracker). Added: `pyarrow` **[R8]** and `tomli-w` (D9.3, D13).

## D2. Ownership: no worktree lock **[R1]**

- The daemon writes `cells/` for the checked-out lane whenever the lane's selection changes, whoever changed it: a UI edit, `cells.new`, `import`, `adopt`, `rewind`, `rename`, `delete`, `switch`. There is no holder, no deferral, no `force` needed to write.
- `agent.begin` / `agent.end` keep registering sessions for attribution and the panel line; the `worktree` flag and its `AgentBegin.worktree` field are removed. MCP no longer escalates to "take the files" on the first write.
- The *lock* meaning of `force` goes: `cells.delete`, `import`, `rename`, `rewind`, `switch` and `flow.checkout` lose the parameter, their `--force` CLI flags and MCP arguments (on those verbs it only bypassed the guard). `adopt` keeps `force` as the `AdoptConflict` resolution (D4.5) and `cells.edit` keeps it as the `EditConflict` override; on neither does it touch the file plane.
- Removed: `Worktree.guard/holder/deferred/pending`, `WorktreeLocked`, `reconcile._held_versions`, `_Pending.withheld` and its `skip/seen` plumbing, the brief's `unwritten` key and the workbench's `FlowBrief.unwritten` field, `WorktreeLockNotice.vue`, `LiveCellCard`'s `pending`/`pendingProjection` state, the "saved · not yet written to files" wording, and the guide's "agent is working in the files" troubleshooting entry.
- The optimistic lock on `cells.edit` (`base` vs head → `EditConflict`) is the only collision mechanism; the `force` on `cells.edit` that overrides a conflict stays. After this change `force` has exactly four meanings, none about the file plane: the `EditConflict` override on `cells.edit`, the `AdoptConflict` resolution on `adopt`, *overwrite an existing file* on the CLI's `asset.download` (D4.4), and *compute it again* — drop memoization — on `run`.
- `reconcile._complete_projections` keeps only its unlocked arm; that arm may complete a projection only when the older version the file matches is on the *same lane's* lineage **[R22]**. A file whose bytes match a version from another lane is an offline edit and lands as a new version on this lane.
- The same-lane completion is kept deliberately, and its trade-off is stated: with deferral gone its two cases are a projection that never landed (a crash between commit and write) and a hand revert to an older version of this lane — `git checkout -- cells/score.py`, the git-friendly gesture — and, since the daemon keeps no record of what it last projected, the bytes alone cannot tell them apart. The store wins because every version is still in it and the revert is one rewind away. So that a revert is never undone *silently*, each completion is journaled as a **cell note** (below) under the `system` actor — no version, no selection change — naming the cell and the version it restored; the activity feed shows it as one line, and the docs say that a git revert of a cell file is completed this way and that `rewind` is how to make it stick (D12).
- **Cell notes** — the one journal op this spec adds, shared by D2, D6.3 and D7. No existing op can carry it: a version flag lands lane-agnostically (a version may be selected on several lanes) and a transaction-level flag names no cell. A cell note is an op inside a lane-scoped `system` transaction, keyed to the cell's uid, carrying a note kind — *projection completed* · *refresh failed* · *experiment unclosed* — the sentence, and, where the kind has one, the version it names. The index keeps notes by (lane, uid, kind, step) so the planner, `cells.show` and the card find the latest note *of each kind* for a cell on a lane — a later *projection completed* note never masks a *refresh failed* one: the card shows the refresh-failed note while it is the active decline (D7) and a projection note only in the feed. A note changes no version and no selection, so staleness is untouched; it streams to open cards like any transaction and the activity feed shows it as one line. On the wire the op is `CellNoted`, named like its siblings; `cells.show` exposes the latest note of each kind for the cell on the viewed lane — kind, sentence, the version it names where it has one, the step and actor it was journaled under — and the card and feed read those same fields from the journal frame. The *projection completed* sentence names the cell and the restored version and says that `rewind` is how to keep the file's bytes instead. Because it is a new op type, the journal schema version constant is raised with it from 1 to 2, once: a store stamped 1 was written by a pre-release build and is refused on open with the re-initialise sentence (D11.4).
- Journaling **[R2]**: a reconcile-detected delete, edit or rename is attributed to the verb's caller only when that caller is not `user` — an MCP session, a `LUMLFLOW_ACTOR` or harness-marked shell (D9.5), an `agent exec` wrapper; otherwise, whichever door found it — the watcher, or a `user` verb such as the workbench's `cells.list` — it is attributed to the one agent session registered on the flow when exactly one is registered, else `user`. A `user` verb is never the tiebreak, because the workbench reads on every revision and every click, inside the watcher's two-second debounce, and "whoever quiesced first" would then attribute by timing. That is how a registered shell agent's direct file edits keep its name once the holder is gone; a hand edit in an external editor while one agent is registered reads as that agent's, as it does today under the holder, and `agent end` is what ends it.

## D3. Workspace model **[R18]**

- **One daemon per user.** Every verb, `lumlflow ui`, the workbench and every MCP session reach one daemon process per user, which serves every flow they open, wherever it lives on disk. It is started by `lumlflow ui` in the foreground, or in the background by the first verb or `lumlflow mcp` that finds none running — today's auto-start, with one target instead of one per directory. A daemon has no workspace root: there are no per-root records, no registry of roots and no root resolution for discovery. The only two questions anyone asks are *which daemon* — answered by one record — and *which flows* — answered by paths.
- **One record.** The daemon keeps one record in the user's state directory (`LUMLFLOW_STATE_DIR` overrides it, as today), mode 0600: its pid, a random instance id minted at start, its socket address — the loopback TCP port of the RPC door, the one transport the socket door and its client use today — its web token — the key the browser and every socket caller present, as today — its web host and port, the tracker store path it serves, and the lumlflow version. The record says where to call; the lock says whether anyone is there. The state directory should be on a local filesystem — the lock is an OS file lock, and file locks on network filesystems are unreliable: `ui` prints one warning line naming the directory and the reason when it is not, at start, and `doctor` reports it; neither refuses to run there.
- **One daemon.** The daemon holds an exclusive OS lock on one lock file in the state directory for its whole life — `flock` on Unix, `msvcrt.locking` on Windows, the mechanism `WorkspaceLock` in `daemon/workspace.py` already uses per root. The operating system releases the lock on any death of the process — `kill -9`, a crash, the OOM killer, a closed terminal, a reboot — so the lock, never the pid and never the port, is the truth about whether a daemon exists. The lock file is opened non-inheritable, a requirement: no kernel subprocess, and nothing else the daemon spawns, ever holds it, so a kernel that outlives a dead daemon leaves the lock free. Starting has two roles, because a verb or `lumlflow mcp` must return while the daemon it starts lives on: it cannot become the daemon in its own process, and a lock taken in one process cannot be handed to another. The **daemon role** belongs to the daemon process alone — `ui` runs it in-process, in the foreground; a verb or `lumlflow mcp` spawns a detached daemon process to run it, as today's auto-start does. Try the lock. Got it → this process is the daemon: it writes the record, binds its socket and its web port, and serves; a web port it cannot bind is an error naming the port and the flag that changes it, never a sign that someone else is running. Held by another → exit at once with a code meaning *someone is there*, writing nothing. Only the daemon process ever opens the lock file. The **caller role** is what every verb, `lumlflow mcp`, and `ui` before it decides run: read the record and ping the daemon over its socket; the reply must echo the record's instance id — the handshake is the proof, since pids are reused. The ping answers with that id → attach: a verb calls, `ui` opens the browser. No record, or a record whose ping fails, while the lock is free → the daemon died without cleaning up, or never ran: a stale record is unlinked, and the caller starts the daemon — `ui` becomes it in this process; a verb or `lumlflow mcp` spawns it — then waits for a record whose ping answers with a fresh instance id. A spawn that exits with the *someone is there* code means another caller's daemon won the race: the caller pings again and attaches. The ping fails while the lock is held → the daemon is starting or hung: retry for a few seconds, then fail with a sentence naming the log path and `lumlflow daemon stop` — a daemon is never replaced silently. `lumlflow daemon stop` signals the recorded pid only while the lock is held; with the lock free it unlinks the record and says that no daemon was running — pids are reused, and a stale record never points a signal at a stranger. Two callers starting at once are resolved by the lock — one daemon process takes it, the other's finds it held and exits, and both callers attach to the one that took it. On a clean stop the daemon closes its kernels and stores, unlinks its record and releases the lock last.
- **`lumlflow ui [dir]` is a view.** It opens the landing page, which lists the flows found beneath `dir` — the launch directory by default — plus *New flow*, which creates a flow in that directory. The directory is a listing filter, never a boundary: the daemon serves flows from anywhere, a flow opened by path from another directory works the same, and there is no browse-up. When a daemon is already running, `ui` prints the recorded URL, opens the browser on it (`--no-browser` only prints) and exits; it starts nothing and stays attached to nothing. When none is running, `ui` starts the daemon in this process, in the foreground, prints its URL and log path, and Ctrl-C stops it — kernels, stores, record and lock — as today; when other clients are attached at that moment — a leased agent session, a stream subscriber, a flow open from another directory — `ui` says so on one line and still stops: the user asked, and the one daemon is theirs (D13). The tracker store and the host are the running daemon's: a `ui` whose `--path` (or the environment it resolves the store from) names a different store, or whose `--host` differs from the recorded host, is refused with a sentence naming the running store and host and `lumlflow daemon stop`; restarting with other settings is the user's act, never `ui`'s. A different `--port` is not a conflict: `ui` says which port is serving and opens it. A daemon a verb or `lumlflow mcp` started runs in the background, serving every flow, until `lumlflow daemon stop` or D8's rule that `run` stops what it started; a later `ui` attaches to it exactly as above. A background daemon binds loopback and the default web port — the one `ui` would bind — and, when that port is taken, an ephemeral one, which the later `ui` then reports as the port that is serving; it resolves its tracker store by the rules `ui` uses — `BACKEND_STORE_URI` from the environment it inherited, else the default store — so a verb and a `ui` run from one shell name one store. Whoever starts the daemon — `ui` with its flags, or a verb or `lumlflow mcp` with its environment — fixes its store and host for the daemon's life (D13).
- **Flows are addressed by path.** A flow's identity to the daemon is the absolute path of its `<name>.flow` directory: the API's `flow` parameter, `brief.path`, the workbench route (`/flow/:flowId` carries the path), the compare page, the download route (D6.9) and every MCP tool address a flow by it, and the daemon opens one session per path — two same-named flows in different directories are two flows. A bare name is a convenience for the CLI and MCP: it is resolved against the flows found beneath the caller's cwd — for the MCP server, the directory it was spawned in — and an unnamed flow-scoped verb means the flow the caller is standing in, else the only flow beneath the cwd; a name matching more than one flow, or an unnamed verb with several flows beneath, is refused with a sentence naming the paths (today's `select_flow` / `_addressed` in `daemon/workspace.py`, with the root replaced by the caller's directory). `status` with no flow lists the flows beneath a directory — the caller's cwd by default, an explicit one otherwise; `init` / `flow.init` creates in a directory the same way; `gc` and `doctor` take the same directory; the MCP `status` and `init-flow` tools take it as an optional argument for a client with no meaningful cwd. Nothing walks up from the cwd to find a flow, and no listing walks a directory nobody asked for.
- **A flow's workspace is the directory that contains `<name>.flow`.** That directory is `ctx.workspace_dir`, the run's current directory (the per-run scratch directory serves only `ctx.tempdir()` and output staging), the root of the shared-code scan and of the watcher for that flow, and the place interpreter resolution starts from. Wherever this spec says *the flow's directory* it means this containing directory, never the `<name>.flow/` directory itself. The per-flow scoping `hub._workspace_of` and the `Watches` registry already give an outside flow is what every flow now gets. Nested roots (`~/proj/a.flow` and `~/proj/exp/b.flow`) are two watched roots, one inside the other; an edit under the inner root reaches both sessions, which is right — it lies inside both scan roots.
- **Interpreter resolution** walks up from the flow's directory (the containing directory, so nothing inside `<name>.flow/` is ever consulted) to the nearest directory holding `.venv` or `pyproject.toml` (the way editors and `uv` do); with none found, lumlflow's own interpreter is used and labelled as such (D11.7). `uv sync` behaviour is unchanged: an existing `.venv` is used as it is and never synced, and a `pyproject.toml` with no `.venv` beside it is synced to create one — an ancestor project the user never pointed lumlflow at included: that is the intent, the flow's project is the nearest one above it.
- **Shared-code scan exclusions**: besides the current names, prune any directory containing `pyvenv.cfg`, any directory named `site-packages`, `env`, `venv`, `.tox`, `build`, `dist`, and everything matched by a `.gitignore` in the scanned tree.
- **Worktree binding survives a move**: the binding is keyed by the flow id, not the absolute path. Opening a store that has history but no binding for its current location re-binds to the lane the last `WorktreeBound` op names — never to `main` by default — and the cold reconcile runs against that lane.
- Cells that consumed `ctx.workspace_dir` under the old model observe the same attribute; only its value changes.

## D4. Engine robustness

Each item is a behavioural contract; the named modules locate the code.

### D4.1 Link and door limits

- One kernel message or one RPC line of any size up to 16 MiB is delivered intact on the kernel link and the socket door — the two places asyncio's 64 KiB default applies today. Above that, the socket door answers `INVALID_REQUEST` with a sentence naming the limit, and the connection stays open. The HTTP door has no line limit today and none is introduced.
- A `readline` overrun on the kernel link is a protocol error that fails the run with a sentence, not a dead link: the kernel process is not declared stopped while it is alive.
- The kernel caps a single capture chunk at 32 KiB before base64 and clips a REPL result and output to 64 KiB with an explicit "… N bytes omitted" marker.
- An RPC error on the socket door never drops the connection, so a paired agent's leased session survives a large edit.

### D4.2 Editing

- `cells.edit` refuses an empty or whitespace-only `source` with a `FlowError` naming the cell; `base` is always sent by the UI.
- The workbench keeps the previous cell detail while it refetches (stale-while-revalidate); *edit* and *apply suggestion* are disabled while no detail is loaded; an edit always carries `base`.

### D4.3 Every-verb robustness

- Reconciliation never raises on an unreadable file: dangling symlinks and editor lock names (`.#*`, `._*`) are ignored by the cell glob; an undecodable cell file lands as an `invalid` version with a flag that names the encoding problem; an unreadable file elsewhere in the tree is skipped by the workspace scan.
- A journal append that fails after bytes reached disk leaves the file as it was before the append, and the next commit uses the step the journal actually ends at. The flow reopens.
- Editing shared code during a long run never makes a verb wait on the running cell: module eviction is applied before the next run instead of being queued behind the current one.
- The HTTP door answers every exception the socket door answers, in the same JSON shape with CORS headers: malformed numeric/typed params become a `FlowError` sentence (400), anything else a JSON 500 with the message; the traceback goes to the daemon's log — the file D11.6 rotates and `doctor` names — never to the `lumlflow ui` terminal.

### D4.4 Slugs and download paths

- A slug given to `cells.new`, `rename` or `import` must be non-empty, contain no path separators, `..`, control characters or a leading dot, and case-fold to a single `cells/<slug>.py` inside the flow; otherwise the verb raises a `FlowError` naming the rule (the rule `portable._cell_name` already applies). Acceptance and projection assert the resolved path is under `cells/`.
- `asset.download` is served only on the socket door, the CLI's transport (D6.9); the HTTP door refuses the method with a `FlowError` sentence whether or not `to` is given — without `to` the verb copies `<slug>.<output>` into the daemon's working directory, so refusing only the `to` form would leave a browser token holder able to write into the workspace. Over the socket it refuses to overwrite an existing file unless `--force`. The CLI resolves `--to` — or, when none is given, its own working directory — to an absolute path before sending, as it does today, and the socket verb refuses a relative `to`, so nothing ever resolves against the daemon's working directory, which after D3 is wherever the one daemon happened to be started and not the shell's.
- `rename` to a name another cell holds raises instead of landing as `<name>_2`.

### D4.5 Lane semantics

- Adopting a cell whose slug differs on the donor lane respells its consumers on the target lane by uid (the `rewire` path `rename` uses); consumers stay synced and the projected files spell the new name.
- Deleting a cell on any lane re-accepts its consumers, so they carry a `dangling_ref` flag and an unsynced cause whether or not the lane is on disk.
- A hand edit whose bytes match an older version from *another* lane is an offline edit on this lane (D2).
- `import` that renames a cell rewires its consumers; a renamed file that does not parse still recovers its uid from the text, so the rename is recorded and the old uid stays on the lane.
- A forced `adopt` over a name clash resolves the duplicate deterministically: the pre-existing cell keeps its slug, the adopted cell is suffixed, and the adopted uid is always re-accepted — regardless of ULID order.

### D4.6 Scheduler

- A stop that arrives while the kernel is starting is honoured: the run ends `cancelled`, nothing is journaled as succeeded, and no cell code runs.
- A cell edited while a plan is in flight runs from the version the lane selects when its turn comes; if the version moved, the plan is re-derived from that step or the run is reported `abandoned` — never journaled under the superseded version.
- Reverting a shared-code edit (A→B→A) leaves no cell stale: the workspace-code cause is derived from the tree hash the materialization ran under, not from steps.
- `force` never joins another lane's in-flight run.

### D4.7 File plane hygiene

- A cell whose class body sits on the header line (`class Todo: """…"""`) gets its uid line inserted without breaking the syntax; a UTF-8 BOM is accepted for parsing.
- The `AGENTS.md` merge is gone with D1; nothing under D9 writes into the repository.

### D4.8 Daemon

- The MCP server addresses every call after `flow.open` by the path the open resolved — D3's general rule, applied to a session that remembers its flows — so two same-named flows in different directories both work in one session.

### D4.9 Rendering and paging

- `asset.page` rows go through the same cell-normalisation the preview uses (non-finite floats → null, non-JSON objects → repr) without the preview's 120-character clip; a page response never fails serialisation after the handler returned — a serialisation failure is an error reply, not a 30 s timeout. Pages honour the same column bound as previews and carry `total_columns`; the frame footer shows both row and column totals and marks truncation.
- Preview shrinking has a per-block strategy: images are re-encoded smaller, text is clipped with a marker, key-value blocks keep their first N entries; a single over-sized block no longer collapses the whole preview to "too large to show".
- Console and logs are rendered with ANSI escapes stripped and `\r` applied (a progress bar is one line); the live console buffer is bounded and appends in constant time per frame.
- Non-finite metrics render as `nan`/`inf`, distinct from a missing value: the preview envelope is JSON and the HTTP door refuses non-finite numbers, so a non-finite metric value travels in previews as the string `"nan"`, `"inf"` or `"-inf"` and the renderers show it as such (frame cells keep the `null` of the first bullet — a table cell is not a metric); a non-zero value whose magnitude is below `1e-3` renders in scientific notation with two significant digits instead of `0.000`; drawer paging with no page in hand starts at row 0.
- A frame is deserialised in the flavor it was serialised in: the flavor rides in the Arrow schema metadata, so a polars output reaches its consumer as a polars frame even with pandas installed.

### D4.10 Frontend state

- Checking out or rewinding a lane updates the session brief from the verb's reply, so the switcher, identifier, paired-agent line and URL agree with the tree (there is no force-checkout after D2).
- The brief that `flow.open` and `status` return carries the store's `flow_id` (today it is visible to a client only on the replayed `FlowInit` op, which a cursor ahead of a re-created journal never receives); the workbench's brief type gains it, and the cursor reset of D4.11 compares it with the id the cursor was recorded under.
- The compare page addresses the flow by `brief.path`.
- The daemon token never re-enters the address bar: it is excluded from the query keys the selection mirror copies back.
- The "agent session ended · N stale assets" banner counts only `agent_end` transactions newer than the cell's own last change.
- A reconnect after a drop re-arms the first-load toast guard, so a replayed window produces no toast storm.
- A successful socket `open` marks the daemon reachable.
- An open source editor is never unmounted by a run starting: the running tab switch does not fire while a draft is open (or the editor stays mounted).
- "Save to a new lane" opens the lane-name dialog prefilled with `<slug>-edit`; if the edit fails after the fork, the new lane is still shown and the draft is kept.
- Clicking a control on an unselected card selects it without scrolling or panning mid-gesture (the popover stays anchored); the URL mirror rewrites only when the selection actually changes, never on a press on the selected card, and — `set_focus` being gone (D1) — a press reports nothing to the daemon.

### D4.11 Low sweep

- The note renderer forbids `style`, `form`, `input`, `button` and remote images.
- Export/import does not mint a spurious version for a file that ends in zero or two newlines; when `flow.open` returns a `flow_id` different from the one a cursor was recorded under, both the in-memory high-water mark and the persisted catch-up marker for that flow reset to zero; the copy-context payload (D1) carries the traceback's frames and the exception's final line, not the exception's full text — a size and noise rule now that secrets are gone.

## D5. Cell creation

### D5.1 Order key

- `flow.yaml` gains a top-level `order` map, uid → key **[R27]**. Keys are decimal numbers in the same domain as journal steps — an unmapped cell's creation step is a whole number in it — so a mapped key and a creation step compare directly. A new key is the midpoint between its two neighbours' effective keys; when there is no larger neighbour, the midpoint between the anchor's effective key and the flow's next journal step — so a cell created after the map was last written always orders after every existing effective key, mapped or not. There is no renumbering: keys are written with whatever digits the midpoint needs and never rounded, so a midpoint between two distinct keys always exists and no existing entry is ever rewritten by an add or a move; unmapped cells' creation steps are therefore never disturbed. The map is not part of any version (a reorder never changes a `definition_hash`), not journaled, and committed with the flow like the settings. An entry for a uid no lane selects is dropped on the next manifest write; an entry whose key does not parse as a number, or that duplicates another effective key, is ignored deterministically and that cell falls back to its creation step — a hand-edited map never fails `open`.
- **Effective key** of a cell: its `order` entry if present, else its creation step. A flow with no map — every flow until its first anchored add or move — therefore orders by creation step, as today.
- `cells.new` takes an optional `anchor` — a slug, resolved on the lane the add lands on; a cell that lane does not select (one that lives only on another lane) is an unknown anchor; `after` implies `anchor = after`. The new cell's key is strictly between the anchor's effective key and the next larger effective key on the flow; with no anchor no entry is written — the cell's creation step is already larger than every existing effective key, so it orders last — and the map first appears on the first anchored add or move. An `anchor` that names no cell on the flow raises a `FlowError` naming it. `duplicate` anchors on the original. The UI passes the selected cell as the anchor when *add a cell* is used with a selection.
- New verb `cells.reorder` (and `lumlflow cells move --before/--after`; MCP `move-cell`): takes the cell's slug, the lane, and one of `before` / `after` naming the neighbour, and moves the cell's key next to that neighbour's. It is refused with a sentence when the requested position would leave any cell on that lane before one of its producers — the moved cell before something it consumes, or a consumer of the moved cell before it (topology wins over placement), and with a sentence naming the cell when either cell is not selected on the lane it is called on. The refusal is checked against the wiring of the lane the verb is called on; the key itself is flow-wide, and on every other lane the notebook's topological pick (D5.2) is the invariant, so a key that is illegal there is silently overridden at render time, never an error. Archive is cosmetic for a reorder as it is for an edit (D7).
- **A move is seen everywhere.** The map is not journaled, and the workbench refetches a slice only when the journal's revision moves, so without more a move would change nothing on screen in any tab — the issuing one included. So the verb's reply carries the cell's new `order`, which the issuing tab applies at once, and the daemon pushes a state frame (`order_changed`, the D6.5 mechanism, naming the flow) on which every open tab refetches its slice and the canvas re-places the moved uid. An anchored `cells.new` needs no frame: its transaction already moves the revision.
- The key is dropped from the map when no lane selects the uid any more (same rule as the slug index, D5.4) and is not restored when a `rewind` re-selects the uid — the cell falls back to its creation step. Rename keeps it (uid-keyed).
- `cells.list`/`cells.show` return the effective key as `order` beside `created_step`.

### D5.2 Notebook order

The notebook keeps its one-at-a-time topological pick, with priority = effective key instead of mint step. Topology still wins (a child never precedes a parent); within what topology allows, the user's placement wins. Adding a cell downstream of `eda` in the churn demo yields `load_data > eda > untitled_1 > split > …`. Existing cells keep their relative order: insertion, never reflow — which is why a DFS tiebreak is not adopted **[R29]**.

The card menu offers **move up** and **move down**, only when the neighbouring slot is topologically legal; each calls `cells.reorder`.

### D5.3 Canvas layout

- Columns are top-aligned, not centred; adding a node shifts only the nodes below it in its own column.
- Within a column, rows sort by (barycenter of parents, effective key). A cell with no parents is placed in the column of, and directly below, the nearest cell that precedes it in order, and takes that cell's barycenter for the row sort; with none, the root column. Notes therefore sit where they were added, map or no map: with no map a parentless cell sits under the cell preceding it in creation order, not in the root column.
- Layout is incremental: positions are kept per session by uid; a new uid is placed by the rule above without moving existing nodes; the full layout is recomputed only on an explicit **tidy** control on the canvas or when an existing cell's wiring changes.
- Viewport: on a new selection the view pans only if the node is off-screen and never zooms out; `fitView` runs only on first load. Edge ids include the input name so two references to one producer are two edges.

### D5.4 Wiring and index hygiene

- *Add cell downstream* wires exactly one output of the producer: the first by the primary ranking (`queries._KIND_ORDER` / the workbench's `model/registry.ts` `PRIMARY_RANKING`) that is **not** an `experiment`; a producer whose only output is an experiment wires that one **[R24]**. This is deliberately not `primary_output`, which ranks `experiment` first and stays the display ranking — a training cell producing `model` and `run: experiment` wires `model`. `cells.new` accepts the literal `all` for `outputs` (CLI `--all-outputs`, MCP `all_outputs`) for the old behaviour. The duplicate toast says the copy keeps the original's inputs.
- Deleting a cell drops its slug from `flow.yaml`'s `cells:` index when no lane selects the uid any more; whatever brings the uid back onto a lane — `rewind` above all, which today selects without accepting, so the accept-time index write never sees it — re-adds its slug; the committed `churn.flow/flow.yaml` loses its five `untitled_N` ghosts.
- Placeholder slugs never repeat within a flow **[R4]**: `untitled_N` uses one more than the largest N ever assigned, on any lane, deleted or not.

## D6. Tracker integration

### D6.1 Decisions

- An `experiment` output **exists only in the Experiments tracker**. The flow store holds a *reference* to it plus a *snapshot* for kernel-free browsing; there is no experiment-as-a-file and no download of one.
- `model` outputs stay stored values in the flow's CAS (pickle bytes today) with the download route of D6.9. Linking a model to its experiment is out of scope.
- A removed or unreachable experiment is a rendered, repairable state, never an error that breaks a card, a lane or the compare view.
- The kernel is the tracker's writer: `ctx.tracker` wraps the SDK's `ExperimentTracker`, opened on the store the daemon names, and the kernel executor owns the experiment's lifecycle (D6.2, D6.3). The daemon reads the tracker — dangling-state detection, the `tracker` field on cells and previews, the delete hook (D6.5) — and the flow subsystem writes it from the daemon in exactly one case: failing the experiment of a run whose kernel died (D6.3). The Experiments API's own writes — delete, update, annotations, groups, models — run in the daemon process as they do today and keep doing so, through the provider below. Two processes on one SQLite store is accepted (D6.6).
- The daemon's read side and the Experiments handlers reach the tracker through one shared provider rather than the process-wide cached singleton directly: one provider, one in-process *experiment deleted* hook on it (D6.5), and one store path — the path the provider serves is the path the daemon hands the kernel — so that a test-time binding of the provider to a temporary store points the kernel's writes, the daemon's reads and the Experiments API at that store together, and no daemon test that runs an `experiment` cell or deletes through the Experiments API can reach the developer's real store. The first tracker task owns all of it; how the handler singletons and the test fixtures resolve through it is that task's concern.

### D6.2 `ctx.tracker` in the kernel

- `ctx.tracker` is a thin wrapper over the SDK's `luml.experiments.ExperimentTracker`, opened by the kernel on the tracker store the daemon names: the store path behind `BACKEND_STORE_URI`, handed to the kernel in the spawn environment or in the run payload — implementer's choice, but one path, the one the daemon serves (D6.6) — and, beside it, the version of `luml-sdk` the daemon itself imports, which the wrapper compares with the SDK it imported before its first write, to warn on a mismatch (D6.6). The wrapper translates the cell-facing calls below into the tracker's own vocabulary — the tracker has no params/metrics vocabulary of its own: one static value per `log_static` call, one dynamic value at a step per `log_dynamic` call — one write per logged value, in the order logged. There is no batching, no proxy and no request channel: the kernel writes the store directly, and the kernel→daemon channel that once served `secret_get` goes with secrets (D1).
- The SDK is imported lazily, inside the run and only when the run declares *or consumes* an `experiment` output — a consumer's handle reads through it (D6.4); the kernel's rule of no non-stdlib module-level import stands, and a run that neither declares nor consumes an experiment never imports it. On lumlflow's own interpreter the import succeeds by construction — `luml-sdk` is a lumlflow dependency. In a workspace venv the user must have installed `luml-sdk`; where the import fails, a run declaring or consuming an `experiment` output fails before the cell's code executes with a sentence naming the package to install into that env — the rule D11.2 already applies to `pyarrow`, and nothing is installed on the user's behalf. The SDK cannot be path-injected the way `lumlflow_kernel` is: injection works for the kernel because it is stdlib-only, whereas the SDK brings its own dependencies — pydantic, cloudpickle, fnnx, pyfnx-utils, sqlparse — which would clash with whatever versions the venv already holds.
- **What a cell calls** is the surface it calls today, source-compatible with the demo's `evaluate.py` (`examples/churn/churn.flow/cells/evaluate.py` after D11.2): `log_param`, `log_params`, `log_metric`, `log_metrics` and the `record` property. The two metric methods gain an optional step, which is what the Experiments tab's step curves are drawn from; the current call shapes keep working unchanged. The snapshot keeps the latest value per metric; the tracker keeps the history.
- `ctx.tracker.record` (kept as a property, as the churn demo uses it) returns an **`ExperimentRef`**: `experiment_id`, `group` (the group *name* the experiment was started under — the tracker resolves or creates the group by name), `store` (the tracker store path the daemon named and the kernel wrote), and a `snapshot` of what this run logged (`params`, latest value per metric). The kernel keeps the snapshot from its own logged calls; it does not read it back from the tracker. The snapshot's params start from the cell's declared `params` — the same set the executor logs as static params (D6.3) — so the card's preview, the `content_hash` and the Experiments screen agree on the params.
- `ctx.tracker` is available only when the cell declares exactly one `experiment` output; using it otherwise raises a sentence naming the requirement; declaring more than one fails the run with a sentence **[R12]** — checked when the run is planned, before any tracker experiment is started, so a refused cell leaves nothing in the tracker.
- `lumlflow_typing.Ctx` gains `tracker` (and `tempdir()` is typed as returning a `Path`, matching the implementation).

### D6.3 Lifecycle, owned by the kernel executor

- For a run of a version that declares an `experiment` output, the kernel executor starts a tracker experiment before it calls `materialize`: `name = <slug>`, `group = <flow name>`, `tags = [<lane>, <slug>]`, metadata `lumlflow: {flow, flow_id, path, slug, uid, lane, version_id, run_id}` — `path` the absolute path of the `<name>.flow` directory, the address D3 gives a flow, there for `doctor` and support; a flow that moves leaves its old path in older experiments, and `flow_id` stays the identity **[R11]**. The kernel knows none of those identity fields by itself, so the daemon hands them to it in the run payload — the same fields the `ExperimentRef` names. The cell's declared `params` are logged as static params before the cell runs; `ctx.tracker.log_params` adds to them. The group is the flow's *name*, so two flows with one name in different directories (which D4.8 and D6.9 address by path) share a group; accepted as cosmetic — the metadata's `flow_id` tells them apart, and a group is a browsing convenience, not an identity.
- Outcome, applied by the executor on its way out of the run: `succeeded` ends the experiment — the tracker's `completed` status; `failed` and `cancelled` fail it — its `error` status **[R10]**, the cancel path taking the same arm. Those two are the tracker's only terminal states, and *ended* / *failed* below mean them. A run whose kernel dies mid-run cannot close its own experiment: when the daemon records that run as failed it fails the orphaned experiment — whose id it holds on the run record from the moment the kernel reported the start (below) — on the tracker it already holds open through the D6.1 provider: **the flow subsystem's one daemon-side tracker write**; the Experiments API keeps its own writes through the same provider. Either way a run that dies leaves an `error` experiment, never a running one.
- The output's value is the `ExperimentRef`. `ExperimentKind` serializes only refs (a value that is not the ref fails the run with a sentence naming `ctx.tracker.record`), renders the snapshot as the preview, and implements `content_hash` over the **snapshot** (params + final metrics), not the id, so a rerun that recorded identical numbers still cuts off downstream.
- The kernel reports the `experiment_id` and `store` as soon as the experiment is started, before the cell's code runs — on the run's `started` event, which today carries only the run id and slug, or on an event of its own right after it — and repeats them in its `materialized` and `failed` events. The daemon puts them on the run record the moment that first report arrives; a kernel that dies afterwards emits nothing more, and that start-time record is what the orphan-fail path above reads. On success the daemon also records them on the `OutputRecord` (`tracker_ref`) through `RunRecorded`, so `queries` can report it without opening the value — and, because a failed or cancelled run records no output, the run record keeps them for every outcome, so `cells.show`'s view of a failed run and the failed card's logs tab can still name the experiment.
- A memo hit reuses the materialization it hit and therefore its experiment reference; it creates no experiment.
- **What a failure does.** A start that fails — the SDK missing from the env (D6.2), the store unwritable, a read-only `--path`, a lock held past the busy timeout (D6.6), a store schema the venv's SDK refuses to open (D6.6) — fails the run before the cell's code executes, with a sentence naming the store path (or the package to install), and where the SDK itself refused, its own sentence with the venv's SDK version beside the path; a log call that fails fails the run with the same kind of sentence at that call — a cell never proceeds untracked while claiming an experiment. A failure to close an experiment after a run that otherwise succeeded leaves the materialization standing: the kernel reports it in its `materialized` event, and the daemon records it as a cell note (D2) of kind *experiment unclosed*, carrying the sentence, so the card, `cells.show` and the activity feed agree on it. Tracker writes never touch the daemon's event loop because the daemon does not make them; its reads are the cached lookups of D6.5.

### D6.4 Consumers

A cell consuming an `experiment` output receives a read-only `Experiment` handle: `id`, `params`, `metrics`, `metric_history(name)`, hydrated by the kernel at access time through the SDK tracker's read calls on the same store — no channel involved. The consumer imports the SDK the same lazy way a producer does (D6.2): a consumer in a workspace venv without `luml-sdk` fails before its code executes with the same sentence naming the package. Reading it observes nothing (no `identity`/`external` mark). If the experiment is missing or unreachable at access time, the access raises a sentence naming the state, and the run fails with it. In the normal path D6.5's demanded-producer rule makes this unreachable — running the consumer reruns the producer first and hands the consumer a live reference; this failure is what a consumer sees only when the producer is deliberately not rerun or its rerun itself failed.

### D6.5 Dangling references

| State | Detected by | Card / drawer | Scheduling |
|---|---|---|---|
| `ok` | the served tracker returns the experiment | live experiment renderer, *open in Experiments* | — |
| `missing` | `ref.store` is the served store and the tracker returns nothing | snapshot kept and greyed, badge *experiment removed from the tracker*, link disabled, one line: *the numbers below are what it recorded at step N. run `<slug>` to record it again.* | treated like missing bytes: an explicit run of any consumer pulls the producer in (the planner's demanded-producer rule extended to a dangling `tracker_ref`), and the preflight names why. Reactivity never reruns it — the deletion was the user's act: the verdict declines any `auto` target whose closure would demand the producer, with a reason naming the removed experiment (D7), so the reactor submits neither the producer nor the consumer. |
| `unreachable` | `ref.store` differs from the served store, or the tracker raises — a read that still fails past the busy timeout, and a store schema the daemon's SDK cannot read (D6.6), included | same rendering; for an unreadable store the line names the store and, when known, the SDK version that wrote it, and suggests upgrading lumlflow; otherwise the line: *recorded in a different tracker store (`<path>`). stop the daemon (`lumlflow daemon stop`) and start `lumlflow ui --path` with that store, or run the cell again here.* | same as `missing`, with that wording in the preflight |

- Detection is one indexed lookup per experiment output, cached per session and invalidated in-process: the Experiments delete handler runs in the daemon process, and the tracker provider (D6.1) exposes an in-process *experiment deleted* hook the hub subscribes to — the handler stays ignorant of flows — on which the hub drops the cache entry and pushes an ephemeral **state frame** (`experiment_removed`) that updates open cards live; nothing is journaled (the flow did not change). A delete that did not pass through this process (the SDK from another process, a store swapped under a running daemon) is still caught: the cache is dropped on `flow.open` and on a socket reconnect, and an entry older than a bounded age — one module constant, on the order of seconds — is re-checked on its next look.
- **State frames** **[R25]**: the mechanism this bullet, D5.1 and D7 share. They ride the existing journal channel (the one that already carries the kernel's run lifecycle beside transactions) as their own frame type — `state` — carrying the state's name (`experiment_removed`, `refreshing`, `order_changed`), the flow, the lane and cell it concerns where it concerns one, and the step it was stamped at: the flow's current step, so a client's replay cursor is unmoved; they are never journaled and never replayed. A client that was disconnected when one fired re-derives the state on its next `cells.list` / `asset.preview` — the frame is latency, never truth. With no client connected the frame is simply dropped.
- Nothing in the flow store is rewritten when an experiment disappears; history, rewind and compare keep working. Compare keys on content hashes, which come from the snapshot, so a removed experiment still compares; its column carries the same badge.
- The Experiments screen's delete confirmation names the producing flow, cell and lane when the experiment carries `lumlflow` metadata **[R11]**. That confirmation is built in `lumlflow/frontend/src/confirm/confirm.ts` and raised by the experiment edit and buttons components under `src/components/experiments/experiment/` — inside `lumlflow/frontend`, so its spec lands in `lumlflow/frontend/tests` under D11.1's job. The tracker's HTTP API serves no experiment metadata today (the SDK reads it), so the metadata reaches the screen either on the experiment payload it already loads or through a metadata read the tracker API gains for it.
- A failed run's experiment stays linked from the failed card's logs tab.

### D6.6 Two processes, one store

The kernel writes the tracker store and the daemon reads it (and fails an orphaned experiment, D6.3): two processes on one store's SQLite files — the store is a directory holding `meta.db` and one `exp.db` per experiment, opened in WAL mode — which SQLite serialises with its own locking — accepted at this write rate (D13). The contract: neither side sets a busy timeout of its own — the SDK opens its connections with `sqlite3`'s default five-second wait, and that wait is the busy timeout this spec means; above it, a `database is locked` that outlasts the wait is retried a bounded number of times, the bound one module constant, owned by the kernel wrapper for writes and by the daemon's tracker provider for reads; a kernel write that still fails fails the run with a sentence naming the store path (D6.3); a daemon read that still fails degrades to the `unreachable` state of D6.5 — the card renders, the lane and the compare view stand — never an error. The store the two share is one path: the one the daemon serves for the Experiments tab, named to the kernel at spawn or in the run payload (D6.2), so a test that points the daemon's provider at a temporary store points the kernel there too (D6.1).

**Version skew.** The kernel writes through whichever `luml-sdk` the workspace venv holds — Jupyter-style, the environment's own — and the daemon reads through lumlflow's own; the SDK migrates a store's schema when it opens it and refuses one it does not know, so a newer SDK in a venv can migrate `meta.db` and the experiment files forward under the running daemon. Store compatibility across SDK versions is the SDK's own responsibility: lumlflow pins nothing and blocks nothing on it — it validates and warns. The daemon hands the kernel, beside the store path, the version of the SDK it imports (D6.2); before its first tracker write the wrapper compares it with the version it imported and, when they differ, emits a warning naming both versions and the venv — into the run's console and logs, and reported on the run's events so the daemon keeps it on the run record and the card shows it as one warning line — and the run proceeds. A write the SDK then refuses is a failure like any other (D6.3): the run fails with the SDK's own sentence, the store path and the venv's SDK version beside it — a failed write cannot be warned away. On the daemon's side a store its SDK cannot read — migrated forward by a newer SDK in a venv, say — degrades to the `unreachable` state of D6.5 with a sentence naming the store and, when the store records it, the version that wrote it, and suggesting upgrading lumlflow; the daemon reports, never blocks (D13).

### D6.7 Surfaces

- `cells.list` / `cells.show` / `asset.preview` return `tracker: {id, group, state, url, store}` for experiment outputs; `url` is a path the SPA can navigate to (its experiment route is `experiments/:groupId/:experimentId`) and is null unless `state` is `ok` — the daemon derives it from the tracker record's group id in the same cached lookup that yields `state`, since the ref's `group` is a name, not the id — and `store` is what the `unreachable` line prints.
- `previewFrom` yields an `experiment` preview for stored kind `experiment` so `ExperimentRenderer` renders live data: run name, headline metric, params, and the tracker link when `state` is `ok`; the inert `href="#"` in `ExpandDrawer` and the hard-coded `/experiments` in `ExperimentRenderer` go. The headline metric is the first metric in the snapshot — the first the cell logged — and, the snapshot carrying no direction, it is shown without a higher-/lower-is-better arrow; the other metrics follow as rows. `ModelRenderer` is not wired (see the out-of-scope list: it draws on the `log_model` linkage); a `model` output keeps rendering through its stored kind's blocks.
- The left panel's existing **experiments** lens (today rows built from the declared kinds) is re-fed from the `tracker` field and gains state badges, listing the tracker experiments the viewed lane produced: what the lane's selected materializations reference, so a memo hit's experiment is listed on the hitting lane too, carrying the tag of the lane that recorded it.
- The experiment card has no download/export control **[R19]**.

### D6.8 Compare links

`compare/ArtifactLinks.vue` becomes a tracker-links section: for each compared lane, the experiment its cells produced, linked when `ok`, badged otherwise. `useCompare` fills it from the `tracker` field above.

### D6.9 Asset download

- New HTTP route in `daemon/web.py`, authenticated by the same token (query parameter, as the WebSocket already does). The flow is addressed by its path — what `brief.path` holds, as every other workbench read does — and, because a path holds slashes, it travels as a query parameter beside the token together with the branch and `<slug>.<output>`; a bare flow name is not accepted. Failures: a missing or wrong token answers 401; a bare flow name answers 400 with a sentence naming the path rule — addressed by path, a flow is never ambiguous; an unknown path, a lane the flow does not have, or an output whose value is not stored, answers 404 with the same sentence the RPC raises. It streams the stored bytes with `Content-Disposition: attachment` and a filename `<slug>.<output>.<ext>` where the extension follows the kind: `frame → .arrow`, `metric`/`eval` → `.json`, `plot` → `.png` or `.json` by content, `note → .md`, `checkpoint`/`pickle` → `.pkl`, `file` → the original name, which the kernel records on the output record through `RunRecorded` (today only the preview block carries it; a record without one falls back to `<slug>.<output>`). Experiment outputs are not downloadable (404 with a sentence).
- The workbench downloads through that route (`<a download>` or the blob pattern `LiveCompare.saveFile` uses); the *saved to `<path>`* wording goes; `FileRenderer`'s inert link downloads.
- `asset.download` remains a CLI verb over the socket; the HTTP door refuses the method outright, with or without `to` (D4.4).

### D6.10 Docs strings in code

The served guide (D9.4) and the MCP `instructions` say that `ctx.tracker` records to the Experiments tracker and that `record` returns a reference, not the numbers.

## D7. Reactivity

- The reactor sweeps **every non-archived lane** that has auto targets, not only the checked-out one; runs on other lanes are pure store operations. The verdict a card shows is computed for the lane it is shown on, so card and reactor always agree **[R5]**. Archived lanes are skipped — the flag's first and only reader. Archive otherwise stays what it is today: cosmetic for runs, edits, reorders, checkout, fork and adopt, and one-way in this release (no `unarchive`; see the out-of-scope list).
- Each target is submitted under its own guard: a target the queue cannot bring to the cell's own execution — planning, input resolution, kernel start — is recorded as *could not refresh: `<sentence>`* for that (lane, cell) and the sweep continues with the next target. A cell whose own code fails is an ordinary `failed` materialization, not a refresh failure. The record is a cell note (D2) of kind *refresh failed* under the `system` actor **[R26]**, lane-scoped and keyed to the cell's uid, so the planner finds it by (lane, uid, kind). No version, no selection change, so staleness is untouched; it streams to open cards like any transaction, the activity feed shows it as one line, the planner reads it from the store, and it survives a daemon restart. The verdict for such a cell declines with that reason until the cause can plausibly have changed: the decline lifts when the cell's selected version, or any of its inputs' selected versions on that lane, changes after the note; when a workspace-code or environment change is journaled on the flow after it; when the flow's kernel is restarted; or when the cell is run explicitly. Most refresh failures are environmental (an interpreter that cannot start, a missing `uv`), and none of those repairs edits a cell — without this rule reactivity would stay silently dead after any transient failure. Where each lift is read from: the version, workspace-code, environment and explicit-run lifts are store facts — the note declines only while it is newer than each of them on that lane; the kernel-restart lift is the session's, because a restart journals nothing: the session remembers the step at which it opened and at which its kernel was last restarted, and a note older than the later of the two no longer declines. A daemon restart therefore lifts every decline (the kernel is the daemon's child and starts anew with it): the note stays in the journal, the feed and `cells.show` as history, the card stops showing it as a decline, and the next sweep submits the target again — a target that fails again gets one new note. While declined a target is not resubmitted, so one failure is one note. The reactor never arms on transactions, so recording a failure cannot start a sweep.
- A target whose plan holds an unresolvable reference, or whose closure would demand the producer of a dangling experiment (D6.5), is declined by the verdict with a reason naming the reference or the removed experiment, never submitted.
- **Refreshing state**: when the reactor takes a target, a state frame (D6.5) marks the cell `refreshing` until the run's `started` event; the card shows it. The watcher's debounce before an external-editor edit reaches the reactor is accepted as-is (it is by design); `refreshing` begins when the target is taken, not when the file changes.
- Verdict wording: an `unmaterialized` cell under `auto` says *never run yet — run it once to enable auto-refresh*; a stale never-timed cell keeps the current line; a cell blocked by a failure names the failed parent and says that an edit to *that* cell is what unblocks it (an edit to a sibling does not). A stale cell under `auto` never renders an empty auto line.
- The top-bar stale summary counts cells by gate: waiting on threshold · never timed · blocked by a failure · could not refresh.

## D8. Pipelines **[R17]**

- `run` (API, CLI, MCP) accepts no target: it plans the leaves of the lane the verb addresses (`branch` / `--lane`, defaulting to the checked-out lane as on every verb) — every cell no other cell on the lane consumes — and runs what is stale or unmaterialized among their closure. The UI's *rerun lane* uses it instead of a client-side loop.
- CLI exit code, with or without a target: 0 when every planned cell ended succeeded or was pruned; 1 if any failed, was abandoned or could not be planned; the summary names each failed cell.
- `lumlflow run` that had to start a background daemon stops it on exit unless `--keep-daemon` — and only when nothing else attached to it meanwhile: with a leased agent session, a stream subscriber (a browser a later `ui` opened on it, D3) or another flow open on it, `run` leaves the daemon running and prints one line saying so, its exit code still reporting the run; a `run` that found a running daemon leaves it running. The rule is `run`'s alone: every other verb keeps today's behaviour and leaves a daemon it started running — `agent begin` in particular, whose leased session must outlive the process so that the agent's file edits and `agent end` find the same daemon.

## D9. Agent pairing

### D9.1 Two classes, one registry

- **Shell agents** (Claude Code, Codex CLI, Gemini CLI, Cursor Agent CLI, Copilot CLI, opencode) edit `cells/*.py` directly and use `lumlflow <verb> --json`; the DSL reaches them through the served guide. One user-level MCP entry per harness is installed for attribution and typed tools; they work without it.
- **Non-shell agents** (Claude Desktop, Cursor / Windsurf / VS Code chat, JetBrains AI, any MCP client) get MCP tools and resources only.
- The registry is lumlflow's own module, `daemon/harnesses.py`: a plain list of entries (`id`, display name, detection — binary on PATH and/or config directory, whether the harness spawns MCP servers with the project as cwd, the **user-level** config path and its shape, and the **environment marker** — the variable the harness sets in the shells it runs, by which a bare verb is attributed to it, D9.5; a harness with no verifiable marker has none, and its bare verbs attribute as `user`). The cwd column decides nothing about the entry — every harness gets the same one (D9.2); it says only whether the server's `status` and `init-flow` can default their directory to the project, or whether the agent passes one (D3). No code is shared with Prisma. Project-scoped config locations are never used. The table below holds the best-known starting values; **each path, shape and environment marker is verified against the harness's current documentation before implementation**, and the verification is recorded in the module. A harness whose config path or shape cannot be verified ships detect-only: it is listed, the panel shows the snippet and the documented path, and no writer is installed for it.

Best-known values — **unverified**; paths move, so each row is confirmed against the harness's current documentation before it is implemented, and rows that cannot be confirmed ship as detect-only:

| Harness | Detect | User-level MCP config | Shape | cwd = project? | Environment marker |
|---|---|---|---|---|---|
| Claude Code | `claude` on PATH, `~/.claude` | `~/.claude.json` (global `mcpServers`; the per-directory `projects[<dir>].mcpServers` form is also outside the repo) | `{"mcpServers": {name: {command, args, env}}}` | yes | `CLAUDECODE` |
| Claude Desktop | app config directory | `~/Library/Application Support/Claude/claude_desktop_config.json` / `%APPDATA%\Claude\…` | same | no | — (no shell) |
| Cursor | `cursor` / `cursor-agent`, `~/.cursor` | `~/.cursor/mcp.json` | same | yes (agent CLI / workspace) | `CURSOR_AGENT` |
| Windsurf | `~/.codeium/windsurf` | `~/.codeium/windsurf/mcp_config.json` | same | workspace | none known |
| VS Code (Copilot) | `code` | user `settings.json` → `mcp.servers` | `{"servers": {name: {"type": "stdio", command, args}}}` | workspace | none known |
| Codex CLI | `codex`, `~/.codex` | `~/.codex/config.toml` | `[mcp_servers.<name>] command = … args = […]` (TOML) | yes | a `CODEX_*` variable, to be confirmed |
| Gemini CLI | `gemini`, `~/.gemini` | `~/.gemini/settings.json` | `{"mcpServers": …}` | yes | `GEMINI_CLI` |
| opencode | `opencode` | `~/.config/opencode/opencode.json` | `{"mcp": {name: {"type": "local", "command": [ … ]}}}` | yes | none known |
| Copilot CLI | `copilot`, `~/.copilot` | `~/.copilot/mcp-config.json` | `mcpServers` | yes | none known |

A marker in the last column is as unverified as the paths; a row whose marker cannot be confirmed keeps its entry — detection, config and writer are untouched — and attributes bare verbs as `user`.

### D9.2 The entry

- One static entry for every harness, desktop apps included, named `lumlflow`: command `<lumlflow executable> mcp`, with **no `--workspace`** and no other argument. Nothing is keyed by path and nothing names a directory: the server reaches the one daemon (D3), addresses flows by path, and defaults the directory of `status` and `init-flow` to its own cwd — the project, for a harness that spawns servers there; for a desktop app with no meaningful cwd the agent passes the directory. There is no per-workspace entry, no served-workspace list and no `lumlflow-<workspace>` naming; nothing changes when directories come and go.
- `command` is `lumlflow` when it is on PATH, else the absolute path of the running daemon's executable — the one `ui` or the first verb started it from — kept current by the sync pass. Ownership marker: `env: {LUMLFLOW_MANAGED: <version>}` where the shape allows `env`; under the table for TOML.

### D9.3 Install and sync

1. On daemon start and whenever the panel's **Agents** section opens, harnesses are detected (PATH + config directories; cached per daemon).
2. The section lists each detected harness with a state — *not set up* · *set up* · *out of date* (executable moved, older marker — transient, see 6) · *broken* (the entry's command no longer exists) · *removed by you* — a per-harness checkbox and one **Set up** button; **Update** appears only beside *out of date* and retries the write. Shell harnesses carry *also works without setup: run `lumlflow guide` in it*.
3. First time per harness: one-line consent naming the file to be written, remembered in the daemon's state directory (never in `flow.yaml` or the repository). Consent covers later automatic rewrites of the entries lumlflow owns in that file (6); it is asked again only after **Remove**.
4. Writing: parse the existing file, replace only entries lumlflow owns (the marker; an entry named `lumlflow` whose command is a lumlflow executable counts as owned too, so one a pre-release build wrote is replaced rather than left beside the new one), keep every other key, write atomically, keep one `.bak` on first touch. The writer re-reads the file immediately before it writes and writes nothing when the entries it owns already match — a harness rewrites its own config while it runs, and the narrower the window the fewer updates lost on either side (D13). A config file or directory that does not exist yet is created, with nothing to back up — the consent line names the path either way. A file that does not parse is never rewritten — the panel shows the snippet and the path instead. Codex's TOML config gets a writer of its own (D13).
5. After a write the panel names the one thing left to the user (*restart Claude Desktop* / *approve the server when Claude Code asks*).
6. **Sync**: the desired entry is a pure function of (executable, lumlflow version). The daemon recomputes it on every daemon start and section open and, for every harness whose consent is on record, rewrites the entries it owns that differ without asking again — so *out of date* is shown, with **Update**, only when that rewrite could not be applied (the file no longer parses or is not writable). A newly detected harness is proposed, never silently added; an entry the user deleted stays deleted until they press Set up. **Remove** deletes every entry lumlflow owns. `lumlflow doctor` lists them.
7. New API methods back the section (`agents.harnesses`, `agents.setup`, `agents.remove`): `harnesses` lists each detected harness with its registry id, display name, state from the vocabulary above, config path and the snippet the panel would show; `setup` and `remove` answer with that harness's entry as it now stands, so the panel re-renders from the reply. The pair-an-agent button on the empty flow and in the identity line opens the section.

### D9.4 What the agent is told — served, never written

- The MCP `instructions` grow to the short rules, name `context` as the first call and `lumlflow://guide` as the first read; the resource returns the cheatsheet `docs.CHEATSHEET` renders, generated in memory. The current closing sentence — *nothing here writes files or puts a lane on disk* — goes: under D2 an edit on the checked-out lane is written to `cells/` at once, and the instructions say so. `lumlflow guide` prints the same text; `lumlflow context` ends with a one-line pointer to it. Both texts also say that `use`, `rewind` and `adopt` rewrite `cells/` on the checked-out lane at once, and `context` names the last such rewrite — the verb, lane and step — so an agent that calls it first sees when the files moved under it (D13).
- The scaffold keeps the `lumlflow_typing` header and adds one comment line naming `lumlflow guide`. Nothing else lands in the repository; the `.gitignore` inside `<name>.flow/` remains the one exception.

### D9.5 Attribution for shell agents

Order of precedence for a bare verb: `LUMLFLOW_ACTOR` if set; else, when a harness's environment marker (the registry entry's, D9.1) is present in the shell the verb inherits, that harness's registry `id` (`claude-code`, `codex`, …); else `user` — which is also what a harness with no verifiable marker gets. This changes only the actor a transaction carries: no session is registered, so the pair line — which reads `agent.begin` / `agent.end` — is untouched; the activity feed shows the verb under that name. `agent exec` stays as the explicit wrapper. A registered shell agent's direct file edits are attributed by the watcher rule of D2 **[R2]**: with exactly one session registered on the flow they carry its actor. MCP attribution keeps its precedence (`--label`, then `LUMLFLOW_ACTOR`, then `clientInfo.name`, then `mcp`), with one addition, placed after `LUMLFLOW_ACTOR` and before `clientInfo.name`, so that one agent does not appear under two names: when the handshake's `clientInfo.name` matches a registry entry, the label defaults to that entry's `id`, so a Claude Code session over MCP and its bare verbs both read `claude-code` in the feed; the actor's pid suffix stays as today.

### D9.6 Send to agent

Stays copy-to-clipboard, shrunk to the single **copy context** gesture of D1.

## D10. Cell placement, tracker and reactivity in the CLI and MCP

`cells new --anchor/--all-outputs`, `cells move`, `agents list/setup/remove` (over `agents.harnesses/setup/remove`), `run` with no target, `guide`, `doctor`, `gc` are CLI verbs; `new-cell` gains `anchor`/`all_outputs`, `move-cell` is a new tool over `cells.reorder` (non-shell agents have no other way to place a cell), `run` loses its required target, and `lumlflow://guide` is a resource. Every new API method is `--json`-able like the rest.

## D11. Production readiness

### D11.1 Frontend CI

A job in `[lumlflow] tests-and-linters.yml` (or a sibling workflow with the same trigger paths) runs `npm ci`, builds `@luml/experiments` and `@luml/attachments`, then `vue-tsc --build`, `eslint`, `vitest run` and `vite build` in `lumlflow/frontend`, on pull requests touching `lumlflow/**`. The package's `lint` script runs `eslint` with `--fix`, which would pass in CI while rewriting files; the job invokes `eslint` without `--fix` (a dedicated script or the bare command).

### D11.2 Dependencies and first run **[R8]**

- `scikit-learn` and `matplotlib` leave the runtime dependencies; `pyarrow` joins them.
- A frame output serialized in a workspace env without `pyarrow` fails the run with a sentence naming the package to install into that env.
- A run declaring or consuming an `experiment` output in a workspace env without `luml-sdk` fails before the cell's code executes with a sentence naming the package to install into that env (D6.2, D6.4); lumlflow's own interpreter always holds it, and nothing is installed on the user's behalf.
- `uv` is named as a requirement in the README and guide; its absence is a `FlowError` sentence wherever the daemon would spawn it; the Packages panel says *no uv-managed environment here* instead of an empty list.
- **First run** **[R8]**: the documented install is `uv tool install lumlflow` / `pipx install lumlflow` (D12), whose isolated environment holds no `pandas`, so the quickstart creates a project first — `uv init`, then `pandas` and `pyarrow` added — and the D3 walk-up runs the flow on that project's venv. A directory with no project above it runs on lumlflow's own interpreter, where `pyarrow` is present as a runtime dependency and `pandas` only if that environment happens to hold it (a `pip install lumlflow` into a shared venv); a cell's `import pandas` failing there is an ordinary missing user package, never a sentence from lumlflow's code.
- The `churn.flow` demo — a repository fixture, not part of the wheel — moves out of `lumlflow/` into its own directory (`lumlflow/examples/churn/`), beside a `pyproject.toml` declaring its own dependencies (scikit-learn, matplotlib, pandas, pyarrow, luml-sdk — the last two because a frame output and an `experiment` output in that venv need them), so that the D3 walk-up from the flow's containing directory finds that file and not lumlflow's own **[R28]**; the demo no longer depends on lumlflow's environment. The move lands before D3's rooting does, since between the two opening `lumlflow/churn.flow` would `uv sync` lumlflow's own project. `/examples` is excluded from the sdist as `/frontend` is (the wheel never carried the demo; the sdist did), so the demo ships in neither distribution. Whether the demo runs end to end on its own venv — `uv sync` fetching scikit-learn — is a manual check, not a test; the automated check is that the walk-up resolves the demo's `pyproject.toml`.

### D11.3 The shipped contract

- `lumlflow ui --host` is restored (default `127.0.0.1`); the daemon binds the web listener to it and records it (D3). The token is required on a non-loopback bind exactly as on loopback. Known limitation **[R15]**: the tracker routers on the same port are unauthenticated and CORS is `*`; unchanged from `main`. Because a non-loopback bind exposes exactly those routers to the network, the option's help text and the README line that documents it carry that one sentence, `lumlflow ui` prints it at start whenever the bind is non-loopback, and `doctor` prints it when the running daemon is bound that way.
- Docs: see D12.

### D11.4 Store version tolerance **[R31]**

- Tolerance is forward-looking only — for what a future release writes; nothing written by a pre-release build needs to open (Proposals). Two tolerances, because the two files are treated differently. Journal ops and transactions *ignore* unknown fields on read. The manifest and its settings *preserve* unknown keys: read without rejecting them and written back unchanged — the models cannot both drop and carry, so the manifest side keeps what it does not know rather than ignoring it. The preservation matters because the daemon rewrites `flow.yaml` on every accept in a shared repository: an older lumlflow touching a flow must not strip what a newer one wrote.
- `open` compares the journal's `FlowInit.schema_version` — written today and never read — with the constant the running lumlflow writes, 2 in this release (D2). A store at a newer version, or one carrying an op type this lumlflow does not know, fails `open` with a sentence naming both numbers (or the op), never "corruption". A store at an older version — 1, which only a pre-release build wrote — is refused with a sentence naming both versions and telling the user to delete `<name>.flow/.lumlflow/`, after which the flow re-initialises from `cells/` and `flow.yaml`.

### D11.5 Dev surfaces

The design gallery route is registered only under `import.meta.env.DEV` (its import is already dynamic); the `?state=`/`?source=` switch is gone (D1); `FileRenderer` downloads (D6.9).

### D11.6 Operability **[R6]**

- `lumlflow doctor` prints: the state directory and whether it is on a local filesystem, the one daemon record (pid, instance id, socket address, web host and port, tracker store, version) or that there is none, the lock state (held or free), the liveness handshake's result (answering with the record's instance id, not answering, or stale record), the log path, interpreter path and source for the directory it is run in, the tracker store path, disk usage of the flow stores beneath that directory, and the harness entries lumlflow owns (D9).
- The daemon's log is size-rotated (a small fixed number of files); `lumlflow ui` prints its path at start and the daemon-down banner shows it.
- `lumlflow gc` runs `gc.sweep` for the flows beneath the directory it is run in (D3) and reports bytes reclaimed. A sweep never unlinks bytes of a run in flight: output refs are pinned before the kernel stages them (or in-flight runs' scratch and staged blobs are excluded from the sweep). That rule is what makes `gc` safe to run while a kernel is running; it does not wait for the run.
- Troubleshooting docs gain a *how to report a problem* line naming `doctor` and the log path.

### D11.7 Which Python **[R30]**

The Packages panel header shows the interpreter path and its source — the resolved env directory, or *lumlflow's own interpreter* — from the environment description `status` and the env report already carry (`envs.describe`, path and source), not from the kernel handshake, whose `python` is only a version string. `lumlflow status` and `lumlflow env status` print only the path today, and `lumlflow context` prints no interpreter at all (its payload carries none); all three gain a line with the path and its source — `context`'s payload gaining the interpreter it lacks — and the header reuses that sentence.

## D12. Documentation alignment

Scoped to what the decisions above require: `lumlflow/docs/user-guide.md` (the tracker claim at :39 becomes true, with the sentence that a cell declaring or consuming an `experiment` run on a project venv needs `luml-sdk` installed there (D11.2); the Compare *Links* paragraph at :195 keeps its experiment-link sentence and loses its model-card sentence, `ModelRenderer` and `log_model` being out of scope; the params-editing sentence at :91 goes; the workspace paragraph at :67 describes D3; the settings count at :103; the agent section describes D9; troubleshooting drops the lock entry and gains the how-to-report line and log path, and a line that a store refused on open names both versions — the store's and the running one — and that a store from a pre-release build is re-initialised by deleting `<name>.flow/.lumlflow/`, after which the flow rebuilds from `cells/` and `flow.yaml`; `uv` and `uv tool install`/`pipx` named; a *what to commit / what a clone sees* section for the git-friendly pillar: `cells/*.py` and `flow.yaml` are the committed surface, `.lumlflow/` — journal, values, previews, index, every lane and result — is not and is hidden by the `.gitignore` lumlflow writes inside `<name>.flow/` on `init`, the one file it writes into a repository — written only when a `.git` ancestor exists at that moment, so a flow created before `git init` needs that line added by hand; a clone re-roots a fresh history under the committed flow id with `main`'s cells as they were on disk; and a `git checkout` or `pull` that puts an older version of a cell file back is completed by the daemon to the lane's head and noted in the feed (D2) — `rewind` is how to make the revert stick), `lumlflow/README.md` (`--host` true again, with the one-sentence non-loopback warning of D11.3; the quickstart creates a project — `uv init`, `pandas` and `pyarrow` added — before `lumlflow ui`, and names `uv` (D11.2); a Workspace / flows section linking the guide), `docs/docs/apps/lumlflow/lumlflow.md` (a Workspace / flows section linking the guide), `docs.CHEATSHEET` (lane vocabulary, tracker sentence, new verbs, and the MCP entry as `lumlflow mcp` with no workspace argument).

## D13. Dependencies and trade-offs

- **Adds**: `pyarrow` (runtime), `tomli-w` (TOML writer for Codex config). **Removes**: `scikit-learn`, `matplotlib`. `luml-sdk` stays (the kernel writes the tracker through it, and a workspace venv that runs a cell declaring or consuming an `experiment` must hold it — D11.2), `keyring` stays (tracker auth).
- **Order key in `flow.yaml`** increases manifest churn in git diffs; accepted — ordering is presentation, and the alternative (client-only) loses placement on reload. Not journaled: rewind does not restore card order.
- **Rooting the scan and watch in the flow's containing directory** puts no bound on the tree: a flow beside a large repository pays a measurable per-verb cost (about half a second per 10,000 `.py` files) for hashing every `.py` under it, less what the D3 exclusions prune. Accepted for the MVP — a bound or a cache would engineer what has not bitten yet — and the mtime cache in the out-of-scope list is the remedy when it does.
- **One daemon per user** serves every open flow from one process: a runaway flow's daemon-side work — reconciles, previews, journal writes — shares one event loop with every other open flow (cell code never does: kernels are already one process per flow). Accepted — the loop is I/O-bound, and one process is what lets one record and one lock answer *which daemon*. One tracker store and one host per daemon, fixed by whoever starts it — a `ui` with its flags, or a verb or `lumlflow mcp` with the environment it inherited — for the daemon's life: a second `ui` asking for another store or host is refused rather than served beside it, and one asking for another port is told which port is serving; a user whose first contact was a verb gets the default store and port, and stops the daemon to change them. A foreground `ui`'s Ctrl-C ends the one daemon for everyone attached to it — MCP sessions and runs of every other project included: accepted, the daemon is the user's and the user asked; `ui` says what is attached on one line first, and the mitigation is to let verbs and `lumlflow mcp` start the daemon in the background and run `ui` after it, which then only attaches (D3). The landing page needs a directory to list, so `ui` still carries its launch directory — as a listing filter, never as a boundary: the same daemon serves a flow opened from anywhere.
- **Sweeping every lane** can run more cells; the cost threshold applies per lane as today, and archived lanes are skipped.
- **Dropping the lock** means `use`/rewind/adopt rewrite `cells/` under a working agent; the next `context` says so, and a real collision on one cell is what `EditConflict` handles. Attribution of file edits rests on the registered sessions instead of a holder **[R2]**: a hand edit in an external editor while exactly one agent is registered is journaled under that agent — today's behaviour — and `agent end` is what ends it; a `user` verb that happens to reconcile first never claims the change, so which door noticed it first is never what decides the name.
- **Two processes on one SQLite store** — the kernel writes the tracker, the daemon reads it and fails an orphaned experiment (the Experiments API's writes staying the daemon's, D6.1): accepted. SQLite's locking suffices at this write rate, a `database is locked` is retried under a busy timeout (D6.6), and it is far simpler than a proxy over a kernel→daemon channel and a daemon-side writer.
- **Two SDK versions on one store** — the venv's `luml-sdk` writes, lumlflow's own reads, and the SDK migrates a store's schema on open: accepted; the SDK owns its schema compatibility, and lumlflow validates and warns — the mismatch warning on the run and the `unreachable` sentence on the daemon's side (D6.6) — and never pins or blocks. The alternative, the daemon writing on the kernel's behalf, is what R9 rejected.
- **Rewriting a harness's live config** — `~/.claude.json` is rewritten by Claude Code itself while it runs, so lumlflow's atomic write can still race it and one side's update be lost. Accepted: the writer re-reads before it writes and skips unchanged entries (D9.3), so it writes rarely and briefly, and a lumlflow entry that a harness clobbered is repaired by the next sync pass.
- **Memoization on the experiment snapshot** keys on the final numbers only: a consumer that read `metric_history` is memoized on the producer's final params and metrics, so a rerun that records the same final numbers over a different curve does not rerun it. Accepted — the alternative, hashing the history, would make every consumer rerun on any curve jitter — and the snapshot is what the card shows, so what prunes is what the user sees.
- **No cloud path** in the MVP: `promote` returns, if at all, as "publish this tracker experiment", after this spec.
- **Gallery kept DEV-only** keeps `workbench/fixtures/` maintained against wire-type changes; the fixtures no longer ship or masquerade as live data.

# Scenarios

## Scenario: Prune — production bundle has no fixture or concept surfaces
**Given** a production build of `lumlflow-ui`
**When** a user opens `/flow/design`, `/flow/railroad`, or a real flow's URL with `?state=running` or `?source=fixture`
**Then** the design and railroad routes do not exist, the query keys are ignored and the live workbench renders, and no chunk in `dist/` contains the fixture data or the gallery.

## Scenario: Prune — a manifest carrying an unknown key opens and keeps it
**Given** a `flow.yaml` carrying a top-level key and a `settings` key this lumlflow does not know
**When** the flow is opened and the daemon next rewrites the manifest
**Then** it opens with no error and both keys are still in the rewritten file, unchanged.

## Scenario: Prune — declaring a model no longer touches the network or the lockfile
**Given** a workspace with a `pyproject.toml` and no LUML API key
**When** a cell declaring `produces = {"model": "model"}` runs
**Then** no upload is journaled or attempted, `pyproject.toml` and `uv.lock` are unchanged, and the activity feed shows no upload lines.

## Scenario: Prune — retired spellings are gone
**Given** the CLI and MCP server
**When** `lumlflow fork x`, `lumlflow variant list` or the MCP tool `new-variant` is invoked
**Then** the CLI reports an unknown command and the MCP server reports an unknown tool; `lumlflow lane new x` and `new-lane` work.

## Scenario: Ownership — a cell added while an agent is registered is written at once
**Given** an agent session registered via `agent.begin`
**When** the user adds a cell from the UI
**Then** `cells/untitled_N.py` exists immediately, `cells.list` on the next revision still lists it, and the journal holds one `added` transaction under `user` and no `deleted` transaction.

## Scenario: Ownership — an agent renames a file after a UI edit
**Given** the user saved `score` from the editor and the file holds the new bytes
**When** an agent runs `mv cells/score.py cells/total.py` and the daemon reconciles
**Then** the cell is renamed to `total`, its head is still the user's version (a `Renamed` op, no new version, no `divergent` flag), and consumers are respelled by uid.

## Scenario: Ownership — verbs no longer accept force for the lock
**Given** any registered agent session
**When** `rewind`, `adopt`, `rename`, `cells.delete`, `import` or `switch` is called without `force`
**Then** each succeeds, `cells/` is rewritten to the resulting selection, a `force` parameter sent to `rewind`/`rename`/`cells.delete`/`import`/`switch`/`flow.checkout` is ignored like any parameter the API does not read, their CLI `--force` flags are unknown options and their MCP tools no longer declare the argument, and `force` on `adopt` still resolves an `AdoptConflict` and nothing else.

## Scenario: Ownership — a stale base is the one collision that is refused
**Given** the user opened `score` in the editor at head version A, and an agent then edited `score` to version B
**When** the user saves with `base = A`
**Then** `cells.edit` raises `EditConflict` naming the cell, nothing is journaled, the editor offers *overwrite* / *save to a new lane*, and the same save with `force` lands as a new head over B.

## Scenario: Ownership — a hand edit matching another lane's older version is kept
**Given** lane `exp` has `score` at version A (step 6) and `main` at version B (step 7), and `main` is on disk
**When** the user writes version A's bytes into `cells/score.py` and the daemon reconciles
**Then** `main` gets a new version with A's bytes as an offline edit under `user`, the file is not rewritten back to B, and one transaction is journaled.

## Scenario: Ownership — a hand revert to this lane's older version is completed and recorded
**Given** `main` on disk with `score` at version B (step 7), whose parent A (step 6) is on `main`'s own lineage
**When** the user runs `git checkout` to put A's bytes back into `cells/score.py` and the daemon reconciles
**Then** the file is rewritten to B, no version is created, `main`'s selection is unchanged, one `system` transaction holding a *projection completed* cell note naming `score` and the restored version is journaled and the activity feed shows it, and rewinding to step 6 restores A.

## Scenario: Ownership — a reconcile-detected change is attributed to the one registered agent, never by timing
**Given** an agent session `claude-1` registered via `agent.begin` and `cells/score.py` edited directly on disk
**When** the watcher notices the file; separately when the user's `cells.list` from the UI is the verb that reconciles it, inside the watcher's debounce; and separately when a second session `codex-2` is also registered and the watcher notices it
**Then** the watcher-found change under one session is attributed to `claude-1`; the change the UI's `cells.list` found is attributed to `claude-1` too — a `user` verb never claims it; the watcher-found change under two sessions is attributed to `user`; and a bare `lumlflow cells list` from an `agent exec` shell, or from a shell carrying `LUMLFLOW_ACTOR`, attributes the reconcile it triggers to that actor.

## Scenario: Workspace — the launch directory is a listing, not a boundary
**Given** `~/proj/sub` contains no flows, `~/proj/a.flow` exists, and no daemon is running
**When** `lumlflow ui` is launched in `~/proj/sub`, and the browser then opens `~/proj/a.flow` by its path
**Then** the landing page lists no flows and offers *New flow*, there is no browse-up control, `a.flow` opens in the same daemon with `~/proj` as its workspace, and no second daemon starts.

## Scenario: Workspace — every verb reaches the one daemon
**Given** `lumlflow ui` running, launched in `~/proj`, and shells in `~/proj/sub` and `~/other`
**When** `lumlflow status` runs in each
**Then** both answer from the same daemon — one pid, one record — no second daemon starts, and each lists the flows beneath its own cwd: none for `~/proj/sub`, `~/other`'s flows for `~/other`.

## Scenario: Workspace — ui attaches to the daemon a verb started
**Given** a verb started a background daemon, now carrying a run and a leased MCP session, and no `ui` running
**When** `lumlflow ui` is launched in any directory
**Then** it prints the recorded URL, opens the browser on it and exits; the run continues, the session stays registered, and one daemon is running.

## Scenario: Daemon — killed with kill -9, the next start is clean
**Given** a running daemon killed with `kill -9`, its record still on disk and its lock released by the operating system
**When** `lumlflow ui` runs
**Then** the stale record is unlinked, a new daemon starts with a new instance id, and no sentence mentions the dead one; and `lumlflow daemon stop` run against the stale record before that start signals no pid — the lock is free — unlinks the record and says no daemon was running.

## Scenario: Daemon — two starters at once make one daemon
**Given** no daemon running
**When** two verbs — or a verb and `lumlflow mcp` — start at the same instant
**Then** each spawns a daemon process; one takes the lock and serves, the other finds the lock held and exits with the *someone is there* code; both callers ping and attach, both answers carry the same instance id, one record exists and one daemon process remains.

## Scenario: Daemon — a hung daemon is named, never replaced
**Given** a daemon holding the lock whose socket does not answer
**When** a verb or `lumlflow ui` runs
**Then** after a few seconds of retries it fails with a sentence naming the log path and `lumlflow daemon stop`, starts nothing and unlinks nothing; `lumlflow daemon stop` ends the process by the recorded pid — the lock being held — and the next start is clean.

## Scenario: Daemon — a kernel outliving a dead daemon holds no lock
**Given** a daemon with a running kernel subprocess, killed with `kill -9` while the kernel survives
**When** the next start runs
**Then** the lock is free — the lock file was never inherited — a new daemon starts, and the orphaned kernel is not what answers the handshake.

## Scenario: Daemon — ui with a conflicting store or host is refused
**Given** a daemon serving tracker store `~/a/experiments` on loopback port 5000
**When** `lumlflow ui --path ~/b/experiments` runs, separately `lumlflow ui --host 0.0.0.0`, and separately `lumlflow ui --port 6000`
**Then** the first two are refused with a sentence naming the running store and host and `lumlflow daemon stop`, nothing starts and the daemon is untouched; the third says port 5000 is serving and opens the browser there.

## Scenario: Daemon — a background daemon serves the default port and store
**Given** no daemon running; a shell with no `BACKEND_STORE_URI` and, separately, a shell with it set to `~/b/experiments`; and, separately, another process holding the default web port
**When** `lumlflow status` starts the daemon from the first shell, and — after a `lumlflow daemon stop` — from the second, and from the first again while the port is held
**Then** the first daemon serves the default store on loopback and the default web port, and a later `lumlflow ui` prints that URL and attaches; the second serves `~/b/experiments`, and a later `lumlflow ui` run without `--path` in a shell without that variable is refused naming `~/b/experiments`; the third binds an ephemeral port, and a later `lumlflow ui` says that port is serving and opens it.

## Scenario: Daemon — Ctrl-C on a foreground ui with clients attached
**Given** `lumlflow ui` running in the foreground with an MCP session leased against it and a flow from another directory open in a second tab
**When** Ctrl-C is pressed
**Then** `ui` prints one line naming what is attached — the leased session and the other open flow — and still stops: kernels, stores, record and lock go as on any Ctrl-C, the following `lumlflow agent end` finds no daemon, and the tab shows the daemon-down banner with the log path.

## Scenario: Daemon — a state directory on a network filesystem is warned about, not refused
**Given** `LUMLFLOW_STATE_DIR` pointing at a directory on a network filesystem
**When** `lumlflow ui` starts and `lumlflow doctor` runs
**Then** `ui` prints one warning line naming the directory and the reason — file locks are unreliable there — and starts; `doctor` reports the directory as not local; nothing is refused, and on a local directory neither says anything.

## Scenario: Workspace — a cell's cwd is the flow's directory
**Given** `~/proj/churn.flow` and a cell that reads `data.csv` by relative path
**When** the cell runs
**Then** `data.csv` resolves to `~/proj/data.csv`, `ctx.workspace_dir` is `~/proj`, and `ctx.tempdir()` returns a directory under the run's scratch which is removed after the run.

## Scenario: Workspace — interpreter resolution walks up
**Given** `~/proj/.venv` and `~/proj/pyproject.toml`, and the flow two levels below at `~/proj/experiments/q3/churn.flow`
**When** the kernel starts for that flow
**Then** it runs on `~/proj/.venv`'s interpreter, no `uv sync` runs — an existing `.venv` is used as it is — and the Packages header names that path; with `~/proj/pyproject.toml` and no `.venv` beside it, `uv sync` runs against that file and the kernel runs on the venv it creates; with no venv or `pyproject.toml` above, it runs on lumlflow's interpreter and the header says *lumlflow's own interpreter*.

## Scenario: Workspace — moving the workspace keeps the checked-out lane
**Given** lane `exp` checked out on disk and the daemon stopped
**When** the directory is moved and the flow is opened from its new path
**Then** the worktree is bound to `exp` again, the cold reconcile runs against `exp`, `main`'s selection is unchanged, and the journal contains no `offline edits` transaction.

## Scenario: Workspace — environment directories are not shared code
**Given** a workspace with `venv/lib/python3.12/site-packages/pkg/__init__.py` and a `.gitignore` listing `build/`
**When** `pip install` adds files there and a verb quiesces
**Then** no cell becomes unsynced and no `WorkspaceCodeChanged` op names those paths.

## Scenario: Workspace — nested flows are two roots, one inside the other
**Given** `~/proj/a.flow` and `~/proj/exp/b.flow`, both open, with `~/proj/exp/helpers.py` consumed by a cell of each
**When** `helpers.py` is edited
**Then** the cells of both flows become unsynced with a workspace-code cause naming it, an edit to `~/proj/top.py` reaches only `a.flow`, and closing `b.flow` leaves `a.flow`'s watch in place.

## Scenario: Limits — a large stdout write completes the run
**Given** a cell that prints 200 000 characters in one write
**When** it runs
**Then** the run succeeds, the console shows the full text, delivered in chunks of at most 32 KiB, the kernel state stays `running`/`idle`, and no second kernel is spawned.

## Scenario: Limits — a kernel message above the limit fails the run, not the kernel
**Given** a cell whose single message to the daemon — one result or capture line on the kernel link — exceeds 16 MiB
**When** it runs
**Then** the run fails with a sentence naming the limit, the kernel is not declared stopped while its process is alive, the next run reuses the same kernel, and no second kernel is spawned.

## Scenario: Limits — a large edit over the socket is answered
**Given** an MCP client with a leased session
**When** it sends `edit-cell` with a 200 KiB source
**Then** the edit lands, the connection stays open, the session stays registered, and the pair line still shows the agent.

## Scenario: Limits — an oversized RPC line is refused politely
**Given** a socket client
**When** it sends a 20 MiB line
**Then** it receives an `INVALID_REQUEST` error naming the limit and can send the next request on the same connection.

## Scenario: Editing — an empty source is refused
**Given** a cell with 194 bytes of source
**When** `cells.edit` is called with `source: ""` or `"   \n"`
**Then** a `FlowError` names the cell, the file is unchanged, and no version is journaled.

## Scenario: Editing — the card keeps its detail across a journal burst
**Given** an agent committing ten transactions in a second
**When** the user clicks *edit* on a card during the burst
**Then** the editor opens with the current source (never blank), `save` sends the source and its `base`, and *edit* / *apply suggestion* are disabled only while no detail has ever loaded.

## Scenario: Robustness — an Emacs lock symlink does not break the flow
**Given** `cells/.#score.py` as a dangling symlink and `cells/latin1.py` holding a Latin-1 byte
**When** the flow is opened and `cells.list` runs
**Then** both succeed, the symlink is ignored, and `latin1` is listed as `invalid` with a flag naming the encoding.

## Scenario: Robustness — a one-line class and a BOM are legal cells
**Given** `cells/todo.py` holding `class Todo: """Write the report."""` with no uid line, and `cells/meta.py` saved as UTF-8 with a BOM
**When** the daemon reconciles
**Then** `todo` gets its uid line without a syntax error and both cells are listed with no `invalid` flag; a second reconcile changes nothing.

## Scenario: Robustness — an unreadable file elsewhere in the tree is skipped
**Given** `~/proj/churn.flow`, a readable `~/proj/helpers.py`, and `~/proj/private/notes.py` with no read permission
**When** a verb quiesces
**Then** the scan completes, `helpers.py` is hashed as shared code, `notes.py` is skipped without an error, no cell is flagged for it, and a later edit to `helpers.py` still makes its consumers unsynced.

## Scenario: Robustness — a failed fsync does not corrupt the journal
**Given** an `fsync` that raises after the bytes landed
**When** a commit fails and the next commit succeeds
**Then** the journal has no duplicated step, replay succeeds, and the flow reopens.

## Scenario: Robustness — helper edit during a long run
**Given** a cell running for 60 s
**When** `helpers.py` is edited and `cells.list` is called 5 s later
**Then** `cells.list` answers while the cell is still running — it never waits on the run — and the next run sees the new helper code.

## Scenario: Robustness — a bad parameter over HTTP is a JSON 400
**Given** the HTTP door
**When** `rewind` is posted with `to_step: "abc"`
**Then** the reply is a JSON `FlowError` with status 400 and CORS headers, and nothing is printed to the `lumlflow ui` terminal.

## Scenario: Robustness — an unexpected error over HTTP is a JSON 500
**Given** the HTTP door and a handler that raises an exception that is not a `FlowError`
**When** the method is posted
**Then** the reply is JSON with status 500, CORS headers and the exception's message, the traceback is not in the reply, and the SPA shows that message (where the traceback lands is the *doctor, logs, gc* scenario's).

## Scenario: Slugs — a path-shaped slug is refused
**Given** the daemon
**When** `cells.new` is called with slug `../../escaped`, or `rename score --to ../out`, or an empty `to`, or an export whose cell is named `../escaped` is imported
**Then** each raises a `FlowError` naming the rule, no file is written outside `cells/`, and the lane is unchanged.

## Scenario: Lanes — adopting a renamed cell keeps consumers synced
**Given** `score` renamed to `points` on lane `exp`, with `report` consuming it on `main`
**When** `points` is adopted onto `main`
**Then** `report` is `synced` with no flag, its projected file spells `points.summary`, and `run report` succeeds.

## Scenario: Lanes — deleting on an off-disk lane flags consumers
**Given** lane `exp` not on disk with `report` consuming `score.summary`
**When** `score` is deleted on `exp`
**Then** `cells.list` for `exp` shows `report` with a `dangling_ref` flag and an unsynced cause naming `score`.

## Scenario: Lanes — an import that renames a cell rewires its consumers
**Given** an export in which `score` was renamed to `points`, and `report` consuming `score.summary` on the target lane
**When** the export is imported
**Then** `report` is `synced` with no `dangling_ref` flag and its projected file spells `points.summary`; and when `cells/score.py` is renamed to `cells/points.py` by hand while holding a syntax error, the cell keeps its uid, a `Renamed` op is recorded, and fixing the syntax leaves `report` wired to it.

## Scenario: Lanes — a forced adopt over a name clash is deterministic
**Given** `main` holding a cell `score` (uid A) and lane `exp` holding a different cell also named `score` (uid B), in either creation order
**When** `exp`'s `score` is adopted onto `main` with `force`
**Then** the pre-existing cell keeps the slug `score`, the adopted cell lands as `score_2`, the adopted uid B is re-accepted, `score`'s consumers on `main` still resolve to uid A, and swapping which uid was created first gives the same result.

## Scenario: Scheduler — stop during kernel start is honoured
**Given** a cold workspace whose kernel takes seconds to start
**When** `run` is issued and `cancel` follows 100 ms later
**Then** the run ends `cancelled`, no `RunRecorded` with state `succeeded` is journaled, and the cell's code never executes.

## Scenario: Scheduler — a cell edited mid-plan is not run from the old version
**Given** a plan `load > child` in flight with `load` running
**When** `child` is edited before its turn comes
**Then** `child` either runs from the version the lane now selects or the run is reported `abandoned`; no `RunRecorded` names the superseded version, and the card never reads *stale: child was edited* right after a run of it.

## Scenario: Scheduler — reverting shared code clears staleness
**Given** every cell synced under `helpers.py` = A
**When** `helpers.py` becomes B and then A again
**Then** every cell reads `synced` with no workspace-code cause, and the reactor has nothing to do.

## Scenario: Scheduler — force does not join another lane's run
**Given** lane `a` running `train` with memo key K
**When** `run train --force` is issued on lane `b` with the same K
**Then** `b` gets its own run, not a memo hit on `a`'s flight.

## Scenario: Rendering — a frame with NaN and a datetime column pages
**Given** a frame output with a NaN float and a datetime column
**When** `asset.page` is called
**Then** it answers — a serialisation problem being an error reply, never a timeout — with `null` for the NaN and a string for the datetime, and `total_columns` matches the frame.

## Scenario: Rendering — a NaN metric is not a missing one
**Given** a `metric` output `{"loss": nan, "auc": 0.00032}` and a second output with no `loss` at all
**When** both are previewed over HTTP
**Then** the door answers 200, the first card shows `loss` as `nan` and `auc` as `3.2e-4`, and the second shows `loss` as absent, not `nan`.

## Scenario: Rendering — a polars frame stays polars
**Given** a cell returning a `polars.DataFrame` in an environment where pandas is also installed
**When** a consumer reads that output
**Then** it receives a `polars.DataFrame`; a pandas producer's consumer receives a `pandas.DataFrame`.

## Scenario: Rendering — a 200-column frame says so
**Given** a 200-column frame
**When** it is previewed and paged
**Then** the preview shows 40 columns with a footer *40 of 200 columns*, and each page carries the same column bound with `total_columns: 200`.

## Scenario: Rendering — a large image does not become "too large to show"
**Given** a matplotlib figure whose PNG exceeds 64 KiB
**When** it is previewed
**Then** the preview holds a downscaled image block, not a key-value placeholder.

## Scenario: Rendering — a tqdm progress bar is one line
**Given** a run printing `\r`-updated progress with ANSI colours
**When** the console renders 5 000 frames
**Then** the bar is a single line without escape codes, the live console buffer holds at most its bounded number of chunks, and the rendered text is appended per frame rather than re-joined from every chunk.

## Scenario: Low sweep — notes, export noise, cursor and payload
**Given** a note whose markdown holds a `<style>` block, a `<form>` with an `<input>` and a `<button>`, and a remote `<img>`; a cell file ending in two newlines; a flow deleted and re-created under the same path while a tab is open; and a failed cell whose traceback is several frames long
**When** the note renders, the flow is exported and imported, the tab's stream catches up, and *copy context* is used on the failed card
**Then** none of the forbidden elements or the remote image survives sanitising; the import mints no new version; because `flow.open` returned a different `flow_id`, both the tab's in-memory cursor and its persisted catch-up marker for that flow reset to zero and the new flow replays from the start; and the payload holds the traceback's frames and the exception's final line, not its full text.

## Scenario: Frontend — checkout refreshes the brief
**Given** the user viewing lane `exp` while `main` is on disk
**When** they click *use exp here*
**Then** the switcher shows `exp` checked out with no *viewing* icon, the identifier says the files are on `exp`, the stop payload and pair line name `exp`, and the URL drops `?branch=exp`.

## Scenario: Frontend — compare addresses a same-named flow by path
**Given** `a/sales.flow` and `b/sales.flow` under the launch directory and the compare page open on `a/sales.flow`
**When** two lanes are compared
**Then** `diff`, `tree` and every preview are addressed by `brief.path` and succeed against `a/sales.flow`; no request is refused as ambiguous and none renders `b/sales.flow`'s lanes.

## Scenario: Frontend — the token never re-enters the URL
**Given** a tab opened from `…/flow/churn?token=abc`
**When** the user clicks a cell, toggles the view and switches lanes
**Then** the address bar never contains `token=`.

## Scenario: Frontend — the running switch does not destroy a draft
**Given** an editor open with unsaved changes
**When** the reactor runs that cell
**Then** the draft is intact and the editor is still open after the run.

## Scenario: Frontend — save to a new lane asks for the name and keeps the draft
**Given** an `EditConflict` on `train` and a lane `train-edit` that already exists
**When** *save to a new lane* is chosen
**Then** the lane-name dialog opens prefilled with `train-edit`, a second name is accepted, the fork and the edit land on it; and if the edit fails after the fork, the new lane is shown and the draft is still in the editor.

## Scenario: Frontend — reconnect after sleep is quiet
**Given** a tab that dropped its socket for eight hours while an agent worked
**When** the socket reconnects and replays 150 transactions
**Then** no toasts fire for the replayed window, and `reachable` is true as soon as the socket opens.

## Scenario: Frontend — the agent-ended banner counts only later endings
**Given** `score` last changed at step 12, `report` last changed at step 16, and one `agent_end` transaction journaled at step 14
**When** the workbench renders
**Then** the *agent session ended · N stale assets* banner counts `score` and not `report`, N reads 1, and a second `agent_end` at step 18 raises it to 2.

## Scenario: Frontend — a card press selects without scrolling
**Given** the canvas scrolled so that `train_model`'s card is partly visible, with `split` selected and the URL mirroring it
**When** a control on `train_model`'s card is pressed, and then a control on the now-selected `train_model` again
**Then** the first press selects `train_model` with no scroll or pan during the gesture, its popover stays anchored, the URL now names `train_model` and nothing is sent to the daemon; the second press changes no selection and rewrites the URL not at all.

## Scenario: Placement — add downstream lands under the producer
**Given** the churn flow in notebook view
**When** *add cell downstream* is used on `eda`
**Then** the notebook reads `load_data > eda > untitled_N > split > …`, no other card changes position, and the new cell's `order` lies strictly between `eda`'s and `split`'s effective keys.

## Scenario: Placement — blank add with a selection anchors on it
**Given** `train_model` selected in the canvas
**When** *add a cell* is used
**Then** the new node appears in `train_model`'s column directly below it, `load_data` does not move, and the viewport does not jump to x=0.

## Scenario: Placement — order survives reload and rename
**Given** a note cell placed after `eda`
**When** the page is reloaded and the note is renamed
**Then** the note is still after `eda` in both views.

## Scenario: Placement — move up refused across a producer
**Given** on lane `main`, `evaluate` directly after `train_model`, which it consumes there
**When** *move up* is requested on `evaluate` while viewing `main`
**Then** the menu item is disabled in the UI, and `cells.reorder` called on `main` raises a sentence naming `train_model`; on a lane `exp` where `evaluate` does not consume `train_model`, the same reorder succeeds and `main`'s notebook still shows `train_model` before `evaluate`; and on an archived lane a topologically legal reorder is accepted, archive being cosmetic for it as for an edit.

## Scenario: Placement — a move is seen in every open tab
**Given** two tabs open on the churn flow, one in notebook view and one in canvas view
**When** *move down* is used on a note cell in the first tab
**Then** the verb's reply carries the note's new `order` and the first tab re-orders at once; the second tab receives one `order_changed` state frame on the journal channel, refetches its slice and re-places the note without moving any other node; the journal has no new transaction and neither tab's replay cursor moves.

## Scenario: Placement — a flow with no order map orders by creation step
**Given** a flow with no `order` map
**When** it is opened
**Then** the notebook order is the creation-step tiebreak, and the `order` map is absent from `flow.yaml` until a cell is added with an anchor or moved — an unanchored add and the daemon's other manifest rewrites do not invent one; on the canvas a parentless cell other than the first sits under the cell preceding it in creation order rather than in the root column, and every open places it the same way.

## Scenario: Placement — an unknown anchor is refused
**Given** the churn flow
**When** `cells.new` is called with `anchor: nowhere`, and separately on lane `main` with an anchor naming a cell selected only on lane `exp`
**Then** each raises a `FlowError` naming the anchor, no cell is added, and `flow.yaml` is unchanged.

## Scenario: Placement — tidy and the first-load fit
**Given** the churn flow open in canvas view, its nodes placed incrementally over several adds
**When** the page loads, a cell is then added, and later the **tidy** control is pressed
**Then** `fitView` runs once on the load and not on the add; the add moves no existing node; tidy recomputes the whole layout and is, beside a change to an existing cell's wiring, the only thing that moves existing nodes.

## Scenario: Wiring — downstream wires one non-experiment output
**Given** `train` producing `model` and `run: experiment`, where `primary_output` names `run`
**When** a cell is added downstream of `train`
**Then** its `consumes` is `{"model": "train.model"}` and `materialize(self, ctx, model)`; `primary_output` still names `run` for display; with `--all-outputs` both are wired; the canvas draws two distinct edges when both are consumed.

## Scenario: Wiring — an experiment-only producer wires its experiment
**Given** `evaluate` producing only `metrics: experiment`
**When** a cell is added downstream of `evaluate`
**Then** its `consumes` is `{"metrics": "evaluate.metrics"}` and its `materialize` signature names `metrics`.

## Scenario: Index — delete drops the slug and never reuses the number
**Given** `untitled_3` is the highest placeholder ever minted and `untitled_1` was deleted on every lane
**When** a blank cell is added
**Then** it is `untitled_4`, and `flow.yaml`'s `cells:` no longer lists `untitled_1`; rewinding a lane to a step where `untitled_1` was selected lists it in `cells:` again, while its `order` entry stays gone and it orders by its creation step.

## Scenario: Tracker — an experiment output creates one tracked experiment
**Given** the churn `evaluate` cell
**When** it runs and succeeds
**Then** the tracker holds exactly one new experiment named `evaluate` in group `churn`, tagged with the lane and slug, with metadata naming flow, cell, lane, version and run, the static param `alpha` that the cell logged through `ctx.tracker.log_params`, metrics `rmse/mae/r2`, status `completed`; the stored output is an `ExperimentRef` holding the id, store and snapshot — not the metric history — whose preview shows the numbers; `cells.show` reports `tracker.state == ok` with a URL the SPA routes. And separately, **Given** a cell declaring `params = {...}` and an `experiment` output, **When** it runs, **Then** those params are logged as static params before the cell's code executes and are present in its snapshot.

## Scenario: Tracker — a failed run leaves a failed experiment
**Given** a cell declaring an `experiment` output that raises after logging one metric
**When** it runs
**Then** the tracker experiment has status `error` with that metric, the run record carries the experiment id although no output was recorded, `cells.show` reports it for the failed run, and the failed card's logs tab links to it.

## Scenario: Tracker — a cancelled run fails its experiment
**Given** a cell declaring an `experiment` output that logs a metric per step in a loop long enough never to finish on its own
**When** `cancel` arrives once the tracker has been observed to hold the metric at step N
**Then** the run ends `cancelled`, the tracker experiment has status `error` holding at least those N steps, and no setting governs this.

## Scenario: Tracker — two experiment outputs are refused before anything starts
**Given** a cell declaring `produces = {"a": "experiment", "b": "experiment"}`
**When** it is run
**Then** the run fails with a sentence naming the one-experiment rule before the cell's code executes, and the tracker holds no new experiment.

## Scenario: Tracker — an unwritable store fails the run with a sentence
**Given** a tracker store the kernel cannot write (a read-only `--path`)
**When** a cell declaring an `experiment` output is run
**Then** the run fails before the cell's code executes with a sentence naming the store path, no materialization is journaled as succeeded, the tracker holds no new experiment, and `cells.list` still serves the cell's card — the daemon's read of that store is not an error.

## Scenario: Tracker — a locked store is retried, then named
**Given** a second process holding a write lock on the tracker store
**When** a cell declaring an `experiment` output runs while the lock is released within the busy timeout, and separately while it is held past it
**Then** the first run succeeds and its experiment is `completed`; the second fails with a sentence naming the store path; and in both a `cells.list` read of an experiment output's `tracker` state answers `ok` or `unreachable`, never an error.

## Scenario: Tracker — live metrics during a run
**Given** a cell logging a metric at each of M steps that blocks on a signal before returning
**When** the tracker is read from the daemon's process while the cell is blocked
**Then** the metric history already holds the M values in order with their steps — each written by the kernel as it was logged, nothing waiting for the run to end — and `cells.list` over the socket answers while the cell is still blocked on the signal.

## Scenario: Tracker — a failed close leaves the materialization and a note
**Given** a cell declaring an `experiment` output whose run succeeds, and a tracker whose end-experiment call fails in the kernel
**When** the run completes
**Then** the kernel's `materialized` event carries the reference and the close failure, the materialization is journaled as succeeded and its output holds the reference, one `system` transaction on that lane holds an *experiment unclosed* cell note carrying the sentence, `cells.show` and the card show the note, the activity feed shows it as one line, and the cell is not stale.

## Scenario: Tracker — a kernel that dies mid-run leaves a failed experiment
**Given** a cell declaring an `experiment` output that kills its own process after logging one metric
**When** the daemon records the run
**Then** the run is `failed`, the tracker experiment has status `error` with that metric — failed by the daemon, the flow subsystem's one daemon-side tracker write — and the run record carries the id the kernel reported at start, no later event ever having arrived.

## Scenario: Tracker — memo hit creates nothing
**Given** `evaluate` materialized on `main`
**When** lane `exp` (same inputs and definition) runs `evaluate`
**Then** it is a memo hit, no experiment is created, and `exp`'s output carries the same reference.

## Scenario: Tracker — identical numbers prune consumers
**Given** `report` consuming `evaluate.metrics`, both synced
**When** `evaluate` is forced to rerun and records identical numbers
**Then** a second experiment exists, and `report` stays synced (early cutoff on the snapshot's content hash).

## Scenario: Tracker — a wrong value for an experiment output fails the run
**Given** a cell declaring `metrics: experiment` that returns `{"params": {}, "metrics": {"a": 1}}`
**When** it runs
**Then** the run fails with a sentence naming `ctx.tracker.record`, and the tracker experiment started for the run has status `error`.

## Scenario: Tracker — ctx.tracker without a declared experiment
**Given** a cell with `produces = {"result": "asset"}` that calls `ctx.tracker.log_metric`
**When** it runs
**Then** the run fails with a sentence saying an `experiment` output must be declared.

## Scenario: Tracker — a workspace venv without the SDK names the package
**Given** a flow whose interpreter resolves to a project venv holding `pandas` and `pyarrow` but not `luml-sdk`
**When** a cell declaring an `experiment` output runs, separately a cell consuming one, and separately a cell that neither declares nor consumes an experiment
**Then** the first two fail before their code executes with a sentence naming `luml-sdk` as the package to install into that env, nothing is installed on the user's behalf and the tracker holds no new experiment; the third runs and the SDK is never imported for it; and on lumlflow's own interpreter the first two run.

## Scenario: Tracker — a consumer reads the experiment handle
**Given** `report` consuming `evaluate.metrics`
**When** it reads `metrics.metrics["rmse"]` and `metrics.metric_history("rmse")`
**Then** the values match the tracker, and the materialization is neither `identity_dependent` nor `external`; a cell added downstream of an experiment-only producer receives the same handle for the output it was wired to.

## Scenario: Tracker — an SDK version mismatch warns and proceeds
**Given** a flow whose interpreter resolves to a project venv holding a `luml-sdk` of another version than the one the daemon imports
**When** a cell declaring an `experiment` output runs
**Then** the run proceeds and succeeds, the tracker holds the experiment, one warning naming both versions and the venv is in the run's console and logs and the card shows it as one warning line, nothing is installed or refused; and when the venv's SDK itself refuses a write, the run fails with the SDK's own sentence carrying the store path and that SDK's version.

## Scenario: Tracker — deleting the experiment flips the card
**Given** `evaluate`'s experiment shown as `ok`
**When** it is deleted through the Experiments API
**Then** within one state frame on the journal channel the card shows *experiment removed from the tracker* with the greyed snapshot, the client's replay cursor is unchanged, the journal has no new transaction, `run report` pulls `evaluate` in with the preflight naming why, and the reactor runs nothing on its own; a tab that reconnects afterwards shows the same state from its first `cells.list`, with no frame replayed.

## Scenario: Tracker — a delete from another process is still caught
**Given** `evaluate`'s experiment shown as `ok` and cached in the session
**When** it is deleted through the SDK from a second process, and the card is next read after the cache entry's bounded age has passed
**Then** the state reads `missing` with no restart, no journal transaction, and no frame — the re-check on the next look found it gone; a `flow.open` or a socket reconnect before that age also reads `missing`.

## Scenario: Tracker — a stale consumer under auto does not resurrect a deleted experiment
**Given** `report` consuming `evaluate.metrics`, `auto` with a generous threshold, `evaluate`'s experiment deleted in the tracker, and `report` then edited so it is stale
**When** the reactor sweeps
**Then** neither `evaluate` nor `report` runs, `report`'s auto line declines naming `evaluate`'s removed experiment, no transaction is journaled by the sweep, and an explicit `run report` runs `evaluate` first with the preflight naming why.

## Scenario: Tracker — a different store reads as unreachable
**Given** an experiment recorded while serving `~/a/experiments`
**When** the daemon is stopped and lumlflow is started again with `--path ~/b/experiments`
**Then** the card reads *recorded in a different tracker store (`~/a/experiments`)*, the link is disabled, and compare still shows the lane's numbers.

## Scenario: Tracker — a store the daemon's SDK cannot read is unreachable
**Given** a tracker store migrated forward by a newer `luml-sdk` in a project venv, on which a cell's run just succeeded
**When** the daemon reads the experiment for the card, the lane and the compare view
**Then** the run stands as succeeded with its reference, the state reads `unreachable` with a sentence naming the store and, when the store records it, the version that wrote it, and suggesting upgrading lumlflow; the card renders the snapshot, the lane and the compare view stand, and no verb fails.

## Scenario: Tracker — deleting a flow-produced experiment warns
**Given** an experiment carrying `lumlflow` metadata
**When** delete is chosen in the Experiments screen
**Then** the confirmation names `churn / evaluate` on lane `main` before proceeding.

## Scenario: Tracker — the experiments lens lists the lane's experiments with badges
**Given** `evaluate`'s experiment recorded on `main`, and lane `exp` forked from `main` where `evaluate` was a memo hit
**When** the experiments lens is opened on each lane, and again after the experiment is deleted in the tracker
**Then** before the deletion both lenses list that one experiment as `ok`, `exp`'s row carrying the tag of `main`, the lane that recorded it; after it both list it badged *removed*, and no other row changes.

## Scenario: Download — a model downloads through the browser
**Given** `train_model.model` materialized
**When** the user clicks download
**Then** the browser receives `train_model.model.pkl` as an attachment, no file appears in the workspace, and `git status` is clean.

## Scenario: Download — kinds map to extensions
**Given** outputs of kind `frame`, `plot` (PNG), `note`, `file` (original `report.csv`)
**When** each is downloaded
**Then** the filenames end `.arrow`, `.png`, `.md`, `report.csv` respectively; downloading an experiment output answers 404 with a sentence, and so does a request naming a lane the flow does not have.

## Scenario: Download — the CLI refuses to overwrite
**Given** `./train.model` exists
**When** `lumlflow asset download train.model --to ./train.model` runs
**Then** it refuses naming the file; with `--force` it overwrites; the path the CLI sent was absolute, resolved against the shell's directory and not the daemon's; a relative `to` sent straight over the socket is refused with a sentence; and `asset.download` posted to the HTTP door with a valid token — with `to`, and again without it — is refused with a `FlowError` sentence and writes nothing anywhere, the daemon's working directory included.

## Scenario: Reactivity — a forked lane refreshes
**Given** lane `sweep` forked from `main`, not checked out, `auto` with a 60 s threshold
**When** `score` is edited on `sweep`
**Then** `score` and `report` run on `sweep` attributed to `auto`, `main` is untouched, and `cells/` on disk is unchanged.

## Scenario: Reactivity — one bad target does not stop the sweep
**Given** `alpha` consuming `nowhere.summary` and `zeta` both stale on `auto`
**When** the sweep runs
**Then** `zeta` runs; `alpha` is never submitted — its auto line declines naming `nowhere.summary`, a verdict computed from the store, so the sweep journals no transaction for it — and a second sweep changes nothing.

## Scenario: Reactivity — a kernel start failure is visible
**Given** a workspace whose interpreter cannot start
**When** the reactor sweeps
**Then** each target shows *could not refresh: <sentence>* on its card, the feed records it once (one `system` transaction per target holding a *refresh failed* cell note, no new version), a second sweep with nothing repaired adds no second transaction, and the reason is in the journal — the sweep prints no traceback as its only record; after a daemon restart the note is still in the feed but no longer declines, and the next sweep submits the targets again — each one that fails again gets one new note.

## Scenario: Reactivity — fixing the cause lifts the decline
**Given** every target on a lane declined with *could not refresh* after a kernel start failure, and no cell edited since
**When** the interpreter is repaired and the kernel is restarted — or, separately, an environment change is journaled on the flow, or one declined cell is run explicitly
**Then** the next sweep submits the declined targets again (in the explicit-run case, that cell and what its result makes stale), the cards drop the reason, and a target that fails again gets one new note.

## Scenario: Reactivity — the refreshing state
**Given** a cell edited on a lane under `auto`
**When** the reactor takes it
**Then** the card shows `refreshing` until `started`, then `running`.

## Scenario: Reactivity — wording and summary
**Given** one unmaterialized cell, one never-timed stale cell, one cell over the threshold, and one blocked by a failed parent
**When** the workbench renders
**Then** the auto lines read *never run yet — run it once to enable auto-refresh*, the never-timed line, *too expensive*, and *blocked* naming the failed parent and saying an edit to it unblocks; the top bar counts one of each gate.

## Scenario: Reactivity — archived lanes are skipped
**Given** an archived lane with stale cells under `auto`
**When** the reactor sweeps
**Then** no run happens on it.

## Scenario: Pipelines — run with no target
**Given** the churn flow with `load_data` edited
**When** `lumlflow run` runs with no target
**Then** the stale closure up to the leaves runs, synced cells are pruned, and the exit code is 0; with one cell failing, the summary names it and the exit code is 1; and on a lane with nothing stale or unmaterialized, nothing runs, the summary says there was nothing to do, and the exit code is 0.

## Scenario: Pipelines — a daemon started by the verb is stopped
**Given** no daemon running
**When** `lumlflow run` runs in CI
**Then** on exit no lumlflow process remains; with `--keep-daemon` it does; a `run` that found a daemon leaves it running; and `lumlflow agent begin` with no daemon running leaves the daemon it started alive, so the following `lumlflow agent end` finds the same session.

## Scenario: Pipelines — run leaves a daemon others attached to
**Given** no daemon running
**When** `lumlflow run` starts one and, while the pipeline runs, `lumlflow ui` opens a browser on it — or an agent leases a session against it, or a shell opens another flow — and the run then exits
**Then** the daemon is left running, `run` prints one line saying so, its exit code still reports the run's outcome, and the browser, the session and the other flow are undisturbed; with nothing attached, it is stopped as in the previous scenario.

## Scenario: Pairing — detection and setup
**Given** `claude` on PATH with its verified user-level config file present and no other harness
**When** the Agents section opens
**Then** Claude Code is listed *not set up*; after consent and **Set up**, that file holds a `lumlflow` entry — the command, the `mcp` argument and nothing after it, the ownership marker — every other key intact, a `.bak` beside it, and the panel says *approve the server when Claude Code asks*.

## Scenario: Pairing — nothing is written into the repository
**Given** any setup or sync run
**When** the workspace tree is diffed before and after
**Then** no file under the workspace changed except `<name>.flow/.gitignore` on flow creation.

## Scenario: Pairing — an unparseable config is left alone
**Given** `~/.cursor/mcp.json` with a syntax error
**When** **Set up** is pressed for Cursor
**Then** the file is unchanged and the panel shows the snippet and the path to paste it into.

## Scenario: Pairing — a missing config file is created
**Given** `codex` on PATH and neither `~/.codex/config.toml` nor its directory
**When** consent is given — the line naming that path — and **Set up** is pressed
**Then** the directory and the file are created holding the one `lumlflow` entry in the TOML shape with its ownership marker under the table, no `.bak` exists because there was nothing to back up, and the harness reads *set up*.

## Scenario: Pairing — sync after an upgrade
**Given** an entry written by an older lumlflow at a path that no longer exists, for a harness whose consent is on record
**When** `lumlflow ui` starts the daemon
**Then** the entry is rewritten with the current executable and marker without a prompt and the harness shows *set up*; if the file has meanwhile stopped parsing, or parses but is not writable, nothing is written and the harness shows *out of date* with **Update** and the snippet; an entry the user deleted shows *removed by you* and is not re-added.

## Scenario: Pairing — a desktop app uses the one entry
**Given** Claude Desktop detected and set up, and flows in two directories
**When** the agent calls `status` with each directory, `init-flow` with one of them, and `context` on a flow named by its path
**Then** the config holds one `lumlflow` entry naming no directory, each `status` lists only the flows beneath the directory it was given, the flow is created where asked, and the path-named flow opens in the one daemon.

## Scenario: Pairing — a harness without a verified config ships detect-only
**Given** a harness on PATH whose registry entry records no verified config path or shape, and no verified environment marker
**When** the Agents section opens and a bare `lumlflow cells edit` runs from that harness's shell
**Then** the harness is listed with the snippet and its documented path and no **Set up** button, consent is never asked and nothing is written; the edit's transaction carries the actor `user`.

## Scenario: Pairing — consent declined, and Remove
**Given** Claude Code detected and listed *not set up*
**When** the consent line is declined, and later — after a completed setup — **Remove** is pressed
**Then** on decline nothing is written and the harness stays *not set up* with no consent recorded; on Remove every entry lumlflow owns leaves `~/.claude.json`, every other key is intact, the harness reads *not set up*, and the next **Set up** asks for consent again.

## Scenario: Pairing — the agent is told, never handed a file
**Given** an MCP client connecting
**When** it reads the `initialize` result and `lumlflow://guide`
**Then** the instructions name `context` first and the guide, say that an edit on the checked-out lane is written to `cells/` at once and that `use`/`rewind`/`adopt` rewrite it, and no longer claim that nothing writes files, the guide holds the cheatsheet with the tracker sentence, and no `AGENTS.md` or `CHECKOUT.md` exists in the workspace; `lumlflow guide` prints the same text; after a `rewind`, `context` names that rewind as the last rewrite of `cells/`.

## Scenario: Pairing — shell attribution
**Given** a bare `lumlflow cells edit` run from a Claude Code shell
**When** the transaction is journaled
**Then** its actor is the harness's registry id, `claude-code` (or `LUMLFLOW_ACTOR` when set), the activity feed shows the edit under that name, and the pair line is unchanged because no session was registered; the same harness connecting over MCP with `clientInfo.name` matching the registry entry is labelled `claude-code` too, so the feed shows one agent under one name.

## Scenario: Readiness — frontend CI runs
**Given** a pull request touching `lumlflow/frontend/src/**`
**When** CI runs
**Then** a job builds `@luml/experiments` and `@luml/attachments`, then runs `vue-tsc --build`, `eslint` without `--fix`, `vitest run` and `vite build` for `lumlflow/frontend`; a type error fails the PR, and so does a lint error the `--fix` script would have rewritten.

## Scenario: Readiness — first run stores a frame
**Given** `uv tool install lumlflow` and a directory created as the quickstart says (`uv init`, `pandas` and `pyarrow` added); separately `pip install lumlflow` into an environment that also holds pandas, and an empty directory; and in each a cell returning a DataFrame
**When** the cell runs
**Then** under the quickstart the kernel runs on the project's venv and the frame is stored; under the shared environment it runs on lumlflow's interpreter and the frame is stored (pyarrow rides with lumlflow); and in a project venv holding pandas but not pyarrow, the run fails naming `pyarrow` as the package to install into that env.

## Scenario: Readiness — missing uv is a sentence
**Given** no `uv` on PATH and a workspace with `pyproject.toml`
**When** the kernel would sync
**Then** the verb fails with a `FlowError` naming `uv` and the Packages panel says *no uv-managed environment here*.

## Scenario: Readiness — --host is back
**Given** `lumlflow ui --host 0.0.0.0`
**When** the daemon starts
**Then** the web listener binds `0.0.0.0`, the flow API still requires the token, the printed URL carries it, `lumlflow ui` prints the one-sentence warning at start and `doctor` repeats it while the daemon is bound that way, and `lumlflow ui --help` says in one sentence that the tracker API on that port is unauthenticated on a non-loopback bind; on the default loopback bind neither prints it.

## Scenario: Readiness — a store at another version names both
**Given** a journal whose `FlowInit.schema_version` is 3 while the running lumlflow writes 2, and separately one stamped 1 by a pre-release build
**When** each is opened
**Then** the first is refused with a sentence naming 3 and 2 — not "corruption"; the second is refused with a sentence naming 1 and 2 and telling the user to delete `<name>.flow/.lumlflow/`, after which the flow re-initialises from `cells/` and `flow.yaml`; and a journal carrying an op this lumlflow does not know is refused naming the op.

## Scenario: Readiness — doctor, logs, gc
**Given** a running daemon and a directory holding flows
**When** `lumlflow doctor` and `lumlflow gc` run there
**Then** doctor prints the state directory, the one record, the lock state, the handshake result, log path, interpreter and source, tracker store, disk usage of the flows beneath the directory and owned harness entries; gc reports bytes reclaimed, and a value produced by a run in flight is never removed; the log directory holds at most the configured number of rotated files; and the traceback of an unexpected error on the HTTP door is in that log file and not on the `lumlflow ui` terminal.

## Scenario: Readiness — the demo runs on its own environment
**Given** the demo directory `examples/churn/`, holding `churn.flow/` and a `pyproject.toml`
**When** the interpreter is resolved for that flow
**Then** the walk-up from the flow's containing directory resolves `examples/churn/pyproject.toml`, not `lumlflow/pyproject.toml`, with no network, and the built sdist and wheel hold no `examples/` entry.

# Tasks

- [x] Remove the legacy frontend prototype and fixture pages
  - [x] Delete `src/flow/{engine,types}.ts`, `fixtures/`, `components/`, `composables/`, `concepts/` (move `CONCEPT.md` to `lumlflow/docs/`), the `flow-railroad` route, `FlowShell`'s fixture select and `FlowTabs`' railroad entry, `tests/flow-concepts.spec.ts`
  - [x] Delete `pages/{FixtureWorkbench,FixtureCompare}.vue`, `pages/useWorkbenchState.ts`, the `?state=`/`?source=` arms of `live/source.ts`, and the fixture branches of `WorkbenchPage.vue` / `ComparePage.vue`
  - [x] Register `flow-design` only under `import.meta.env.DEV` (its import is already dynamic); verify `vite build` output holds no fixture or gallery chunk
  - [x] Update `flow-workbench-ui.spec.ts` (its fixture-page cases go; its *pairing hands over a prompt* block stays until the task that removes the prompt) and any spec that imported removed modules; `vue-tsc`, `eslint`, `vitest`, `vite build` green
- [x] Add frontend CI for lumlflow-ui
  - [x] Add a job to `.github/workflows/[lumlflow] tests-and-linters.yml` (trigger `lumlflow/**`): `npm ci`, build `@luml/experiments` and `@luml/attachments`, then `vue-tsc --build`, `eslint` without `--fix` (the package's `lint` script fixes in place; add a CI script or call the bare command), `vitest run`, `vite build` in `lumlflow/frontend`
  - [x] Fix whatever `vue-tsc` and `eslint` find on the current tree — neither has ever run in CI — so the job passes; that fixing is in this task's scope
- [x] Remove the sandbox and safety modes
  - [x] Delete `daemon/sandbox.py`, the spawn wrapping in `kernel_proc.py`, the `sandbox`/`paranoid`/`strict` settings and their threading to the executor and REPL; keep `_restored`; drop the `sandboxed` line in `render.py` and the sandbox half of `_kernel()`
  - [x] Remove `tests/daemon/test_safety.py` and other references
- [x] Remove the cloud upload queue and SDK scaffolding
  - [x] Delete `daemon/uploads.py`, `api.promote`, `uploads.sync()` on `run`, `hub._scaffold_sdk`, `envs.ensure_sdk`, `FlowSession.declares_native`, `LumlUploader` wiring in `main.py`; delete the two upload ops, `OutputRecord.luml_ref` and the `uploaded` field `queries` derives from it
  - [x] Remove the CLI `promote` verb, the UI *promote to LUML* item, the `uploaded` badge and its model field, and the `uploaded` chips `useCompare` feeds `ArtifactLinks.vue` (`ExpandDrawer` has no cloud link to remove); leave `ArtifactLinks.vue` in place, rendering its rows without chips, for the tracker rewrite
  - [x] Delete `tests/daemon/test_uploads.py` and the five `ensure_sdk` tests in `test_envs.py`; add a test that a `model` run journals no upload and touches no lockfile
- [x] Remove secrets, env writes and env_policy
  - [x] Delete `daemon/secrets.py`, `api.secrets_*`, `lumlflow secrets`, `ctx.secret`, `secret_get` and the kernel→daemon request channel it rode on (`kernel_proc._serve` and the kernel's request side), `SecretRefAdded`, `Ctx.secret` in `lumlflow_typing`
  - [x] Delete `envs.add/remove`, `api.env_add/env_remove`, `lumlflow env add/remove`, the Packages panel add/remove rows
  - [x] Delete `env_policy` (setting, `settings.set`, `PanelSettings` control, the `auto` restart path); hard-code the banner-plus-restart behaviour
  - [x] Update tests
- [x] Remove retired aliases
  - [x] Delete CLI `fork/switch/tree/archive`, the `variant` group, `--variant/--branch/--unsynced`, `mcp._RETIRED_NAMES` and the `variant` wire aliases; the `daemon` group is untouched here (the one-daemon task unhides `stop` and `status`)
  - [x] Update `test_cli.py` / `test_mcp.py`
- [x] Remove focus, asset diff, the dev shim and the sidecar
  - [x] Delete `api.set_focus`, `session.focus` and its one reader `handoff._focus`, `session://focus`, the `useSelection` focus reporter, `api.asset_diff` and `lumlflow asset diff`, `_refresh_web_app` and helpers in `lumlflow/cli.py`, `docs.refresh_checkout` and `CHECKOUT.md`
  - [x] Update the affected tests
- [x] Shrink handoff to one copy-context gesture
  - [x] `agent.payload` without a gesture parameter, carrying the traceback's frames and the exception's final line, never its full text (D4.11); one button per card; delete `HandoffPopover`/`HandoffDialog`
  - [x] Update `test_handoff.py` (the payload rule included) and `flow-handoff.spec.ts`
- [x] Add the cell-note journal op
  - [x] The `CellNoted` op of D2 (uid, note kind, sentence, optional version) with its index by (lane, uid, kind, step), its replay, and its exposure on `cells.show` (latest note per kind: kind, sentence, version, step, actor); the journal schema version constant raised from 1 to 2; nothing emits it yet
  - [x] Tests in `tests/flow`: replay and index of a note, the latest note per kind per (lane, uid)
- [x] Tolerate store version skew
  - [x] Per D11.4: journal ops and transactions ignore unknown fields on read; the manifest and settings preserve unknown keys on read and write them back unchanged; `open` compares `FlowInit.schema_version` with the running constant — a newer version or an unknown op type refused naming both numbers (or the op), an older version refused naming both and telling the user to delete `<name>.flow/.lumlflow/`
  - [x] Tests in `tests/flow`: an unknown op field ignored; an unknown manifest and settings key preserved across a rewrite; a version-3 store refused naming 3 and 2; a version-1 store refused with the re-initialise sentence; an unknown op refused naming it
- [x] Drop the worktree lock and deferred projections
  - [x] Remove `Worktree.guard/holder/deferred/pending`, `WorktreeLocked`, the `force` parameter the API reads on `cells.delete`/`import`/`rename`/`rewind`/`switch`/`flow.checkout` (`adopt` keeps `force` as the `AdoptConflict` resolution and `cells.edit` as the `EditConflict` override), `reconcile._held_versions`, `_Pending.withheld` and its plumbing, the brief's `unwritten` key; remove the `AgentBegin.worktree` field; MCP no longer escalates to the worktree; `_complete_projections` keeps only its unlocked arm as it is today (lane-scoping is the next task's)
  - [x] Attribute reconcile-detected changes per D2: to the verb's caller only when that caller is not `user`; otherwise — watcher or `user` verb — to the one registered agent session when exactly one is registered, else `user`
  - [x] Tests: cell added / duplicated / imported under a registered agent is written at once and never journaled as deleted; agent `mv` after a UI edit keeps the user's head; a change found by the watcher or by the UI's `cells.list` under one registered agent is attributed to that agent, under two to `user`, and one found by an `agent exec` or `LUMLFLOW_ACTOR` verb to that actor; a stale `base` still raises `EditConflict` and `force` on `cells.edit` still overrides it; `adopt` with `force` still resolves a conflict
- [x] Scope projection completion to the lane and note it
  - [x] `_complete_projections` completes a projection only when the older version the file matches is on the same lane's lineage (D2); bytes matching another lane's version land as an offline edit; each completion is journaled as a *projection completed* `CellNoted` under `system` naming the cell and the restored version
  - [x] Tests: cross-lane bytes land as an offline edit on this lane with one transaction; a same-lane hand revert is completed, journaled as a cell note under `system`, and rewinding restores the older version
- [x] Remove lock-only force flags from the CLI and MCP
  - [x] Drop the `--force` options of `cells delete`, `import`, `rename`, `rewind` and the lane checkout verb, and the matching MCP tool arguments; `adopt --force`, `cells edit --force` and `run --force` stay; the CLI download's `--force` (D4.4) does not exist yet and is added by the slug-and-download task below
  - [x] Update `test_cli.py` / `test_mcp.py`: the flags are unknown options and the tools no longer declare the argument
- [x] Remove lock state from the workbench
  - [x] Delete `WorktreeLockNotice.vue`, the `pending`/`pendingProjection` state and the *saved · not yet written to files* wording in `LiveCellCard`/`CodeView`, and the `FlowBrief.unwritten` field of `api/types.ts`; confirm no `WorktreeLocked` reference remains anywhere in `lumlflow/` or `frontend/src`
  - [x] Update `flow-live-card.spec.ts` and `flow-workbench-editing.spec.ts`
- [x] Raise the kernel link and RPC door limits
  - [x] Set explicit stream limits (16 MiB) on the kernel link and the socket door (the HTTP door is untouched); treat a `readline` overrun on the kernel link as a run failure, not a dead link; answer `INVALID_REQUEST` on the socket door without dropping the connection
  - [x] Cap capture chunks at 32 KiB; clip REPL output and result at 64 KiB with a marker
  - [x] Tests in `tests/kernel` and `tests/daemon`: 200 000-character print, 200 KiB `edit-cell` over the socket keeping the session, oversized line refused politely
- [x] Refuse empty edits and keep card detail across refetches
  - [x] Daemon: `cells.edit` rejects empty/whitespace source with a `FlowError`
  - [x] Frontend: stale-while-revalidate in `useCell.ts`; disable *edit* / *apply suggestion* while no detail; always send `base`
  - [x] Tests: daemon regression; `flow-live-card.spec.ts` burst scenario
- [x] Harden reconciliation against unreadable files
  - [x] `accept_path` / `scan_workspace`: ignore `.#*` and `._*`, skip dangling symlinks and unreadable files, decode undecodable cells with an `invalid` flag naming the encoding; accept a UTF-8 BOM; fix the header-line-class uid insert
  - [x] Tests: Latin-1 cell, dangling symlink, permission-denied file in the tree, one-line class, BOM
- [x] Truncate a failed journal append
  - [x] `journal.append` leaves the file as it was on failure; `commit` re-derives the next step after a failed append
  - [x] Test with a monkey-patched fsync; the flow reopens
- [x] Evict workspace modules before the next run
  - [x] Module eviction becomes an evict-before-next-run flag, never queued behind a running cell
  - [x] Test: 60 s run + helper edit, `cells.list` answers while the cell is still running
- [x] Mirror socket-door errors on the HTTP door
  - [x] HTTP door mirrors the socket door's exception mapping (JSON 400 for `FlowError`, JSON 500 with the message otherwise, CORS headers on both, the traceback never in the reply); numeric params coerced through a `FlowError`-raising helper; the traceback goes wherever the daemon's exceptions go today until the logging task routes them to the rotated file
  - [x] Tests in `tests/daemon/test_web.py`: `to_step: "abc"`, a non-`FlowError` exception whose reply is JSON and holds no traceback
- [x] Validate slugs and harden the CLI download path
  - [x] Slug rule shared by `cells.new`, `rename`, `import`; assert paths under `cells/` in acceptance and projection; `rename` to a taken name raises
  - [x] `asset.download` refuses to overwrite without `force` and refuses a relative `to`; CLI `--force`, the CLI keeping its absolute `--to` (or its cwd) as today; the HTTP door refuses the `asset.download` method outright, with or without `to`
  - [x] Tests: `../../escaped`, `../out`, empty `to`, an import carrying a path-shaped cell name, taken name, overwrite refusal, a relative `to` over the socket refused, HTTP refusal with `to` and — writing nothing into the daemon's cwd — without it
- [x] Fix lane semantics for adopt, delete, import and clashes
  - [x] `adopt` of a renamed cell rewires consumers by uid; `cells.delete` re-accepts dangling consumers on any lane; `import` rewires after carrying; uid recovered from text when the AST fails; forced-adopt clash resolved deterministically with the adopted uid re-accepted
  - [x] Tests in `tests/daemon/test_api.py` / `test_reconcile.py`: adopt of a renamed cell keeps consumers synced; delete on an off-disk lane flags consumers; an import rename rewires and a mid-edit `mv` keeps the uid; a forced adopt clash is deterministic
- [x] Fix scheduler stop, replan and force
  - [x] A stop that arrives while the kernel is starting ends the run `cancelled` (`kernel_proc.py`, `queue.py`); a step whose selected version moved mid-plan is re-planned or abandoned, never run from the superseded version; `force` never joins another lane's flight
  - [x] Tests in `tests/flow/test_queue.py` and `tests/daemon/test_api.py`: stop during kernel start, edit mid-plan, force never joins another lane's run
- [x] Derive the workspace-code cause from the tree hash
  - [x] The workspace-code staleness cause (`staleness.py`) derives from the tree hash the materialization ran under, not from steps
  - [x] Tests in `test_staleness.py`: A→B→A leaves nothing stale
- [x] Move the churn demo beside its own pyproject
  - [x] Move `churn.flow` to `lumlflow/examples/churn/` beside a `pyproject.toml` declaring its dependencies (scikit-learn, matplotlib, pandas, pyarrow, luml-sdk); exclude `/examples` from the sdist; the demo's cells either pass `ruff` or `examples/` is excluded from its scan (`mypy` and `pytest` already take explicit paths); confirm the nested `pyproject.toml` is not picked up as a `uv` workspace member
  - [x] Tests: the built sdist and wheel hold no `examples/` entry; every reference to the old path (tests, docs, the README) points at the new one
- [x] Root each flow in its containing directory
  - [x] A flow's workspace is its parent directory: `ctx.workspace_dir`, run cwd (scratch only for `tempdir()`/staging), scan and watcher root; `hub._workspace_of` answers the containing directory for every flow — its branch on the daemon's root and the outside-the-launch-directory special case go here, while the root itself still serves daemon discovery until the one-daemon task — the `Watches` registry stays; interpreter resolution walks up from the flow's directory, an existing `.venv` never synced
  - [x] `EXCLUDED_DIRS` extended (pyvenv.cfg, site-packages, env/venv/.tox/build/dist, `.gitignore`)
  - [x] Tests: cell cwd and `ctx.workspace_dir`, interpreter walk-up (an existing `.venv` unsynced, a `pyproject.toml` alone synced) and the own-interpreter fallback, nested roots, venv exclusion, an unreadable file elsewhere in the tree skipped
- [x] Key the worktree binding by flow id
  - [x] The binding is keyed by the flow id rather than the absolute path (`WorktreeBound`, the index's worktree lookup); a store with history but no binding for its location rebinds to the last bound lane, never `main`
  - [x] Tests: moved workspace keeps the checked-out lane and never falls back to `main`
- [x] Restore the ui host option
  - [x] `lumlflow ui --host` (default `127.0.0.1`), the web listener bound to it and the host recorded beside the port in the daemon record; the token required on a non-loopback bind as on loopback; the help text carrying the one-sentence non-loopback warning of D11.3, and `ui` printing it at start on a non-loopback bind
  - [x] Tests in `tests/daemon/test_ui.py` and `test_cli.py`: the bind and the recorded host, the token still required, the warning printed on a non-loopback bind and not on loopback, the help sentence
- [x] Serve every flow from one daemon
  - [x] One record in the state directory — pid, instance id, socket address (the loopback TCP port of the RPC door, as today), web token, web host and port, tracker store, version, mode 0600 — and one lock file, opened non-inheritably and held for the daemon's life (`WorkspaceLock`'s mechanism, keyed by nothing); the two roles of D3: the daemon role — the only code that opens the lock file: take it and write the record, bind and serve, or exit with the *someone is there* code — run in-process by `ui` and by the daemon process a verb or `lumlflow mcp` spawns, and the caller role — read the record, ping for the instance id, unlink a stale record and start the daemon (in-process for `ui`, spawned for a verb or `lumlflow mcp`) then wait for a record whose ping answers, retry-then-sentence naming the log path and `lumlflow daemon stop` for a held lock that does not answer; a web bind failure as an error naming the port; a background daemon binding loopback and the default web port, an ephemeral one when it is taken, and resolving its store by `ui`'s rules; a state directory on a network filesystem warned about at start, never refused
  - [x] Delete `resolve_root`, `registered_roots`, the per-root record keying and per-root log name, `client.live_record` / `stand_down` and the record's `foreground` flag, the daemon module's and `lumlflow mcp`'s `--workspace` options and `lumlflow root`; `daemon start/status/stop` act on the one daemon, `stop` signalling the recorded pid only while the lock is held and otherwise unlinking the record and saying no daemon was running, `stop` and `status` shown in `--help` and `start` still hidden; the hub keeps sessions by path with no root; `ui` starts the one daemon in the foreground or attaches to the one answering — its refusals, port reporting and Ctrl-C line are the next task's
  - [x] Tests in `tests/daemon/test_supervisor.py`, `test_ui.py` and `test_workspace.py`: the surviving supervisor tests (D1) reworked to one record; `kill -9` then a clean start, and `daemon stop` against the stale record signalling no pid; two callers resolved by the lock with one daemon process left; a held lock that does not answer named with the log path after retries; a kernel outliving a dead daemon holding no lock; a background daemon on the default port, on an ephemeral one when it is taken, and on the store the environment names; the network-filesystem warning; the help pages naming `daemon stop` and `daemon status` and not `daemon start`; the takeover, stand-down, per-root record and root-resolution tests deleted
- [x] Make lumlflow ui a view over the one daemon
  - [x] `lumlflow ui [dir]`: when a daemon answers, print the recorded URL, open the browser (`--no-browser` only prints) and exit; refuse a `--path` — or an environment-resolved store — or a `--host` that differs from the record with a sentence naming the running settings and `lumlflow daemon stop`; say which port is serving on a different `--port`; when none answers, start in the foreground as today, and on Ctrl-C with other clients attached — leased sessions, stream subscribers, other open flows — say so on one line and still stop
  - [x] Tests in `tests/daemon/test_ui.py`: `ui` attaching to a verb-started daemon carrying a run and a session; refusing a conflicting store and a conflicting host; reporting the serving port on a different `--port`; the Ctrl-C line with a client attached, and the stop completing
- [x] Address flows by path everywhere
  - [x] The API's `flow` parameter, `brief.path`, the workbench route, the compare page, the download route and every MCP call after `flow.open` (`mcp.py`) address a flow by its absolute path; a bare name resolves against the flows beneath the caller's cwd — the MCP server's spawn directory — with ambiguity refused naming the paths; `status` and `init` / `flow.init` take a directory defaulting to the cwd (`gc` and `doctor` take the same directory when their own tasks land them), and the MCP `status` and `init-flow` tools gain an optional directory argument (D3)
  - [x] Tests: two same-named flows over MCP in one session; a bare name matching two flows refused naming both paths; `status` listing only the flows beneath the given directory; `init-flow` with a directory
- [x] List the launch directory on the landing page
  - [x] Remove `WorkspacePage.vue` browse-up and `workspace.listing/_within/_flow_crossed` (the `hub._workspace_of` special case went with the rooting task); the landing page lists the flows beneath the directory `ui` was given — the listing method takes the directory, and the address `ui` opens carries it — plus *New flow*, which creates there; the listing is a filter, and a flow opened by path from elsewhere opens in the same daemon
  - [x] Replace `flow-workspace-browser.spec.ts` with a listing spec; daemon test for the landing listing of a given directory
- [x] Fix lane and flow addressing in the workbench
  - [x] Brief refresh on checkout and rewind; compare by `brief.path`
  - [x] Specs in `flow-live-workbench.spec.ts`, `flow-compare.spec.ts`, `flow-branch-nav.spec.ts`
- [x] Fix the token mirror, agent-ended banner and reconnect
  - [x] Token excluded from mirrored query keys; agent-ended banner counting only `agent_end` transactions newer than the cell's last change; toast guard re-armed on reconnect; `open` marks reachable
  - [x] Specs in `flow-live-session.spec.ts`, `flow-live-workbench.spec.ts`, the banner count among them
- [x] Keep drafts across runs and select cards without scrolling
  - [x] Editor survives the running tab switch; "save to a new lane" via the dialog with the draft kept; controls on unselected cards select without scrolling or panning, the URL mirror rewriting only on a real selection change and a press on the selected card reporting nothing
  - [x] Specs in `flow-live-workbench.spec.ts` and the canvas/notebook specs, the press-without-scroll and the unchanged URL among them
- [x] Bound kernel pages and previews
  - [x] Page rows through an unclipped cell normaliser; a serialisation failure after the page handler returned becomes an error reply, never a timeout (`rpc.py`); page column bound and `total_columns`; per-block `_shrink` strategies
  - [x] Frame flavor recorded in the Arrow schema metadata and honoured on deserialize
  - [x] Tests in `tests/kernel/test_kinds.py` and `test_rpc.py`, including a polars round-trip with pandas installed
- [x] Fix console, frame footer and metric rendering
  - [x] Frame footer with column totals; ANSI/`\r` handling and a bounded console buffer; non-finite metric values carried in the preview as the strings `"nan"`/`"inf"`/`"-inf"` (kernel preview side) and rendered as such, distinct from absent; scientific `formatMetric`; paging from row 0
  - [x] Renderer specs; a kernel preview test that a NaN metric survives the HTTP door as a string
- [x] Sanitize notes and fix export and cursor noise
  - [x] Note sanitizer forbids `style`/`form`/`input`/`button`/remote images; export/import mints no version for zero or two trailing newlines; `flow.open` / `status` return the store's `flow_id` in the brief and the workbench's brief type gains it (D4.10); both journal cursors (the high-water mark in `api/stream.ts`, the marker in `workbench/live/cursor.ts`) reset when the brief's `flow_id` differs from the one the cursor was recorded under
  - [x] Tests: renderer spec, `tests/daemon` export/import, the brief carrying `flow_id`, and a session spec for the cursor reset
- [x] Add ephemeral state frames to the journal channel
  - [x] Daemon: a `state` frame type on the journal channel (D6.5) carrying the state's name, the flow, the lane and cell where it concerns one, and the flow's current step; never journaled, never replayed, dropped when no client is connected; a hub-side push the later tasks call with `experiment_removed`, `refreshing` and `order_changed`
  - [x] Client: `useFlowSession` delivers state frames to subscribers, leaves the replay cursor unmoved, and keeps them out of the transaction and catch-up paths
  - [x] Tests in `tests/daemon/test_stream.py` and `flow-live-session.spec.ts`: a pushed frame reaches a subscribed client with the cursor unmoved; a reconnect replays no state frame; a frame for another flow is ignored
- [x] Add the order key and anchored adds
  - [x] Manifest `order` map (top-level); decimal keys in the step domain, a new key the midpoint of its neighbours' effective keys — the next journal step standing in for a missing larger neighbour — written unrounded, no renumbering ever; stray, unparseable and duplicate entries handled per D5.1; `cells.new` `anchor` resolved on the target lane (with `after` implying it; an unknown or other-lane anchor refused; an unanchored add writes no entry); key dropped when no lane selects the uid and not restored by rewind; `order` in `cells.list`/`cells.show`; CLI `cells new --anchor`; MCP `anchor`
  - [x] Tests: `tests/flow/test_flowstore.py` (manifest, stray entries, mixed mapped/unmapped order), `tests/daemon/test_api.py` (anchor, unknown and other-lane anchor, persistence across rename, key dropped on delete and not restored by rewind)
- [x] Add cells.reorder with its CLI and MCP verbs
  - [x] `cells.reorder` (slug, lane, `before`/`after`) with the topology check against the called lane — refusing a position that would leave any cell there before one of its producers, the moved cell or a consumer of it — and a refusal for a cell the lane does not select, its reply carrying the cell's slug, uid and new `order`, and an `order_changed` state frame pushed on the journal channel; CLI `cells move --before/--after`; MCP `move-cell`
  - [x] Tests: `tests/daemon/test_api.py` (per-lane reorder refusal, reorder on an archived lane, the frame pushed with no transaction and the cursor unmoved), `test_cli.py` (`cells move`), `test_mcp.py` (`move-cell`)
- [x] Order the notebook by the key
  - [x] Priority = effective key in `topologicalOrder`; *move up* / *move down* menu items gated by topology, calling `cells.reorder`; the issuing tab applies the reply's `order` at once and every tab refetches its slice on an `order_changed` state frame; the UI passes the selection as `anchor`
  - [x] `flow-workbench-model.spec.ts` (order, insertion never reflow) and a session spec for the refetch on `order_changed`
- [x] Make the canvas layout incremental
  - [x] Top-aligned columns, (barycenter, key) rows, parentless placement under the preceding cell, incremental positions with a **tidy** control that alone recomputes the whole layout, `fitView` on first load only, input-name edge ids, minimal viewport pan
  - [x] A canvas layout spec (no existing node moves on add; blank add lands under the selection; tidy recomputes; `fitView` once on load and not on an add)
- [x] Wire one output downstream and clean the slug index
  - [x] `cells.new` after → the first non-`experiment` output by the primary ranking, the experiment itself when it is the only output; `primary_output` unchanged; `outputs: all` / `--all-outputs` / `all_outputs` for everything; duplicate toast wording
  - [x] Drop deleted slugs from `flow.yaml` when no lane selects the uid; placeholder numbering from the largest ever minted; a rewind that re-selects a dropped uid re-adds its slug; remove the five ghosts from `examples/churn/churn.flow/flow.yaml`
  - [x] Tests: downstream wiring (model + experiment producer, experiment-only producer), slug-index cleanup and placeholder numbering, including a rewind after a delete re-adding the slug to the index
- [x] Share one tracker provider with the Experiments API
  - [x] The provider of D6.1 for the daemon's read side and the delete hook, resolved by the daemon and by every `lumlflow/api/*.py` handler singleton — eight modules, each capturing the process-cached `settings.get_tracker()` at import, so either they resolve through the provider or that cache is reset with it, else the ones a fixture does not patch still open the developer's store — with its in-process *experiment deleted* hook; the provider's store path is the one the daemon hands the kernel (D6.2, D6.6); an autouse fixture in `tests/daemon` binding it to a per-test store — `test_web.py`'s opt-in `experiments` fixture, which patches two handlers by hand, goes — and a tracker parameter on the `daemon_api` helper, so no daemon test, one that runs an `experiment` cell included, can reach the developer's store
  - [x] Tests: every tracker router answers from the per-test store; the hook fires on a delete through the Experiments API; an `experiment` cell run under the fixture writes the per-test store
- [x] Write the tracker from the kernel through the SDK
  - [x] Kernel: `ctx.tracker` as a thin wrapper over the SDK's `ExperimentTracker` opened on the store the daemon names (spawn environment or run payload), the SDK imported lazily and only for a run declaring or consuming an `experiment` output; the four cell-facing methods and `record` source-compatible, the metric methods gaining an optional step, every logged value one `log_static`/`log_dynamic` write in order; the executor starting the experiment before `materialize` (name, group, tags and metadata — the flow's path included — from the run payload's identity fields; static params from the declared `params`), ending it on success, failing it on failure and cancel; the experiment id and store reported as soon as the experiment is started and again, with a close failure, in the `materialized`/`failed` events; the snapshot kept from the logged calls and seeded from the declared `params`, `record` still returning today's shape until the next task; `lumlflow_typing.Ctx.tracker` and the `tempdir` type
  - [x] Tests in `tests/kernel`, against a temporary store: one experiment per run with metadata — the path included — and declared params; `completed` on success, `error` on failure and on cancel; the id and store reported before the cell's code runs; per-step metrics in the history in order while the cell is still running; a run that neither declares nor consumes an experiment never imports the SDK; `evaluate.py` runs unchanged with `alpha` logged
- [x] Serialize experiment refs and hash the snapshot
  - [x] `record` returning the `ExperimentRef` (id, group name, store, snapshot); `ExperimentKind` serializes only refs, previews the snapshot, hashes the snapshot; the undeclared-use and wrong-value rules (the more-than-one check is the daemon task's, at planning)
  - [x] Tests in `tests/kernel`: the ref round-trips through the kind with the snapshot as its preview; identical numbers prune consumers; wrong value and undeclared use fail with sentences; `evaluate.py` still runs unchanged
- [x] Surface SDK import, store and version skew in the kernel
  - [x] A failed SDK import failing the run before the cell's code executes with a sentence naming `luml-sdk`; the busy-timeout retry above `sqlite3`'s default wait, its bound one module constant, a write that still fails failing the run with a sentence naming the store path, an unwritable store the same; a write or open the SDK itself refuses failing the run with the SDK's own sentence, the store path and the venv's SDK version beside it; the SDK version the daemon hands beside the store compared with the imported SDK's before the first write, a difference emitting one warning naming both versions and the venv into the run's console and logs and onto the run's events, the run proceeding (D6.6)
  - [x] Tests in `tests/kernel`: a run declaring an experiment output names `luml-sdk` when the import fails; an unwritable store and a lock held past the timeout fail with the store path, a lock released within it succeeds; an SDK refusal carries the SDK's sentence and version; a version mismatch warns in the console and on the event and the run succeeds, a match warns nothing
- [x] Record tracker refs and fail orphaned experiments
  - [x] Daemon: the store path and the version of the SDK the daemon imports in the spawn environment (or run payload) and the identity fields — the flow's absolute path included — in the run payload; the one-experiment-output check at planning, before the kernel is asked; the experiment id and store put on the run record the moment the kernel reports the start, and on the `OutputRecord` (`tracker_ref`) via `RunRecorded` from the `materialized` event, the run record keeping them for every outcome, and the kernel's version warning kept on it; a close failure reported by the kernel journaled as an *experiment unclosed* `CellNoted` under `system` carrying the sentence; a run whose kernel died recorded as failed with the experiment its start-time record names failed on the provider's tracker — the flow subsystem's one daemon-side tracker write; memo hits create nothing
  - [x] Tests in `tests/daemon`: the id on a failed run's record and in `cells.show`; two declared experiment outputs refused before any start; a failed close leaves the materialization, journals the note, and `cells.show` exposes it; a killed kernel — one that reported its start and nothing after — leaves an `error` experiment and a failed run naming it; the warning on the run record; memo hit creates none
- [x] Hand consumers a read-only experiment handle
  - [x] Consumers receive the read-only `Experiment` handle (`id`, `params`, `metrics`, `metric_history`) hydrated by the kernel from the SDK tracker's read calls at access time, without observation marks, the SDK imported lazily as for a producer and a missing SDK failing the consumer's run before its code executes with the sentence naming `luml-sdk`; a missing or unreachable experiment raises a sentence at access
  - [x] Tests: consumer handle values match the tracker; no `identity_dependent`/`external` mark; a consumer in a venv without the SDK fails naming `luml-sdk` before its code runs; access on a removed experiment fails the run with the sentence
- [x] Render dangling experiments and react to tracker deletes
  - [x] `queries` state detection (`ok`/`missing`/`unreachable`) with a per-session cache invalidated through the provider's *experiment deleted* hook, dropped on `flow.open` and reconnect, and re-checked past a bounded age — a store the daemon's SDK cannot read reading `unreachable` with the sentence naming the store, the writing SDK's version when known, and the lumlflow upgrade (D6.6); the hook pushes the `experiment_removed` state frame (the state-frame task's mechanism); planner treats a dangling `tracker_ref` like missing bytes for explicit runs with preflight wording, and `auto_verdicts` declines any `auto` target whose closure would demand the producer of a dangling `tracker_ref`, naming the removed experiment (D6.5) — the two land together, or a stale consumer under `auto` resurrects the deleted experiment in between
  - [x] Tests: a store the daemon cannot read reads `unreachable`, not an error, and one migrated forward by a newer SDK reads `unreachable` with the upgrade sentence while the run that wrote it stands; delete flips preview state without a journal transaction and without moving the client cursor, a reconnecting client re-derives the state, an SDK-side delete from another process is seen after the bounded cache age and on `flow.open`, consumer preflight names the producer, a stale consumer under `auto` is declined naming the removed experiment and the reactor runs neither cell, different `--path` reads unreachable
- [x] Warn on deleting a flow-produced experiment
  - [x] The `lumlflow` metadata reaches the Experiments screen on the experiment payload or through a metadata read the tracker API gains; the delete confirmation in `lumlflow/frontend/src/confirm/confirm.ts` and its two callers under `src/components/experiments/experiment/` names flow, cell and lane
  - [x] Tests: the API read; a spec in `lumlflow/frontend/tests` for the confirmation text
- [x] Show tracker experiments in the workbench
  - [x] `tracker: {id, group, state, url, store}` on `cells.list`/`cells.show`/`asset.preview`, `url` null unless `ok`; `previewFrom` yields `experiment` for stored kind `experiment`; `ExperimentRenderer` live with the first logged metric as the headline, no direction arrow, and a routed link; `ExpandDrawer` state line replaces `href="#"`; the SDK-version warning the run record carries (D6.6) shown as one warning line on the card; no download/export on experiment cards
  - [x] Experiments lens lists the lane's tracker experiments with badges; `ArtifactLinks.vue` becomes tracker links fed by `useCompare`
  - [x] Specs: renderer with live data, drawer states, the warning line, lens (badges, a memo hit's experiment tagged with the recording lane), compare links
- [x] Stream asset downloads over HTTP
  - [x] Authenticated GET route in `daemon/web.py` addressed by flow path (query parameter, as `brief.path`), branch and `<slug>.<output>`, with kind→extension mapping and `Content-Disposition`; the kernel records a `file` output's original name on the output record through `RunRecorded`, with the `<slug>.<output>` fallback; 401 on a bad token, 400 for a bare flow name, 404 for an unknown path, an unstored value and an experiment output
  - [x] Workbench downloads through the route (`ExpandDrawer`, `FileRenderer`); drop *saved to `<path>`*
  - [x] Tests in `tests/daemon/test_web.py` (401, a bare name 400, an unknown path 404, extensions, unstored value, experiment 404) and a drawer spec
- [x] Sweep every lane and record refresh failures
  - [x] `Reactor._advance` iterates non-archived lanes; per-target guard for failures before the cell's own execution, journaling a *refresh failed* cell note (D2) under `system` on that lane with the *could not refresh* sentence; `auto_verdicts` declines on the latest note until it is lifted — a change of the cell's or an input's selected version, a workspace-code or environment change journaled after it, a kernel restart, or an explicit run of the cell — and a declined target is not resubmitted; unresolvable references declined by the verdict (the dangling-experiment decline is already in place from the dangling task); the `refreshing` state frame pushed on take
  - [x] `tests/daemon/test_reactive.py`: forked non-checked-out lane, an unresolvable reference declined without a transaction while the other target runs, kernel start failure (one note, none on the next sweep, the note still in the feed after a daemon restart and the target resubmitted), the decline lifted by a kernel restart / an env change / an explicit run, archived lane skipped, verdict/reactor agreement
- [ ] Show refreshing, gates and refresh failures on the card
  - [ ] Frontend: `refreshing` card state from the state frame; *could not refresh* from the cell note; auto-line wording for unmaterialized and blocked cells (naming the failed parent); top-bar gate counts; the feed shows the note as one line
  - [ ] Card and top-bar specs for the refreshing state, the wording and the counts
- [ ] Run a lane's leaves with no target and exit cleanly
  - [ ] `run` without a target plans the leaves (API, CLI, MCP); UI *rerun lane* uses it; CLI exit codes; a daemon that `run` itself started stops on exit unless `--keep-daemon` and only when nothing else attached meanwhile — a leased session, a stream subscriber or another open flow leaves it running with one line saying so (D8); every other verb (`agent begin` included) leaves one it started running
  - [ ] Tests in `tests/daemon/test_cli.py` / `test_api.py`, including `agent begin` → `agent end` across a daemon the first verb started, and a `run`-started daemon left running with a session leased, a stream subscribed and another flow opened meanwhile
- [ ] Add the harness registry and user-level MCP config writers
  - [ ] `daemon/harnesses.py` with verified entries (paths, shapes, cwd behaviour, environment markers — record the verification; a row whose config cannot be verified ships detect-only, with no writer); JSON `mcpServers`, VS Code `servers`, opencode `mcp`, and TOML writers that replace only owned entries, re-read before writing and skip when unchanged, write atomically, keep a `.bak` on first touch, create a missing file or directory, and refuse unparseable files; add `tomli-w`
  - [ ] Tests: per-harness round-trips on fixture configs, foreign entries preserved, unparseable refusal, an unchanged file untouched, a missing file and directory created without a `.bak`, one identical entry for a desktop app, out-of-date and broken detection, a detect-only entry with no writer
- [ ] Add the agents API and sync pass
  - [ ] API `agents.harnesses` / `agents.setup` / `agents.remove` and CLI `lumlflow agents list/setup/remove`; consent record in the state dir covering later automatic rewrites, cleared by Remove; sync on daemon start and on section open rewriting owned entries without a prompt, *out of date* with **Update** only when the rewrite could not be applied; missing config file or directory created; *removed by you* honoured; post-write hints
  - [ ] Tests: API states, consent declined writes nothing, Remove clears owned entries and consent, the sync pass rewrites an entry that names a directory to the one static entry, a detect-only harness listed with snippet and path and no setup, "nothing written under the workspace"
- [ ] Add the Agents panel section
  - [ ] An Agents section in the left panel replacing `PairLink.vue`/`connectPrompt.ts` (`components/session/`); the pair-an-agent buttons open it; the *pairing hands over a prompt* block of `flow-workbench-ui.spec.ts` goes here, with the prompt it tested
  - [ ] Tests: a panel spec; an end-to-end detected → set up → agent connects → panel shows label
- [ ] Serve the agent guide and attribute shell agents
  - [ ] MCP `instructions` (drop *nothing here writes files*; say an edit on the checked-out lane is written at once) and `lumlflow://guide` resource from `docs.CHEATSHEET` (updated for lanes, the tracker sentence, new verbs, and the MCP entry with no workspace argument); `lumlflow guide`; `context` pointer and its last-rewrite-of-`cells/` line; scaffold comment line
  - [ ] Delete `connect.py`'s prompt builder, `api.agent_connect`, `docs.refresh_workspace`, the `hub.document` calls, `lumlflow/AGENTS.md`, and `tests/daemon/test_connect.py`'s seven prompt-builder tests — its eighth, which spawns the executable and asserts the MCP `initialize` reply, moves beside the harness writers' tests since D9.2's entry command depends on it, spawning `lumlflow mcp` with no workspace argument
  - [ ] Actor precedence for bare verbs (`LUMLFLOW_ACTOR`, the harness's registry id on its environment marker, `user` — also for a harness with no verified marker); no session registered; the MCP label defaults to the registry id when `clientInfo.name` matches an entry, after `--label` and `LUMLFLOW_ACTOR`, which still win
  - [ ] Tests in `test_mcp.py`, `test_docs.py`, `test_cli.py`
- [ ] Fix packaging and dependencies
  - [ ] Drop `scikit-learn`/`matplotlib`, add `pyarrow`; frame serialization names `pyarrow` when missing; `uv` absence is a `FlowError`; Packages panel *no uv-managed environment here*
  - [ ] Tests: a new root-level test module beside `tests/test_packaging.py` (which covers only the hatch build hook) for the dependency set, `test_envs.py` for missing `uv`, a kernel test for missing `pyarrow`
- [ ] Add doctor and rotated daemon logs
  - [ ] Size-rotated daemon log for foreground and background daemons alike, with the path printed by `ui` and shown in the daemon-down banner; the daemon's exception tracebacks — the HTTP and socket doors' included (D4.3) — go to it and never to the `lumlflow ui` terminal; `lumlflow doctor` printing the fields of D11.6 — the state directory, the one record, the lock state and the handshake result among them — and the non-loopback warning of D11.3 when the daemon is bound that way
  - [ ] Tests: doctor output fields, rotation, an HTTP-door traceback in the log and not on stderr
- [ ] Wire lumlflow gc and pin outputs before staging
  - [ ] `lumlflow gc` wired to `gc.sweep` for the flows beneath the directory it is run in, reporting bytes reclaimed; output refs pinned before the kernel stages them (or in-flight scratch and staged blobs excluded from the sweep) so a sweep during a run unlinks nothing of it
  - [ ] Tests: gc reports reclaimed bytes; gc never removes an in-flight run's bytes
- [ ] Show the interpreter and its source in the Packages header
  - [ ] `render.py`'s `status` and `env` interpreter lines gain the source and `context` gains the line, its query payload gaining the interpreter it lacks today; the Packages header shows interpreter path and source from the env description (`envs.describe`, as `status` and `_env()` already report it) with that sentence (D11.7)
  - [ ] Tests: the three CLI lines, a header spec
- [ ] Align the documentation with the shipped behaviour
  - [ ] `lumlflow/docs/user-guide.md`, `lumlflow/README.md`, `docs/docs/apps/lumlflow/lumlflow.md` per D12, including the *what to commit / what a clone sees* section — the `<name>.flow/.gitignore` write and its `.git`-ancestor condition, how a git revert of a cell file is completed and made to stick, the refused-store line with the re-initialise sentence, the `luml-sdk`-in-a-project-venv sentence, and the project-first quickstart — and the `--host` warning line in the README
