# Proposals

Build the **lumlflow flow runtime** — the agent-driven, non-linear notebook
environment specified by `lattice-dfaft.md` (the binding product proposal) and
resolved technically by `preplan.md`. This spec turns the preplan into an
implementable plan; where rationale is needed, the preplan section (§n) is
cited, but every decision an implementer needs is restated here.

**Problem.** ML exploration today is linear notebooks plus ad-hoc scripts:
agents and humans overwrite each other, variants are copy-pasted files,
history is unrecoverable, and nothing tracks what is stale. The product
proposal calls for an artifact-first, lazy-reactive, BYO-agent flow
environment: cells produce versioned assets, branches are cheap first-class
variants, every change is journaled, and any coding agent can drive it with
three gestures (edit a file, `lumlflow run <slug>`, `lumlflow status`).

**Solution at a glance.**

- A **flow** is a directory: one file per cell under `cells/`, shared code
  under `lib/`, a `flow.yaml` index, a uv-managed venv, and a `.lumlflow/`
  store (content-addressed objects/values + SQLite index + append-only
  journal). Git is optional transport for the code plane; the store owns
  branches and history (§4, §5).
- Cells are **importless Python classes** ("declaration as data"): `consumes`,
  `produces`, `params`, `volatility` are literal class attributes extracted by
  AST parse, never by import. Identity is a daemon-minted `uid` written back
  into the file; the filename is the slug (§2).
- A **branch is a selection map** (`uid → version_id`) plus staleness-baseline
  pointers. Fork is one row insert; pin-at-fork is the only v1 mode. Merge is
  per-asset adopt (§5).
- **One kernel process per flow**, launched by the daemon inside the flow's
  venv with the kernel code path-injected from the tool install — the flow
  venv contains no lumlflow code. Cells run in throwaway namespaces; branch
  state is a value, not a process (§1, §14).
- The **scheduler is lazy-reactive**: the store records facts (consumed input
  versions, per-output content hashes); staleness is derived, memoization is
  keyed on `(behaviorHash, named input content-hash map)`, and early cutoff
  compares per-output content hashes (§8).
- The **journal is the API surface for history and streaming**: every
  mutation is a transaction with an `intent`; any transaction is a rewind
  target; the UI and remote mirror are journal subscribers (§5, §12).
- **Surfaces**: `lumlflow <verb>` CLI (primary, `--json` everywhere), an MCP
  server wrapping the same daemon API, a generated `AGENTS.md`, and the
  existing Vue flow UI wired to live sessions (§10–§13).

**Why this approach.** Verdicts argued in the preplan and adopted here:
branch-as-selection-map makes forking O(1); content-hash early cutoff makes
20-branch sweeps tractable; intent-carrying transactions make history
navigable; stable `uid`s survive agent renames; the importless DSL keeps the
flow venv free of lumlflow code and the spec statically extractable; the
watcher is never load-bearing (reconciliation is the truth). Explicitly cut
from v1: track-parent forking, whole-branch merge, multi-actor presence,
per-actor worktrees, parallel executors, non-Python kernels, remote sync.

# Design

## Repo placement and packages

All runtime code lives in the existing `lumlflow/` Python project
(`lumlflow/pyproject.toml`, Python ≥3.12, hatchling, ruff, mypy, pytest with
`asyncio_mode = "auto"`, tests in `lumlflow/tests/`). Three code units:

```
lumlflow/lumlflow/flow/          # daemon-side runtime (tool install only)
  ids.py                         # ULID mint (pure stdlib, Crockford base32)
  hashing.py                     # sha256 canonical-JSON helpers
  store/
    cas.py                       # objects/ and values/ content stores
    journal.py                   # append-only journal: fsync append, replay, torn-line recovery
    index.py                     # SQLite materialized view + rebuild
    models.py                    # pydantic models for all records and FlowOps
    flowstore.py                 # FlowStore: init/open, transaction commit pipeline
    branches.py                  # fork/switch/rewind/adopt, selections, baselines
    gc.py                        # mark-and-sweep, pins, retention window
  dsl/
    loader.py                    # AST extraction + classification
    normalize.py                 # uid write-back, slug→uid binding, canonical source
    accept.py                    # version-acceptance pipeline (path-agnostic)
  scheduler/
    staleness.py                 # verdict derivation (direct / transitive / unmaterialized)
    memo.py                      # memo keys, lookup, in-flight coalescing
    planner.py                   # run-to-X minimal closure with early cutoff
    queue.py                     # serial priority queue, preemption
  daemon/
    main.py                      # supervisor entrypoint, pid/lock, auto-start handshake
    api.py                       # JSON-RPC over unix socket (daemon API)
    kernel_proc.py               # venv discovery, kernel spawn, handshake, sandbox profiles
    watcher.py                   # watchdog events → acceptance; quiesce
    reconcile.py                 # the one reconciliation primitive (3 tiers)
    projections.py               # checkout, deferred projection, CHECKOUT.md, AGENTS.md
    uploads.py                   # native-output upload queue
    envs.py                      # uv integration, restart banner, lock-hash provenance
    stream.py                    # WS/SSE journal + run-log channels (milestone: streaming)
    mcp.py                       # MCP server over the daemon API
  cli.py                         # typer sub-commands, registered on lumlflow.cli:app
  errors.py                      # surface-vocabulary error types (§10 contract)

lumlflow/lumlflow_kernel/        # kernel: separate top-level package in the same wheel
  __main__.py                    # python -m lumlflow_kernel --socket ... --flow-dir ...
  rpc.py                         # JSON-RPC server + event emitter
  executor.py                    # run loop: scratch cwd, fresh namespace, reset hooks
  capture.py                     # fd-level stdout/stderr capture, single seq counter
  ctxobj.py                      # ctx: seed/tempdir/flow_dir/branch/step/secret/tracker
  kinds/
    registry.py                  # open kind registry, inference, priorities
    builtin.py                   # frame/file/checkpoint/metric/eval/plot/pickle kinds
    preview.py                   # primitive-renderable preview builders (versioned schema)
  repl.py                        # scratch REPL: lazy proxy hydration, defensive copies

lumlflow/lumlflow_typing/        # typing stubs: CellProtocol, Ctx, AssetType (TYPE_CHECKING only)
```

Hard rules: `lumlflow_kernel` imports **stdlib only** at module import time
(serde libraries import lazily inside kind matchers), targets **Python ≥3.10**
(the venv floor; the daemon stays ≥3.12), and never imports `lumlflow`. The
wheel ships all three packages (`[tool.hatch.build.targets.wheel] packages =
["lumlflow", "lumlflow_kernel", "lumlflow_typing"]`). New daemon-side
dependencies: `watchdog` (watcher), `websockets` not needed (FastAPI/uvicorn
already present). No ULID dependency — `ids.py` is ~30 lines of stdlib.

Frontend work stays in `lumlflow/frontend/src/flow/` (Vue 3 + vitest), which
already holds the concept mockups (`types.ts`, `engine.ts`, `fixtures/`).

## On-disk formats

Flow directory (§4):

```
churn.flow/
  flow.yaml            # flow id, name, language, cell index (slug ↔ uid), settings
  cells/               # cells live here and only here (classification is by directory)
    load_data.py       # filename sans .py IS the slug; lowercase enforced
  lib/                 # conventional; ANY .py outside cells/ is shared code
  data/raw.csv         # workspace file: unversioned, branch-invariant, watcher-ignored
  pyproject.toml       # flow venv definition (uv); scaffolds cloudpickle by default
  uv.lock
  AGENTS.md            # generated by the daemon, kept current
  .lumlflow/           # the store (gitignored; daemon writes the ignore entry when a git repo is detected)
    store.sqlite       # index: rebuildable materialized view of journal + objects
    journal.jsonl      # append-only transaction log — the source of truth
    objects/aa/<sha256>          # cell source blobs, manifests (small)
    values/aa/<sha256>           # serialized asset values (CAS)
    previews/aa/<sha256>.json    # bounded preview payloads
    logs/aa/<sha256>             # capped per-run log artifacts (ANSI preserved)
    kernel/            # kernel.sock (or tcp-port + token file on Windows), pid, scratch/
    daemon.sock        # daemon API socket (Windows: daemon.port + daemon.token)
    daemon.pid
    CHECKOUT.md        # generated sidecar: branch, checkpoint, staleness summary
    worktrees/         # reserved for per-actor worktrees (post-v1); v1: flow root is the single worktree
```

`flow.yaml` (written by the daemon, committed):

```yaml
flow: 01JABCDEF0123456789ABCDEF          # flow ULID
name: churn
language: python
cells:                                   # committed cross-check of slug ↔ uid
  load_data: 01J9W3ZK7QABCDEF0123456789
settings:
  value_persist_limit_mb: 500
  value_retention_days: 30
  eager_cost_threshold_s: 5
```

Workspace files: anything that is not `cells/`, a `.py` outside `cells/`,
`flow.yaml`, env files, `AGENTS.md`, or `.lumlflow/` is a workspace file —
never versioned, never touched by switch/rewind/fork, reached from cells only
via `ctx.flow_dir` (which marks the materialization `external`).

Journal line format (one transaction per line, canonical JSON):

```json
{"step": 42, "ts": "2026-08-11T12:00:00Z", "actor": "agent:claude-1",
 "intent": "tune lr", "offline": false, "settled": true, "branch": "<branch_id>",
 "ops": [ {"op": "...", ...}, ... ]}
```

`step` is a flow-global monotonic integer. Op types (the versioned wire
vocabulary, `models.py`; the mockups' `FlowOp` is a draft this replaces):
`flow_init`, `cell_accepted` (uid, version_id, slug, flags, parent_version),
`cell_removed`, `selection_set` (uid, version_id, pinned), `branch_created`
(name, parent, fork_step), `branch_archived`, `worktree_bound`, `rewound`
(to_step), `adopted` (uid, from_branch, version_id), `renamed` (uid,
old_slug, new_slug), `run_recorded` (materialization record), `memo_hit`
(uid, version_id, memo_key), `env_changed` (lock_hash, summary),
`upload_recorded` (mat_id, output, luml_ref), `flag_set`, `secret_ref_added`.
`settled` is computed at commit: true iff the branch's whole slice is
materialized and un-stale at that step (a badge, never a gate — §5).

**Write ordering (crash atomicity, §5):** CAS blobs first → fsync'd journal
append (the commit point) → SQLite update. Recovery: truncate a torn trailing
journal line; rebuild SQLite from journal + objects whenever missing or
version-mismatched; unreferenced CAS blobs are GC orphans. The SQLite index is
never trusted over the journal.

## Store data model (SQLite schema)

```sql
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);      -- flow id, schema_version, journal cursor
CREATE TABLE cells(uid TEXT PRIMARY KEY, created_step INT, copied_from TEXT);
CREATE TABLE asset_versions(
  version_id TEXT PRIMARY KEY,        -- ULID
  uid TEXT NOT NULL REFERENCES cells,
  slug TEXT NOT NULL,                 -- slug at acceptance
  source_hash TEXT NOT NULL,          -- CAS ref: raw file bytes
  bound_hash TEXT NOT NULL,           -- CAS ref: uid-bound AST-normalized source
  definition_hash TEXT NOT NULL,
  manifest TEXT NOT NULL,             -- JSON: consumes(bound), produces, params, volatility, kind_overrides, flags[]
  parent_version_id TEXT, author TEXT, created_step INT);
CREATE TABLE branches(
  branch_id TEXT PRIMARY KEY, name TEXT UNIQUE, parent_branch_id TEXT,
  fork_step INT, archived INT DEFAULT 0, sweep_group TEXT);
CREATE TABLE selections(branch_id TEXT, uid TEXT, version_id TEXT, pinned INT,
  PRIMARY KEY(branch_id, uid));
CREATE TABLE baselines(branch_id TEXT, uid TEXT, mat_id TEXT,   -- last materialization observed on branch (§8a)
  PRIMARY KEY(branch_id, uid));
CREATE TABLE materializations(
  mat_id TEXT PRIMARY KEY, version_id TEXT, memo_key TEXT, state TEXT,  -- running|succeeded|failed|cancelled
  branch_id TEXT,                      -- origin branch (provenance; hits may come from others)
  inputs TEXT,   -- JSON: name -> {uid, output, content_hash, mat_id}
  outputs TEXT,  -- JSON: name -> {content_hash, kind, size, preview_ref, value_ref?, luml_ref?, persisted}
  identity_dependent INT DEFAULT 0, env_lock_hash TEXT,
  cost_seconds REAL, log_ref TEXT, started_step INT, finished_step INT);
CREATE INDEX mat_memo ON materializations(memo_key, state);
CREATE TABLE transactions(step INT PRIMARY KEY, actor TEXT, intent TEXT,
  branch_id TEXT, settled INT, offline INT, ts TEXT, ops TEXT);
CREATE TABLE worktrees(path TEXT PRIMARY KEY, branch_id TEXT, actor TEXT, lock_holder TEXT);
CREATE TABLE upload_queue(mat_id TEXT, output TEXT, state TEXT, attempts INT,
  PRIMARY KEY(mat_id, output));
CREATE TABLE value_pins(content_hash TEXT PRIMARY KEY, reason TEXT, expires_step INT);
CREATE TABLE lib_tree(hash TEXT, computed_step INT);       -- current lib tree hash + file list JSON
```

## Identity, hashing, binding

- **`uid`**: 26-char ULID minted by the daemon on first sight of a new cell,
  written back into the file as a single line `    uid = "<ULID>"` inserted
  as the first statement after the class docstring (atomic temp +
  `os.replace`; idempotent; single-line; never touches other lines; on
  Windows, retried on sharing violations). A file at an existing slug
  *without* a `uid` reattaches to the existing uid via `flow.yaml` — never a
  remint. A file bearing an already-known uid under a new slug where the old
  slug still exists is a **copy**: remint + `copied_from` provenance. A known
  uid under a new slug with the old file gone is an **implicit rename**:
  journal a `renamed` op and run the rewire flow under the worktree lock.
- **Slugs**: filename sans `.py`, lowercase enforced (case-insensitive
  filesystems); a non-lowercase filename is flagged and auto-normalized via
  the collision/auto-suffix path. Slugs are per-branch names; `uid` is
  identity everywhere in the store.
- **Binding**: at acceptance, each `consumes` reference string is resolved
  through the branch namespace to `(uid, output_name)` and substituted into
  the AST as `"uid:<ULID>.<output>"`. The **bound source** is
  `ast.unparse()` of the class node after substitution (comments and
  formatting drop out; docstrings remain part of identity). An unresolvable
  reference stays literal and flags the version (`dangling_ref`, with a
  difflib-based did-you-mean suggestion). When a branch's namespace later
  changes such that a slug would bind to a different uid
  (delete-and-recreate, adopt), the daemon **re-accepts** affected consumer
  files on that branch — new version, new binding, surfacing as
  `definition-changed` staleness.
- **Hashes** (all sha256 over canonical JSON — sorted keys, no whitespace,
  UTF-8; blake3 is a recorded future optimization, not v1):
  - `definition_hash = sha256({"bound_source": <bound source text>, "params": params})` — identity;
    drives conflict detection and divergence display.
  - `lib_tree_hash = sha256(sorted [(relpath, sha256(file bytes))])` over every
    `.py` outside `cells/` (excluding `.lumlflow/`).
  - `behavior_hash = sha256(definition_hash + lib_tree_hash)` — computed at
    schedule time, never stored on versions.
  - `memo_key = sha256({"behavior": behavior_hash, "inputs": {name: content_hash}}
    [+ "env": lock_hash iff env_sensitive])` — the inputs are a **named map**,
    never a bag (§8b).
  - Output `content_hash`: sha256 computed by the kind while serializing.

## DSL and the acceptance pipeline

Cell files import nothing. Classification is **directory-scoped**: only files
under `cells/` are cells; every other `.py` is lib, even if it defines
`materialize`. Within a `cells/` file, the cell is the unique top-level class
defining `materialize` or carrying any compute declaration (`uid`,
`consumes`, `produces`, `params`, `volatility`). Two candidates → flagged
`ambiguous`. No qualifying class → flagged `invalid` (never silently
reclassified as lib). A class with only a docstring → **note cell**.
Declarations without `materialize` → flagged `incomplete` (not a note).

```python
class TrainXGB:
    """Train the churn model."""
    uid = "01J9W3ZK7QABCDEF0123456789"
    consumes = {"train": "features.train_split", "config": "sweep.config"}
    produces = {"model": "model", "run": "experiment", "checkpoint": "asset"}
    params = {"lr": 3e-4, "epochs": 10, "seed": 1337}
    volatility = "seeded"          # pure (default) | seeded | nondeterministic | external

    def materialize(self, ctx, train, config):
        ctx.seed()
        ...
        return {"model": m, "run": run, "checkpoint": ckpt}
```

Loader rules: declaration attributes must be literals (`ast.literal_eval`;
non-literal → flag `nonliteral_declaration`); only the declaration block is
parsed, never the body. `produces` values are exactly
`model | dataset | experiment | asset`, or a dict override
`{"type": "asset", "kind": "frame", "persist": True, "ephemeral": False}`.
`consumes` values are `producer_slug.output` or a bare `output` (partial
reference): a bare name resolves iff exactly one cell on the branch produces
that output; the daemon writes back the canonical spelling formatter-style;
ambiguous → flagged with the candidate list. Optional
`env_sensitive = True` (§14) and future `uses = [...]` are accepted and
recorded. Seeded cells draw their seed from `params` (`ctx.seed()` takes no
argument).

Volatility semantics: `pure`/`seeded` — memoized, recomputable, evictable;
`nondeterministic` — records materializations, never claims a memo hit,
values pinned within the retention window; `external` — never memoized, never
claims recompute, values pinned like nondeterministic.

**Acceptance** (`dsl/accept.py`) is one pipeline, observation-path-agnostic
(live watcher event, pre-op quiesce rescan, cold-start rescan, or
daemon-originated edit all converge on it): parse → classify → normalize
(uid mint/reattach/remint, lowercase slug, partial-ref canonicalization) →
bind → hash → validate/flag → write `asset_versions` row + CAS blobs +
`cell_accepted` op → update `flow.yaml` index. Invalid states are flagged on
the version, never rejected. Every watcher-accepted version records the
parent version the file content derived from; if the branch head moved past
that parent (deferred projection landed meanwhile), the version is flagged
`divergent` with fork-my-edit suggested instead of silently advancing the
head (§11/§13).

## Branches: fork, switch, rewind, adopt, GC

- **Fork** (`branches.fork(parent, name)`): insert one branch row; dense-copy
  the parent's `selections` and `baselines` rows (pin-at-fork is the only
  mode). No file or value copies.
- **Resolution** is two-step at schedule time: slug → uid via the branch
  namespace (current selections' slugs), uid → version via the selection map.
  References never embed versions; forking rewires nothing by construction.
- **Switch** (v1 single worktree): rebind `worktrees[flow_root]` to the
  target branch and project its slice into the flow root (write cell files
  whose content differs; delete cells not on the branch; workspace files
  untouched). Blocked while an agent session holds the worktree lock
  (`--force` overrides). Regenerates `CHECKOUT.md`.
- **Rewind** (`rewind(branch, step)`): set selections and baselines to their
  as-of-`step` values (replayed from the journal), journal a `rewound` op.
  Any transaction is a valid target. `preflight(branch, step)` first returns
  `{recompute: [(slug, est_cost)], irrecoverable: [slug]}` — irrecoverable =
  nondeterministic/external values already past the retention window.
- **Adopt** (`adopt(branch, uid, version_id)`): per-asset cherry-pick — set
  the selection entry. Conflict iff both branches edited the cell since the
  fork point (three-way on `definition_hash`); resolution is pick-a-side. If
  the adopted version's bindings resolve differently under the target
  branch's namespace, surface a namespace conflict at adopt time; namespace
  changes caused by the adopt trigger consumer re-acceptance.
- **Deletion** is per-branch: remove the selection entry; consumers dangling
  on that branch get flagged versions, other branches untouched.
- **GC** (`gc.sweep()`): mark from all branch selections (archived included)
  + a recent-journal-window grace + in-flight run pins + `value_pins`
  (nondeterministic/external values, pinned while any journaled transaction
  references them and the retention window (`value_retention_days`, journal
  steps mapped via timestamps) has not lapsed). Sweep deletes unmarked
  `values/` entries only — journal, objects, previews, and logs are never
  pruned. Eviction of pure/seeded values merely demotes them to cold
  (recomputable via lineage).

## Kernel

**Process model (§1, §14).** The daemon discovers the flow venv (`.venv/` in
the flow dir, created via `uv sync`) and spawns
`<venv-python> -m lumlflow_kernel --socket <path> --flow-dir <path>` with
`PYTHONPATH` pointing at the tool install's site-packages entry for
`lumlflow_kernel` only. Handshake reports protocol version, capabilities,
Python version, and the flow's kind registry (names, priorities, matcher
provenance). One kernel per flow; restart is cheap and stateless relative to
`.lumlflow/`.

**JSON-RPC over the kernel socket** (unix socket; Windows: loopback TCP with
a daemon-minted token file): methods `handshake`, `load_slice(values)`,
`run(run_id, version, inputs, params, ctx_info)`, `cancel(run_id)`,
`eval(branch_slice, code)` (REPL), `page(value_ref, kind, query)`,
`diff(ref_a, ref_b, kind)`, `shutdown`; events `started`, `progress`,
`log {run_id, stream, seq, bytes}`, `preview`, `materialized`, `failed`,
`identity_access {run_id, attr}`, `kind_inferred {run_id, output, kind, provenance}`.
No Python objects cross the boundary — values move as CAS entries (§9).

**Executor run procedure (§8c).** Per run: create scratch cwd under
`.lumlflow/kernel/scratch/<run_id>/` → build a fresh namespace → deserialize
inputs (hot cache LRU keyed by content hash, else CAS) → instantiate the cell
class from its bound source → call `materialize(ctx, **inputs)` → for each
returned output: infer kind, serialize to CAS while hashing, build preview →
run reset hooks (close matplotlib figures, restore env/logging deltas) →
destroy scratch cwd (declared `Path` outputs are moved into the CAS first)
→ emit `materialized`/`failed`. Serial: one cell at a time from the daemon's
priority queue (active branch first). stdin is `/dev/null` — `input()` fails
with `EOFError` and the failure record carries the hint "cells are
non-interactive — take values via `params`, secrets via `ctx`".
stdout/stderr are captured at the fd level (`dup2` pipes, one drain loop, a
single monotonic `seq` across both streams, ANSI preserved); chunks stream as
`log` events and land in a capped log artifact per materialization.
Cancellation: `PyThreadState_SetAsyncExc`-style interrupt injection, POSIX
signals as fallback. Preemption: when inputs change mid-run, cancel only if
no awaiting branch still wants the result under its own inputs.

**Runtime defaults (Hazard 1)**: enable pandas copy-on-write at kernel start;
numpy arrays handed to consumers get `writeable=False` views where cheap.
**Paranoid mode**: re-hash inputs after each run; mismatch → hard error
naming the cell, value restored from the store. **Strict mode**: defensive
copy for values live in >1 branch. Both off by default, toggled in settings.

**`ctx`**: `ctx.seed()` (applies the resolved `params["seed"]`),
`ctx.tempdir()`, `ctx.flow_dir` (Path; the sanctioned workspace-file route —
using it marks the materialization `external` via an `identity_access`-style
recorded fact), `ctx.branch` / `ctx.step` (property access emits
`identity_access`; identity-dependent materializations never claim
cross-branch memo hits), `ctx.secret(name)` (RPC to the daemon's
keyring-backed store; values never enter CAS/journal/previews),
`ctx.tracker` (thin luml-SDK wrapper recording locally; the daemon syncs).

**Kinds (§3).** `AssetType` protocol (in `lumlflow_typing`, structural):
`kind`, `python_types`, `serialize(value, sink)`, `deserialize(source)`,
`content_hash(value)` (optional), `preview(value)`, `page(source, query)`,
`diff(a, b)` (optional). Registration: entry points (`lumlflow.kinds` group)
+ the flow's `lib/` (scanned by the kernel at start). Builtins with lazy
imports: `frame` (pandas/polars via pyarrow), `file` (any `Path` return),
`checkpoint` (torch state dicts / safetensors), `metric` and `eval`
(documented plain dict/list shapes matched by shape), `plot` (matplotlib
figure / vega dict), `pickle` (cloudpickle, stdlib pickle if absent —
recorded which). Resolution per output: explicit dict override → matchers in
deterministic registry priority → pickle fallback. The winning kind and
provenance are recorded facts on the materialization. Kind plugins execute in
the kernel only; daemon `page`/`diff` APIs proxy to it, auto-starting on
demand — previews are the kernel-free tier.

**Previews**: always stored, versioned schema
`{"schema": 1, "kind": ..., "blocks": [...]}` with primitive renderables
`table {columns, rows, total_rows}` (≤20 head rows), `series {name, points}`
(≤1000 downsampled points), `image {mime, data_b64}`, `markdown {text}`,
`kv {items}`, `file {name, size, content_hash}`. Payload capped at 64 KB
(truncated with a flag). This schema is the sync payload and the UI contract.

## Scheduler: staleness, memoization, planning

**Facts, not verdicts (§8a).** The store records consumed input versions,
per-output content hashes, and per-`(branch, uid)` baseline pointers (updated
on runs and memo hits; memo hits are journaled compactly). Staleness is
derived on demand:

- `derive(branch, uid) → {state: synced | unsynced | unmaterialized | failed,
  causes: [definition-changed | deps-rewired | parent-rematerialized |
  lib-changed(file)]}` — compared against the baseline materialization on
  that branch. No baseline anywhere for an input → `unmaterialized` (a
  distinct state, never "unsynced").
- Two views over the same derivation: **direct-cause** (own definition
  changed or a direct parent actually rematerialized) and **transitive**
  (downstream closure of any change). The runtime serves both; the UI default
  is a product call, but transitive staleness must always stay discoverable
  (never-silently-stale).

**Memoization (§8b).** Before executing, the planner computes the memo key;
a `succeeded` materialization with that key is a hit (cross-branch by
construction) — recorded as a journaled `memo_hit`, baselines updated, native
refs reused. Identity-dependent materializations never match cross-branch
(the origin branch is checked). `nondeterministic` never hits;
`external` never memoizes. An in-flight run registers its memo key; a second
request awaits it (coalescing); a fork created mid-run picks the result up
iff its resolved key matches.

**Planning.** `plan(branch, target_uid)`: resolve the slice, walk the bound
dependency graph upstream from the target, and schedule the minimal stale
closure with **early cutoff**: after a parent runs, if a consumed output's
content hash is unchanged, downstream consumers of only that output are
pruned. Default mode is lazy (changes only mark); eager auto-run applies per
asset opt-in or when the recorded `cost_seconds` history is below
`eager_cost_threshold_s`. The queue is serial, active-branch-first.

## Daemon: lifecycle, watcher, reconciliation, projections

- **Lifecycle**: `lumlflow` CLI verbs auto-start the daemon (spawn detached,
  wait for socket) if not running; `daemon.pid` + socket liveness check.
  The daemon owns the store exclusively (single-writer). Cloud-synced-folder
  detection (Dropbox/OneDrive/iCloud path markers) warns at init.
- **Daemon API** (JSON-RPC over `daemon.sock`; every CLI/MCP/UI action goes
  through it): `status`, `context`, `tree`, `graph(around, depth)`,
  `cells_list/show/new/edit`, `run(target)`, `cancel`, `fork`, `switch`,
  `rewind`, `preflight`, `adopt`, `diff(a, b)`, `rename(old, new, rewire)`,
  `asset_preview/page/diff`, `eval(code)`, `env_add/remove/status`,
  `agent_begin/end`, `promote(slug, output)`, `secrets_set/list`,
  `journal_since(cursor)`, `shutdown`.
- **Watcher** (`watchdog`): events on `cells/` and non-`cells/` `.py` files
  feed acceptance; workspace files ignored. Events are a latency
  optimization only. **Quiesce contract**: every version-resolving daemon op
  begins with a synchronous rescan of the worktree that flushes pending
  observations — write-then-`run` milliseconds later always runs the new
  edit. Transaction grouping: explicit `agent begin/end` brackets win; else a
  2-second debounce window groups an edit burst into one transaction.
- **Reconciliation** — one primitive, three tiers (live events, pre-op
  quiesce, cold start): diff worktree against branch head; a diverged file
  whose content hash equals a *known version* of that asset is a **pending
  projection** and is completed, not re-accepted; anything else is accepted
  as new versions. Cold-start divergence lands as one coarse transaction,
  actor `user`, marked `offline`, auto-intent ("offline edits: N cells
  changed").
- **Attribution**: `agent begin --label X` / `agent exec -- <cmd>` (sets
  `LUMLFLOW_ACTOR`) registers the actor for the worktree; unregistered edits
  attribute to `user`; plausible mixed-editing windows are flagged. Every
  projection-changing op (`switch`, `rewind`, `adopt`, `rename --rewire`,
  deferred projections) takes the worktree lock and waits (or `--force`)
  while an agent session holds it.
- **Daemon-originated edits** (UI/Monaco, `cells edit`, param edits, rewire):
  write the `AssetVersion` directly to the store with per-cell optimistic
  locking (caller supplies base `definition_hash`; conflict → overwrite /
  fork-my-edit menu, fork suggested). Projection into the worktree happens
  only when the branch is checked out and no agent holds the lock; deferral
  is tracked so reconciliation can complete it. "Add cell" mints the uid
  immediately with placeholder slug `untitled_1` (auto-suffixed), flagged
  softly until renamed; the scaffolder prefills `consumes` from
  `--after <producer>`'s outputs.
- **Lib changes**: on lib tree hash change, journal it, and instruct the
  kernel to evict all `lib.*` entries from `sys.modules` before the next
  materialization. Staleness causes name the changed file.
- **Sandbox (v1)**: kernel runs under a no-network + FS-allowlist profile
  where cheap — macOS `sandbox-exec` profile, Linux network-namespace
  (`unshare -n`) when available; Windows gets plain process isolation.
  The active profile is reported in `lumlflow status`, never silently
  claimed. Native-output uploads are daemon-side, so no-network kernels
  don't strand them.

## Surfaces

**CLI** (typer sub-app in `flow/cli.py`, mounted on the existing
`lumlflow.cli:app`; every verb supports `--json`): `init`, `status`, `tree`,
`graph`, `cells list/show/new/edit`, `run <slug[.output]>`, `cancel`, `fork`,
`switch`, `rewind`, `preflight`, `adopt`, `diff`, `rename`, `asset
preview/page`, `eval`, `context`, `root`, `agent begin/end/exec`, `env
add/remove/status`, `secrets set/list`, `promote`, `sweep`, `export`,
`import`, `daemon start/stop/status`. Ops execute via the daemon socket
(transactional, journaled). `-m/--intent` on mutating verbs.

**Tier-0 contract (§10), enforced:** the minimum loop is edit a file +
`lumlflow run <slug>` + `lumlflow status`, names only. Error and status text
speak slugs, output names, costs, and plain causes; `uid`s, content hashes,
and memo keys appear only under `--json`. `errors.py` defines the surface
error types; a test asserts no hash/uid leaks into human-facing strings. The
generated `AGENTS.md` quickstart must fit in ~20 lines; a scripted
Haiku-class agent gate (harness in `dev/tier0_gate/`) exercising
edit → run → inspect → fix-a-failure is a v1 release gate wired for manual/CI
runs.

**Generated docs**: `AGENTS.md` (DSL cheatsheet — importless spelling, four
output words plus `eval`/`metric` dict shapes, immutability contract,
`ctx.flow_dir` and workspace files, CLI verbs, "run `lumlflow context`
first", "always name cells", "declare `asset` unless you mean to publish")
and `.lumlflow/CHECKOUT.md` (branch, checkpoint, staleness summary), both
kept current by the daemon.

**`lumlflow context` / MCP `session://focus`**: token-budgeted brief —
active branch + checkpoint, user focus, unsynced assets with causes, last
failures with tracebacks, preflight cost of the dirty set, recent
transactions with intents; stable ids included for addressing.

**MCP server** (`daemon/mcp.py`, stdio transport, launched as
`lumlflow mcp`): tools `new-cell`, `edit-cell`, `run`, `status`, `fork`,
`switch`, `rewind`, `adopt`, `diff`, `context`, `asset-preview`; resources:
manifest, cell sources, previews, focus. Strictly a wrapper over the daemon
API. MCP-only sessions never materialize a worktree (§6): with no registered
file actor, projections are skipped entirely.

**Scratch REPL**: `lumlflow eval "<code>"` (and kernel `eval`) evaluates
against the active branch's slice; names hydrate lazily via proxies handing
out **defensive copies**; never writes assets; paranoid mode re-hashes
touched hot-cache values afterwards.

## Native outputs and env management

**Native outputs (`model`/`dataset`/`experiment`, §3)**: serialized
kernel-side into the CAS exactly like `asset` (staging), then the daemon
uploads asynchronously from staged bytes + recorded metadata, writes back
`{collection, artifact_id, version, digest}` as an `upload_recorded` op, and
queues while offline (journal-visible states: `queued/uploading/done/failed`).
Uploads fire on successful materializations only — never failures, never memo
hits. Promotion of an existing inline value is `promote` (cheap; bytes
staged). Flow-emitted artifacts land in a draft/workspace tier on the
platform — a recorded requirement on luml, not built here. The luml SDK is an
ordinary venv dependency scaffolded when native outputs are declared.

**Env (§14)**: per-flow uv env; `lumlflow env add lightgbm` shells out to
`uv add`/`uv sync` and journals an `env_changed` transaction. Each
materialization records the **live** venv's lock hash (never the branch
lockfile's). Branch lockfile ≠ live venv → runs flagged "env mismatch —
restart under this branch's lock", background work for that branch deferred.
After env transactions the daemon compares `importlib.metadata` versions
against the kernel's loaded `sys.modules` and raises a "restart kernel to
apply" banner (status + UI). Env hash is provenance, not a memo-key
ingredient, except for `env_sensitive = True` cells. Materializations whose
recorded env differs from the current lock render a subtle "computed under
older env" badge.

## Streaming and frontend wiring (§12)

The daemon exposes a localhost WebSocket/SSE endpoint (uvicorn on a loopback
port recorded in `.lumlflow/daemon.port`): channel 1 — journal transactions +
kernel lifecycle events, cursor-based (`journal since N` replay on
reconnect); channel 2 — ephemeral `run_id`-scoped log chunks (from the fd
capture; ring buffer serves late joiners the tail). The journal never records
chunk streams — the capped log artifact is what the persistent logs tab
replays. Frontend: add a session client in
`lumlflow/frontend/src/flow/api/` (types generated from the op vocabulary),
and switch `FlowShell.vue` between fixture mode (existing, kept for tests)
and live mode. The existing concept mockups' `engine.ts` staleness
approximation is replaced by verdicts served from the daemon. Cell render
surface: tab strip over declared outputs + implicit `code` and `logs` tabs,
live `console` tab while running; renderers draw preview primitives, expand
pages through `asset page`.

## Portability (v1 requirement, §8)

Watcher via `watchdog` (FSEvents/inotify/ReadDirectoryChangesW); correctness
never depends on event delivery (quiesce/reconcile is the truth). Sockets:
unix domain where available, loopback TCP + token file on Windows. Atomic
writes: temp + `os.replace`, Windows retry on sharing violations. Slugs
lowercase. fd capture and interrupt injection are CPython-portable; signals
are fallback. Kernel CI runs the `lumlflow_kernel` test subset under Python
3.10 (`uv run --python 3.10`); store/watcher tests run on Windows CI from the
first milestone.

# Scenarios

## DSL, identity, acceptance

## Scenario: New cell gets a uid and a version without being imported
**Given** a flow with a running daemon and a new file `cells/train_model.py` containing a class with literal declarations and a `materialize`, no `uid`
**When** the watcher observes the file (or a quiesce rescan finds it)
**Then** a ULID is inserted as `    uid = "..."` right after the docstring via atomic replace, an `AssetVersion` is accepted with the extracted manifest, `flow.yaml` maps `train_model` to the uid, and no user code was imported or executed.

## Scenario: Ambiguous cell file is flagged, not rejected
**Given** a `cells/` file with two top-level classes both defining `materialize`
**When** acceptance runs
**Then** a version is recorded flagged `ambiguous`, `lumlflow status` names the file and both candidates, and no error blocks the agent's edit loop.

## Scenario: cells/ file with no qualifying class is invalid, not lib
**Given** `cells/oops.py` containing only a function
**When** acceptance runs
**Then** the version is flagged `invalid`; the file is never folded into the lib tree hash and the rest of the flow is not marked unsynced.

## Scenario: Note cell vs incomplete cell
**Given** one class with only a docstring, and another with `consumes` but no `materialize`
**When** both are accepted
**Then** the first is a note cell (renders as markdown) and the second is flagged `incomplete` — never treated as a note.

## Scenario: Comment-only edit does not dirty anything
**Given** an accepted, materialized cell
**When** the agent edits only comments/whitespace in the file
**Then** a new version is accepted whose `definition_hash` equals the old one, and no asset becomes unsynced.

## Scenario: Copied cell file is re-minted with provenance
**Given** `cells/eval.py` with uid U, copied to `cells/eval_v2.py` (both files present)
**When** acceptance sees the duplicate uid
**Then** `eval_v2` gets a fresh uid with `copied_from = U`, and `eval` is untouched.

## Scenario: mv is an implicit rename and costs nothing
**Given** cell `train_model` (uid U) with downstream consumers referencing `train_model.model`
**When** the file is `mv`ed to `cells/train_xgb.py`
**Then** a `renamed` op is journaled, consumer reference strings are rewritten atomically under the worktree lock, every consumer's `definition_hash` is unchanged (references hash as uids), and no cache or staleness change occurs.

## Scenario: Dropped uid line reattaches instead of re-minting
**Given** an agent rewrites `cells/features.py` wholesale, dropping the `uid` line
**When** acceptance runs
**Then** the version reattaches to the existing uid via `flow.yaml`'s index — no delete-and-recreate cascade, no consumer re-acceptance.

## Scenario: Dangling reference gets did-you-mean
**Given** a cell consuming `features.train_spilt`
**When** it is accepted
**Then** the version is flagged with "unknown reference `features.train_spilt` — did you mean `features.train_split`?" in `lumlflow status`, and running its consumers is still possible up to the dangling edge.

## Scenario: Partial reference canonicalized by write-back
**Given** exactly one cell on the branch produces `train_split`, and a new cell declares `consumes = {"train": "train_split"}`
**When** it is accepted
**Then** the file is rewritten formatter-style to `"features.train_split"`; if a second producer later exists, a fresh acceptance of a bare name is flagged with the candidate list instead.

## Branching, history, adopt

## Scenario: Fork is one row and shares values
**Given** a branch whose slice includes a 5 GB materialized frame
**When** 20 sweep forks are created
**Then** each fork is a single branch row plus copied selection/baseline rows, `values/` grows by zero bytes, and each fork inherits staleness verdicts instead of showing no observations.

## Scenario: Editing on a fork never touches the parent
**Given** branch B forked from main, both selecting `features` version F1
**When** the agent edits `features` on B (accepted as F2)
**Then** B's downstream cells resolve F2 and mark unsynced on B, while main still resolves F1 with no rewiring and no staleness.

## Scenario: Rewind to an unsettled transaction with preflight
**Given** a branch with an expensive never-materialized leaf (so no transaction is `settled`) and an evicted pure value upstream
**When** the user runs `lumlflow preflight --to <step>` then `rewind`
**Then** preflight lists the recompute set with cost estimates (and an `irrecoverable` list for any expired nondeterministic values), the rewind restores selections *and* baseline pointers to their as-of-step values instantly, and the branch does not light up wholesale-unsynced.

## Scenario: Adopt the sweep winner with conflict detection
**Given** trunk and sweep branch both forked from step S; only the sweep edited `train_model`
**When** `lumlflow adopt train_model --from sweep/lr3`
**Then** trunk's selection points at the winner's version (a journaled `adopted` op) and consumers mark unsynced. **Given** instead both sides edited since S, **then** adopt surfaces a three-way conflict on `definition_hash` with pick-a-side resolution, never a silent overwrite.

## Scenario: Adopt that rebinds a namespace re-accepts consumers
**Given** an adopted version whose bindings resolve a slug to a different uid on the target branch
**When** the adopt lands
**Then** the mismatch surfaces as a conflict at adopt time; once resolved, affected consumer files are re-accepted on that branch and surface `definition-changed` staleness.

## Scenario: Per-branch delete flags dangling consumers locally
**Given** `plot_curves` consuming `metrics.summary` on branches A and B
**When** `metrics` is deleted from A's selection
**Then** `plot_curves` on A is flagged with a dangling reference; B is untouched.

## Scenario: GC never deletes reachable or pinned truth
**Given** archived branches, an in-flight run, and a nondeterministic value referenced only by an old journaled transaction inside the retention window
**When** `gc.sweep()` runs
**Then** values selected by any branch (archived included), in-flight inputs/outputs, and the pinned nondeterministic value all survive; after the retention window lapses, the nondeterministic value may be swept and subsequent preflights report it `irrecoverable`; the journal itself is never pruned.

## Scheduling, memoization, staleness

## Scenario: Lazy by default, eager below cost threshold
**Given** an edit to `features` with a cheap plot (recorded cost 0.2 s) and a training cell (600 s) downstream
**When** the change is accepted
**Then** everything downstream marks (per the derived views) but nothing runs; the plot auto-runs only because its recorded cost is under `eager_cost_threshold_s`; training waits for an explicit `run`.

## Scenario: Early cutoff on per-output content hashes
**Given** `train_model` produces `run` and `checkpoint`, with separate consumers
**When** an edit changes what `run` contains but `checkpoint` serializes byte-identical
**Then** after `train_model` reruns, consumers of `checkpoint` only are pruned from the plan (hash equal) and never re-execute.

## Scenario: Named memo map defeats the swapped-splits false hit
**Given** a consumer of `{"train": split.a, "test": split.b}` with a cached materialization
**When** an upstream fix swaps the two outputs' contents (same multiset of hashes)
**Then** the memo key differs (named map) and the consumer re-runs — no silently wrong cache hit.

## Scenario: Cross-branch memo hit is free and journaled
**Given** branch B forked from main with `features` unchanged
**When** B runs a consumer whose memo key matches main's materialization
**Then** no execution happens, a `memo_hit` op is journaled on B, B's baseline pointer updates (fork does not read as unsynced), and any native-output reference is reused without a second upload.

## Scenario: Identity-dependent cells never hit cross-branch
**Given** a cell that reads `ctx.branch` to prefix an export path
**When** branch B requests the same memo key as main's materialization
**Then** the recorded `identity_access` fact blocks the cross-branch hit and B re-executes (so B's side-effect write fires under B's name).

## Scenario: In-flight coalescing and fork-during-run
**Given** a 10-minute training cell running for main
**When** branch B (and a fork created mid-run whose resolved key matches) request the same memo key
**Then** exactly one run executes; both await it; the result lands on main and B/the fork pick it up on completion; a preemption request fires only if no awaiter still wants the result.

## Scenario: Unmaterialized is not unsynced
**Given** a brand-new cell whose output has never materialized on any branch
**When** staleness is derived
**Then** its state is `unmaterialized` (distinct display state), not `unsynced`, in both the direct-cause and transitive views.

## Kernel execution

## Scenario: Scratch cwd isolates undeclared files, CAS captures declared ones
**Given** a cell that writes `./checkpoints/epoch3.pt` and returns `{"checkpoint": Path("checkpoints/epoch3.pt")}` with `checkpoint` declared `asset`
**When** it runs
**Then** the write lands in the per-run scratch dir, the declared Path is moved into the CAS (kind `file`) before scratch is destroyed, and a second cell reading `./checkpoints/` sees nothing.

## Scenario: input() fails fast with a targeted hint
**Given** a cell calling `input("continue?")`
**When** it runs
**Then** it fails immediately with `EOFError` (stdin is `/dev/null`), the prompt text is visible in the captured console right above the traceback, and the failure record carries the "cells are non-interactive" hint.

## Scenario: fd-level capture catches C extensions and keeps per-run logs
**Given** a cell using tqdm (stderr) and a subprocess printing to stdout
**When** it runs, completes, and is later rewound past
**Then** both streams are captured with one monotonic `seq`, streamed live tagged by stream, persisted as that materialization's capped log artifact, and rewinding shows *that* run's logs, not the latest run's.

## Scenario: Paranoid mode catches in-place mutation
**Given** paranoid mode on, and a cell that calls `df.dropna(inplace=True)` on a consumed input
**When** the run finishes
**Then** the post-run input re-hash mismatches, the run fails with an error naming the cell and the mutated input, and the stored value is restored from the CAS.

## Scenario: REPL hands out defensive copies
**Given** `lumlflow eval "train_df.dropna(inplace=True); len(train_df)"`
**When** it evaluates against the branch slice
**Then** the mutation hits a defensive copy — the hot cache and CAS are unchanged, other branches see nothing, and no asset version is written.

## Scenario: Lib edit marks everything and reloads modules
**Given** cells importing `lib.metrics` inside `materialize`, with warm caches
**When** `lib/metrics.py` is edited
**Then** the lib tree hash changes, every cell's `behaviorHash` changes (all mark unsynced with cause "stale: `lib/metrics.py` changed"), nothing recomputes until asked, and before the next materialization the kernel evicts `lib.*` from `sys.modules` so fresh code is imported — no poisoned cache entry is recorded.

## Scenario: Kind inference records facts and honors overrides
**Given** a cell returning a DataFrame, a dict shaped like the documented `metric` shape, an `EmbTable` matched by a `lib/` plugin, and an unmatchable object
**When** the outputs are captured
**Then** kinds `frame`, `metric`, the plugin's kind, and `pickle` (cloudpickle) are recorded as facts with matcher provenance; a `{"type": "asset", "kind": "frame"}` override wins over inference; every output stores a bounded preview regardless.

## Scenario: Browsing works without a kernel; expand starts one
**Given** the daemon running with no kernel process
**When** the UI renders a session and then the user expands a frame to page rows
**Then** previews render entirely from stored payloads; the page request auto-starts the kernel and proxies `page` to it.

## Watcher, daemon, projections

## Scenario: Quiesce beats the race between write and run
**Given** an agent writes `cells/features.py` and calls `lumlflow run features` milliseconds later, before any watcher event fires
**When** the run op starts
**Then** the pre-op synchronous rescan accepts the pending edit first, and the run executes the just-written version — never the previous one.

## Scenario: Cold start reconciles offline edits coarsely
**Given** the daemon stopped, three cell files edited, one new cell added
**When** the daemon starts
**Then** one transaction is journaled — actor `user`, flagged `offline`, auto-intent "offline edits: 4 cells changed" — with uid minting and validation identical to the live path.

## Scenario: Deferred projection and the stale-worktree conflict
**Given** an agent session holds the worktree while a UI edit to `train_model` lands in the store (projection deferred)
**When** (a) the agent ends its session, or (b) the agent edits the stale file first
**Then** (a) the projection completes and the file updates; (b) the agent's version records the pre-UI parent, the head does not silently advance, and the divergence is flagged with fork-my-edit suggested. A daemon restart mid-deferral recognizes the worktree file as equal to a known version (pending projection) and completes it rather than re-accepting it.

## Scenario: Optimistic locking on daemon-originated edits
**Given** a UI edit carrying base `definition_hash` H while an agent's edit already advanced the head
**When** the edit is submitted
**Then** the daemon rejects it with a conflict carrying both versions and the overwrite / fork-my-edit menu (fork suggested); no version is written until the user picks.

## Scenario: MCP-only session never materializes a worktree
**Given** a fresh flow driven exclusively via MCP `new-cell` / `edit-cell` / `run`
**When** a full edit→run→inspect loop completes
**Then** no checkout is projected, no watcher runs, and all versions/materializations are correctly attributed to the registered MCP actor.

## Scenario: Tier-0 loop uses names only and clean errors
**Given** only the generated `AGENTS.md` quickstart (~20 lines)
**When** a scripted agent edits a cell, runs `lumlflow run train_model`, reads `lumlflow status` after a failure, fixes it, and reruns
**Then** every command needed used slugs/output names only, and no uid, content hash, or memo key appeared outside `--json` output (asserted by the error-vocabulary test).

## Env, native outputs, sync

## Scenario: Mid-run install triggers the banner, not invalidation
**Given** materialized cells, then `lumlflow env add lightgbm` while the kernel has an older version imported
**When** the env transaction lands
**Then** existing materializations keep their recorded lock-hash provenance (no cache nuke), the daemon detects the loaded-vs-installed mismatch, and `status` + UI show "restart kernel to apply"; a cell with `env_sensitive = True` gets a new memo key while others do not.

## Scenario: Branch lockfile diverges from the live venv
**Given** branch B whose committed `uv.lock` differs from the venv the kernel is running
**When** a run on B is requested
**Then** the run is flagged "env mismatch — restart under this branch's lock to clear", background work for B is deferred, and the materialization (if forced) records the *live* lock hash.

## Scenario: Native output staged locally, uploaded async, offline-safe
**Given** a cell declaring `"run": "experiment"` executed while offline (or under the no-network kernel sandbox)
**When** it succeeds
**Then** the value is serialized into the local CAS (consumers and forks work immediately), an upload queue entry is journal-visible as `queued`, and when the network returns the daemon uploads and journals `upload_recorded` with the collection reference; failed runs and memo hits never enqueue uploads.

## Scenario: Clone rebuild reproduces identity
**Given** a flow committed to git (without `.lumlflow/`) cloned to a second machine
**When** the daemon first starts there
**Then** the namespace rebuilds from filenames + in-file uids cross-checked against `flow.yaml`, every cell re-accepts to identical `definition_hash`es, memo keys line up (caches are merely cold), and history starts fresh — the time plane does not travel through git.

## Scenario: Reconnecting client catches up from its cursor
**Given** a browser that disconnects at step N while an agent works overnight
**When** it reconnects with `journal since N`
**Then** it receives the exact transaction sequence after N (grouped by intent for the catch-up view), and a late subscription to a running cell's log channel serves the ring-buffer tail, not the full history.

# Tasks

- [ ] 1. **Store foundations** (`lumlflow/lumlflow/flow/`: `ids.py`, `hashing.py`, `store/cas.py`, `store/journal.py`, `store/index.py`, `store/models.py`, `store/flowstore.py`)
  - [ ] ULID mint (stdlib), canonical-JSON sha256 helpers
  - [ ] CAS (objects/values/previews/logs) with sharded dirs and atomic writes
  - [ ] Journal: fsync append, replay iterator, torn-line recovery; op vocabulary as pydantic models
  - [ ] SQLite schema + full rebuild-from-journal; commit pipeline (CAS → journal → index) with crash-point tests
  - [ ] `FlowStore.init/open`: flow.yaml scaffold, `.gitignore` entry when a git repo is detected, cloud-sync-folder warning
  - [ ] Tests in `lumlflow/tests/flow/test_store_*.py` (include Windows-path and atomic-replace coverage)
- [ ] 2. **Branch ops as pure store ops** (`store/branches.py`, `store/gc.py`)
  - [ ] Branch records, selections, baselines; fork (dense copy), switch (binding only), archive
  - [ ] Rewind: as-of-step selection + baseline replay; `preflight` with recompute estimates and `irrecoverable`
  - [ ] Adopt: per-asset selection set, three-way `definition_hash` conflict, namespace-conflict surfacing hooks
  - [ ] GC mark-and-sweep: selection roots, journal grace window, in-flight pins, nondeterministic/external retention window; `settled` computation
  - [ ] Tests: fork O(rows), rewind/baseline restoration, GC reachability matrix
- [ ] 3. **DSL loader and acceptance** (`dsl/loader.py`, `dsl/normalize.py`, `dsl/accept.py`)
  - [ ] AST extraction of literal declarations; directory-scoped classification; ambiguous/invalid/incomplete/note rules
  - [ ] uid mint + single-line write-back protocol; reattach-by-flow.yaml; copy detect-and-remint; lowercase slug normalization + auto-suffix
  - [ ] Binding (slug→uid substitution, `ast.unparse` bound source), `definition_hash`, lib tree hash, partial-reference resolution with canonical write-back, did-you-mean flags
  - [ ] Acceptance pipeline with parent-version recording and divergence flagging; flow.yaml index maintenance; re-acceptance on namespace change
  - [ ] Tests: every scenario in "DSL, identity, acceptance" above
- [ ] 4. **Kernel package** (`lumlflow/lumlflow_kernel/`, stdlib-only imports, Python ≥3.10)
  - [ ] JSON-RPC server over socket + event emitter; handshake with capabilities and kind registry report
  - [ ] Executor: scratch cwd, fresh namespace from bound source, input injection, stdin `/dev/null`, reset hooks, interrupt-injection cancel
  - [ ] fd-level capture (`dup2`, single drain loop, monotonic seq, ANSI-preserving capped log blob)
  - [ ] Kind registry + builtins (frame/file/checkpoint/metric/eval/plot/pickle, lazy imports, shape matchers, dict overrides, inference facts); serialize-while-hashing; preview primitives (versioned schema, caps)
  - [ ] `ctx`: seed/tempdir/flow_dir/branch/step with `identity_access` events, secret RPC stub, pandas CoW at start
  - [ ] Tests runnable standalone with a fake daemon socket; add a 3.10 test lane (`uv run --python 3.10`)
- [ ] 5. **Scheduler and memoization** (`scheduler/`)
  - [ ] Staleness derivation: baselines, direct-cause + transitive views, `unmaterialized`, lib-changed causes naming files
  - [ ] Memo keys (named map, env_sensitive), lookup, identity-dependent cross-branch block, nondeterministic/external rules, journaled memo hits updating baselines
  - [ ] Planner: run-to-X minimal stale closure, early cutoff on per-output hashes; serial priority queue, active-branch-first, preemption-with-awaiters, in-flight coalescing
  - [ ] Lazy default + eager-below-cost-threshold from recorded `cost_seconds`
  - [ ] Tests against a stub executor: all "Scheduling, memoization, staleness" scenarios
- [ ] 6. **Daemon core** (`daemon/main.py`, `daemon/api.py`, `daemon/kernel_proc.py`)
  - [ ] Supervisor: pid/lock, auto-start-on-verb handshake, exclusive store ownership, clean shutdown/restart statelessness
  - [ ] JSON-RPC daemon API over `daemon.sock` (loopback TCP + token on Windows) wiring store + scheduler + kernel
  - [ ] Kernel spawn: `.venv` discovery (`uv sync` if missing), PYTHONPATH injection of `lumlflow_kernel` only, handshake, restart, `lib.*` sys.modules eviction command
  - [ ] Tests: end-to-end run of a real cell through daemon → kernel → store on a temp flow
- [ ] 7. **Watcher, reconciliation, projections** (`daemon/watcher.py`, `daemon/reconcile.py`, `daemon/projections.py`)
  - [ ] watchdog wiring, workspace-file ignore rules, debounce grouping + `agent begin/end` bracketing, attribution + mixed-editing flags
  - [ ] Quiesce contract on every version-resolving op; the single reconciliation primitive in three tiers; cold-start offline transaction
  - [ ] Checkout/switch projection, worktree lock semantics, deferred projection tracking, pending-projection recognition, implicit-rename rewire flow
  - [ ] Daemon-originated edits (`cells_edit/new`) with optimistic locking + conflict menu; placeholder-slug creation, derived-slug suggestion
  - [ ] Tests: all "Watcher, daemon, projections" scenarios, including the write-then-run race
- [ ] 8. **CLI and generated docs** (`flow/cli.py`, `flow/errors.py`, `daemon/projections.py` docs, `dev/tier0_gate/`)
  - [ ] Flow verbs on `lumlflow.cli:app` (init/status/tree/graph/cells/run/cancel/fork/switch/rewind/preflight/adopt/diff/rename/asset/context/root/agent/daemon), `--json` everywhere, `-m` intents
  - [ ] Surface error vocabulary + test asserting no uid/hash leaks into human output; sliced queries (`graph --around --depth`, `cells --unsynced`, `diff` separating definition vs materialization divergence)
  - [ ] `AGENTS.md` generation (cheatsheet + quickstart ≤ ~20 lines) and `CHECKOUT.md` sidecar, kept current
  - [ ] `cells new --after <producer>` scaffolding (prefilled consumes, future-import, conformance footer)
  - [ ] Tier-0 gate harness in `dev/tier0_gate/` + CI-runnable scripted loop test
- [ ] 9. **Scratch REPL** (`lumlflow_kernel/repl.py`, `eval` verb)
  - [ ] Lazy proxy hydration from the branch slice with defensive copies; never writes assets
  - [ ] `lumlflow eval` CLI + daemon `eval` proxy; paranoid-mode post-eval re-hash backstop
  - [ ] Tests: mutation-isolation scenario, name resolution, error surfaces
- [ ] 10. **Native outputs and luml integration** (`daemon/uploads.py`, `ctx.tracker`)
  - [ ] Kernel-side staging of `model/dataset/experiment` outputs (same CAS path as `asset`), rich previews for experiments
  - [ ] Daemon upload queue: success-only, offline-tolerant, journal-visible states, `upload_recorded` write-back, memo-hit reference reuse
  - [ ] `promote` op (inline → collection); scaffold luml SDK into flow venv when native outputs are declared; `ctx.tracker` local-record wrapper
  - [ ] Tests with a mocked luml API (`luml-sdk`/`luml-api` are already path deps)
- [ ] 11. **Env management** (`daemon/envs.py`)
  - [ ] uv shell-outs (`env add/remove/status` → `uv add`/`uv sync`), `env_changed` transactions, lock-hash provenance on materializations
  - [ ] Loaded-vs-installed comparison after env transactions → restart banner; branch-lockfile mismatch flags + background deferral; `env_sensitive` memo-key opt-in; "computed under older env" badge data
  - [ ] Tests: the two env scenarios, with uv faked where needed
- [ ] 12. **Streaming and live UI wiring** (`daemon/stream.py`, `lumlflow/frontend/src/flow/`)
  - [ ] Daemon WS/SSE: journal channel with cursor replay, run-log channel with ring buffer, port/token files
  - [ ] Frontend session client (`src/flow/api/`), typed op vocabulary, fixture-vs-live source switch in `FlowShell.vue`; staleness verdicts served by the daemon replace `engine.ts` approximations
  - [ ] Cell tab strip: output tabs from previews, code + logs tabs, live console during runs
  - [ ] Tests: vitest for the client + reconnect-replay; pytest for the stream endpoints
- [ ] 13. **MCP server** (`daemon/mcp.py`)
  - [ ] stdio MCP wrapping the daemon API: tools (new-cell/edit-cell/run/status/fork/switch/rewind/adopt/diff/context/asset-preview) + resources (manifest, sources, previews, focus)
  - [ ] Worktree-less session path (no projection, no watcher) with actor attribution
  - [ ] Tests: full MCP-only loop scenario
- [ ] 14. **Modes, sandbox, portability hardening**
  - [ ] Paranoid mode (post-run input re-hash, restore-and-error) and strict mode (defensive copies for multi-branch-live values), settings-toggled
  - [ ] Kernel sandbox profiles: macOS `sandbox-exec` no-network + FS allowlist, Linux `unshare -n` when available, Windows plain isolation — active profile reported in `status`
  - [ ] Windows lane: loopback transports, write-retry on sharing violations, watcher/store CI coverage
  - [ ] Tests: paranoid detection scenario, sandbox profile reporting
- [ ] 15. **Sweeps and param edits**
  - [ ] Param-only edit op (params are data; no source rewrite) exposed via daemon API + CLI; sweep verb: N forks × param overrides with `sweep_group`, comparability guaranteed by pin-at-fork
  - [ ] Frontend: param inspector edit + sweep comparison reading per-output content hashes
  - [ ] Tests: sweep creation, memo sharing across sweep branches, winner-adopt flow
- [ ] 16. **Export/import**
  - [ ] `lumlflow export flow.py` (deterministic single-file projection of the active slice) and `lumlflow import` (round-trip to a fresh flow with preserved uids)
  - [ ] Round-trip equality test on definition hashes
