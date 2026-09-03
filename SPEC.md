# Proposals

## Problem

The platform has no way to record or see where an artifact came from: which dataset and experiment a model was produced from, which dataset another dataset was derived from, which model a model was distilled from. Every artifact (`model`, `dataset`, `experiment`) lives on its own; the only implicit link — the experiment snapshot copied into a model package — is not a reference to a platform artifact and does not form a graph.

The lineage UI already exists (the "Lineage" tab on the artifact page, PR #597) but works as a mock: the graph is not loaded from the server, "Save changes" saves nothing, the node details panel is a stub. The API client (`luml_api`) has no lineage operations. The lumlflow publish flow, which uploads a tracked experiment together with the models logged to it, uploads them as unrelated files even though the local experiment store knows exactly which model belongs to which experiment.

## Solution

Introduce **Artifact Lineage** — a graph of connections between artifacts of one orbit, populated in three ways:

- **By hand in the UI** — a person draws a connection on the Lineage tab (Link → draw → Save; Undo; Unlink; Replace).
- **Explicitly from code** — a script calls `log_lineage` in the API client, or passes `lineage_inputs` (platform artifact ids) when uploading an artifact; the edges are drawn at creation, before the file is transferred.
- **Automatically from lumlflow** — the publish flow uploads the experiment first, then every model with the experiment's artifact id as its input. A model published later, or on its own, is linked to an experiment that lumlflow itself published earlier to the same orbit: lumlflow remembers the platform id of everything it publishes. No run context, no hashing and no platform-side lookup are needed: lineage is recorded where it is known exactly, by the party that holds both ids.

The graph model is **nodes and edges**:
- **Node** — an artifact's representative on the orbit canvas: a reference to the artifact, a copy of its name/type/collection in case it is deleted, and coordinates. One canvas per orbit; the graph around an artifact is a window into it. When an artifact is deleted, a node that has edges remains as "Deleted"; deleting the artifact itself stays physical.
- **Edge** — "source → target" between two nodes, with an author and a creation channel (`ui`, `api`) — informational only.

All edges are equal and are deleted physically, whoever created them. The UI is wired to the API without changing its interaction model, persists node positions, and gains deleted-node states, a details panel with navigation and a depth selector.

## Why this approach

- **Ids at upload time instead of declarations inside the package.** An earlier design had the `luml` SDK embed "declared inputs" (a content hash or a local experiment id) into the package, and the platform resolve them into edges after both sides were uploaded. It was dropped: a content hash breaks whenever the package is rewritten after the declaration (adding a model card, or `link_to_model` itself), the same content uploaded twice makes a hash ambiguous, and the machinery — a declarations table, resolution in both upload orders, an "unresolved inputs" UI, a new package block format read by the client, a parameter on every save function and a tracker migration — is large for information the uploader already has as exact ids. The accepted drawbacks: datasets are not tracked locally today, so dataset edges stay manual or explicit; uploads made outside lumlflow link explicitly or by hand; an experiment published by another tool, or from another machine, is not linked automatically — the model links explicitly or by hand. A platform lookup by local experiment id was considered and dropped: it adds a manifest index and a listing filter to the backend for a narrow case, while the tracker store already holds the exact id for everything lumlflow publishes.
- **The orbit is the security boundary.** Every identifier in a lineage request — artifact, node, edge, and each id in `lineage_inputs` — is resolved inside the orbit in the path; anything not found there answers 404, whether it does not exist or belongs to another orbit or organization, and regardless of whether the caller has access to that other orbit. The graph never returns an artifact of another orbit. Permissions are the artifact permissions of that orbit.
- **No "manual" vs "automatic" split in permissions.** A person and a script can both be wrong; both must be correctable. The creation channel is stored as information only.
- **Nodes instead of soft-deleted artifacts and snapshots on edges.** The node keeps a copy of the fields needed to draw it, artifact deletion stays physical and changes nothing in existing reads, and positions get a natural home.
- **Edges are deleted physically.** A deletion history without an audit UI is pure cost. Undo in the editor is local.
- **The backend adapts to the UI that already exists.** An editor with local history and "Save changes" needs transactional application of a set of changes; single-edge calls are needed by the API client; both are wrappers around one operation.
- **API at the orbit level** — the graph spans collections. Artifact search for "Link an artifact" already works through the orbit listing.
- **Traversal is bounded** by depth and node count and is cycle-safe; of cycles, only the direct reverse edge is rejected.

## Scope

**In scope:** node/edge model and migration; graph read and write operations with positions; `lineage_inputs` on artifact creation; retention of nodes for deleted artifacts; wiring and finishing the UI; lineage methods and `lineage_inputs` in the API client; a remembered mapping "local object → platform artifact per orbit" in the tracker store; ordered, linked publishing in lumlflow.

**Out of scope:** declarations embedded in packages and any platform-side resolution; a platform lookup of experiments by local experiment id; dataset tracking in the local experiment store; a run context; full acyclicity checking; an audit UI; changing an edge's direction as a separate operation; role-based gating of UI actions (the server answers 403); rendering the edge creation channel in the UI; physical cleanup of orphan nodes; the lumlflow web UI (only the TUI publish flow and the handler behind it).

## Stages

1. **Backend** — model, operations, API, `lineage_inputs` at creation, artifact deletion handling, tests.
2. **API client** — lineage methods, `lineage_inputs` on `create`/`upload`.
3. **Tracker store and lumlflow** — remembered platform ids; publish order and automatic linking.
4. **UI** — store on the API with positions, node states, details panel.

# Design

## Data model

Two tables, added by one Alembic migration `backend/migrations/versions/034_lineage.py` (after `033_tracks.py`), with ORM classes in `backend/luml/models/lineage.py` following `ArtifactOrm` (`Base`, `TimestampMixin`, `Mapped[...]` columns) and Pydantic schemas in `backend/luml/schemas/lineage.py`.

### `lineage_nodes`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | default `uuid.uuid7`, as on every ORM model; stable for the node's lifetime |
| `orbit_id` | UUID FK `orbits.id` ON DELETE CASCADE | the canvas the node belongs to |
| `artifact_id` | UUID FK `artifacts.id` ON DELETE SET NULL, nullable | cleared when the artifact is deleted |
| `name` | String, not null | copy of the artifact's name |
| `type` | String, not null | copy of the artifact type (`model`, `dataset`, `experiment`, ...) |
| `collection_name` | String, nullable | copy of the collection name |
| `x`, `y` | Float, nullable | canvas coordinates; null until someone saves the canvas with this node |
| `created_at`, `updated_at` | from `TimestampMixin` | |

Indexes: partial unique `(orbit_id, artifact_id) WHERE artifact_id IS NOT NULL`; index on `orbit_id`.

While the artifact is alive the response uses its live name/type/collection; the copy is refreshed at the moment of deletion and becomes the only source afterwards.

Lifecycle: a node is created implicitly with the first edge touching the artifact. A node without edges does not exist: after any write operation, nodes left without edges are removed. When an artifact is deleted, a node with edges remains (reference cleared, copy refreshed) and is shown as "Deleted"; edges to it can still be removed, and the node can be replaced by another artifact (in the UI: "Replace").

### `lineage_edges`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | default `uuid.uuid7` |
| `orbit_id` | UUID FK `orbits.id` ON DELETE CASCADE | denormalised for orbit-scoped lookups |
| `source_node_id` | UUID FK `lineage_nodes.id` ON DELETE CASCADE | the target was produced from the source |
| `target_node_id` | UUID FK `lineage_nodes.id` ON DELETE CASCADE | |
| `created_by_user` | String, not null | the user's full name, as on artifacts |
| `created_via` | String, not null | `ui` (session/JWT request) or `api` (API-key request) |
| `created_at`, `updated_at` | from `TimestampMixin` | |

Constraints: unique `(source_node_id, target_node_id)`; check `source_node_id <> target_node_id`; indexes on `source_node_id`, `target_node_id`, `orbit_id`.

`LineageEdgeOrm.to_edge()` builds the `LineageEdge` schema (`source` ← `source_node_id`, `target` ← `target_node_id`), in the style of `ArtifactOrm.to_artifact()`.

## Security and permissions

- **Reading the graph:** `Resource.ARTIFACT`, `Action.READ` in the orbit (via `PermissionsHandler.check_permissions(organization_id, user_id, resource, action, orbit_id)`, as in `ArtifactHandler`).
- **Any lineage write** (single create, single delete, batch): `Resource.ARTIFACT`, `Action.UPDATE` in the orbit.
- **`lineage_inputs` at creation:** covered by the artifact create permission already checked in `create_artifact`; no separate check. Each id is still resolved inside the orbit in the path (see below).
- **Orbit boundary:** every artifact id is resolved through `collections.orbit_id = orbit in path` (`ArtifactRepository.get_artifacts_by_ids_in_orbit`, below); every node and edge id through its own `orbit_id`. Anything not found inside the orbit answers 404, with one deliberate exception: `positions` entries in a batch whose reference resolves to nothing are ignored, since the UI sends positions for nodes the same batch may have just removed. The response never distinguishes "does not exist" from "exists elsewhere", and the caller's access to another orbit does not matter.
- **Organization boundary:** the orbit itself is resolved inside the organization in the path, exactly as `ArtifactHandler._check_orbit_and_collection_access` does; a mismatched pair answers 404.
- **Creation channel** is derived from `request.auth.scopes` set by `backend/luml/infra/security.py`: `api_key` → `api`, `jwt` → `ui`. Routes pass the value to the handler; the client cannot set it.
- **Authentication** on the lineage router: `UserAuthentication(["jwt", "api_key"])`, as on the artifact routes.

## API

All endpoints at the orbit level, router `backend/luml/api/orbits/orbit_lineage.py`, registered in `backend/luml/api/organization_routes.py` next to `artifacts_router`. Prefix `/v1/organizations/{organization_id}/orbits/{orbit_id}`.

| Method and path | Purpose | Response |
|-----------------|---------|----------|
| `GET .../artifacts/{artifact_id}/lineage?depth=N` | Graph around an artifact. `depth` 1..5, default 2. | `LineageGraph` |
| `POST .../artifacts/{artifact_id}/lineage` | Create edges from the source artifact to each of `target_artifact_ids`. | `list[LineageEdge]` |
| `DELETE .../artifacts/{artifact_id}/lineage/{edge_id}` | Delete an edge; `artifact_id` is either of its ends. | `LineageEdge` |
| `POST .../lineage/batch` | Apply a set of changes in one transaction. | `LineageBatchResult` |
| `POST .../collections/{collection_id}/artifacts` (existing) | Body becomes `ArtifactCreateIn` = `ArtifactIn` + optional `lineage_inputs: list[UUID] \| None`. | as today |

### Schemas (`backend/luml/schemas/lineage.py`)

```python
class LineageVia(StrEnum):
    UI = "ui"
    API = "api"

class LineageNodeRef(BaseModel):
    artifact_id: UUID | None = None
    node_id: UUID | None = None
    # model validator: exactly one of the two must be set → otherwise 422

class LineagePosition(BaseModel):
    ref: LineageNodeRef
    x: float
    y: float

class LineagePair(BaseModel):
    source: LineageNodeRef
    target: LineageNodeRef

class LineageCreateIn(BaseModel):
    target_artifact_ids: list[UUID]

class LineageBatchIn(BaseModel):
    create: list[LineagePair] = []
    delete: list[UUID] = []
    positions: list[LineagePosition] = []

class LineageEdge(BaseModel):
    id: UUID
    source: UUID          # node id  (built by LineageEdgeOrm.to_edge())
    target: UUID          # node id
    created_by_user: str
    created_via: LineageVia
    created_at: datetime

class LineageNode(BaseModel):
    id: UUID
    artifact_id: UUID | None
    type: str
    name: str
    collection_name: str | None
    x: float | None
    y: float | None
    is_deleted: bool
    data: ArtifactListed | None   # same shape as the orbit listing; None for a deleted artifact

class LineageGraph(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    focal_artifact_id: UUID
    depth: int
    truncated: bool

class LineageBatchResult(BaseModel):
    created: list[LineageEdge]
    deleted: list[LineageEdge]
```

If the focal artifact has no node (no lineage), `nodes` and `edges` are empty; the UI draws the focal node from the artifact already loaded on the page.

### Errors

Body `{"detail": "<message>"}` through the existing exception classes used by `ArtifactHandler` (the not-found, conflict and bad-request errors of `backend/luml/infra`); no new exception types.

| Code | Condition | Message |
|------|-----------|---------|
| 400 | edge ends coincide | `Artifact cannot be linked to itself` |
| 403 | no permission | standard |
| 404 | artifact not found in this orbit — as focal, as an end of a new edge, as an item of `lineage_inputs`, as the artifact in the path of a single delete; node not found in this orbit | `Artifact not found` / `Lineage node not found` |
| 404 | edge not found in this orbit; on single delete — does not touch the artifact in the path | `Lineage connection not found` |
| 409 | an edge with this pair already exists | `Lineage connection already exists` |
| 409 | an edge with the reverse pair exists | `Reverse lineage connection already exists` |
| 422 | `depth` outside 1..5; body not matching the schemas, including a reference with both or neither of `artifact_id`/`node_id` | standard validation |

## The "apply changes" operation

`LineageHandler.apply_changes(user_id, organization_id, orbit_id, changes: LineageBatchIn, via: LineageVia) -> LineageBatchResult` in `backend/luml/handlers/lineage.py`. One transaction (one repository session), all or nothing. Order:

1. **Deletions.** Every edge id must exist in the orbit — otherwise 404. The edges are deleted.
2. **Creations.** References are resolved to nodes: `artifact_id` — a live artifact of this orbit, looked up in one call with `ArtifactRepository.get_artifacts_by_ids_in_orbit(orbit_id, ids, session)` (a join through `CollectionOrm.orbit_id`; any id missing from the result → 404), a node is created if missing with `INSERT ... ON CONFLICT DO NOTHING` on `(orbit_id, artifact_id)` followed by a re-select, so two concurrent writers cannot raise an `IntegrityError` (copy of name/type/collection taken from the artifact); `node_id` — an existing node of this orbit (otherwise 404). Identical pairs within the request collapse into one. Coinciding ends → 400. A pair that already exists after step 1 → 409; the reverse pair → 409. Edges are created with `created_by_user` = the requesting user's full name and `created_via` = `via`.
3. **Positions.** For every reference that resolves to a node, `x`, `y` are written. References that resolve to nothing are ignored.
4. **Cleanup.** Nodes of this orbit without edges are removed (their positions are lost).

`create_links(user_id, organization_id, orbit_id, source_artifact_id, target_artifact_ids, via)` is a batch with only `create` (all by `artifact_id`); `delete_link(user_id, organization_id, orbit_id, artifact_id, edge_id)` checks that the artifact exists in the orbit and that the edge touches its node (otherwise 404), then runs a batch with only `delete`. The artifact's upload status does not affect whether it can be linked.

## Reading the graph

`LineageHandler.get_graph(user_id, organization_id, orbit_id, artifact_id, depth) -> LineageGraph`:

1. The focal artifact must exist in the orbit — otherwise 404. If it has no node — empty graph.
2. Breadth-first traversal by levels, **ignoring direction**, from the focal node: level 1 — edges touching it; level k — edges touching nodes first discovered on level k−1 and not seen yet. Every edge appears once; the set of seen edges makes the traversal cycle-safe. One query per level (`source_node_id IN (...) OR target_node_id IN (...)`, scoped by `orbit_id`).
3. Node limit `LINEAGE_MAX_NODES = 200` in `backend/luml/constants.py`. Level 1 is always returned whole. From level 2 on, a level is added only whole: if it would push the node count over the limit, it and all deeper levels are not added. `truncated = true` whenever a level was withheld **or** the returned node count exceeds the limit (a level 1 larger than the limit).
4. Nodes are assembled by one load of live artifacts by id with the collection and active deployments (the same `selectinload` options as `get_collection_artifacts`); nodes with an empty reference use the copy and `data = None`.
5. Edges ordered by `created_at`, nodes by discovery order.

## `lineage_inputs` at artifact creation

A request-only schema `ArtifactCreateIn(ArtifactIn)` in `backend/luml/schemas/artifacts.py` adds `lineage_inputs: list[UUID] | None = None`. `ArtifactIn`, `ArtifactCreate`, `Artifact` and every response schema stay as they are: the create route (`create_artifact` in `orbit_artifacts.py`) accepts `ArtifactCreateIn`, and the handler builds `ArtifactCreate` from the `ArtifactIn` fields only, so `CrudMixin.create_model` never sees the new field and responses do not gain it.

`ArtifactHandler.create_artifact(user_id, organization_id, orbit_id, collection_id, artifact: ArtifactCreateIn, via: LineageVia)` — the route derives `via` from `request.auth.scopes` exactly as the lineage router does. After the existing checks and before the upload URL is issued:

1. Duplicates are dropped. Every id must be a live artifact whose collection belongs to the orbit in the path (`get_artifacts_by_ids_in_orbit`) — otherwise 404 `Artifact not found` and the artifact row is not created (the error reaches the client before the file transfer). An id of an artifact in another orbit is rejected the same way even if the caller has access to that orbit.
2. The artifact row is created (its own committed session, as every repository call today), then `LineageHandler.create_links` is called for each input as `input → new artifact` with the same `via`. No pair or reverse conflict is possible for a brand-new artifact.
3. If linking fails after the row was committed, the handler deletes the row with `ArtifactRepository.delete_artifact` as a compensating action and re-raises the linking error; no upload URL is issued. The window between the two calls is accepted: nothing references a `pending_upload` artifact that has no upload URL.

Pending-upload status is irrelevant: the new artifact is `pending_upload` when its edges are drawn, like any other artifact.

## Artifact deletion

The existing flow (file delete URL with deployment and track checks → confirmation; force delete) does not change. In the handler's physical deletion path, immediately before `ArtifactRepository.delete_artifact`: `LineageRepository.refresh_node_copy(artifact_id)` rewrites the node's `name`/`type`/`collection_name` from the live artifact (a no-op without a node). The reference itself is cleared by the FK `ON DELETE SET NULL` when the row goes, so a failed delete leaves a live artifact with a live node, never a detached one. After a successful delete, `LineageRepository.delete_edgeless_nodes(orbit_id)` removes the node if it had no edges. Existing artifact reads are not affected.

## UI

### Editor model

The PR #597 model is kept: edits accumulate locally, there is Undo, "Save changes" sends everything at once. Store: `frontend/src/stores/lineage/index.ts`, which delegates all logic to pure modules next to it — `mapping.ts` (graph → canvas nodes/edges, focal synthesis), `layout.ts` (auto-layout), `diff.ts` (canvas vs loaded state → batch body), `validation.ts` (connection rules, unconnected-node blocker) — so they are unit-tested without `useVueFlow()` or `useRoute()`. Components in `frontend/src/components/lineage/`; page `frontend/src/pages/collection/artifact/LineageView.vue`.

- **Loading.** On opening the tab and on a change of the focal artifact in the URL, the graph is requested with the current depth; history is cleared. If the graph is empty, a focal node is synthesized on the canvas from the page's artifact. Nodes with saved coordinates take them; nodes without coordinates are placed by auto-layout relative to already placed neighbours (if nobody has coordinates — auto-layout of the whole graph). The loaded state is remembered for the diff.
- **Edits.** "Link an artifact" adds a node without edges where the user puts it. An edge is drawn by dragging from source to target. "Unlink" removes a node from the canvas together with its edges. "Replace" swaps the node's artifact, keeping edges and position. A single edge is deleted by selecting it and pressing Delete/Backspace. Moving nodes is an edit too. Everything goes into history; Undo steps back.
- **Saving.** The button is active when there are edits and no blockers. Diff against the loaded state: `create` — canvas edges whose pair is not among the loaded ones (references: `node_id` for nodes from the graph, `artifact_id` for added ones); `delete` — loaded edges no longer on the canvas; `positions` — coordinates of **all** canvas nodes. "Replace" is expressed as deletion of the old edges + creation of new ones with the new artifact + the new node's position equal to the old one. One batch request; on success the graph is reloaded and history cleared; on error the edits are kept and the server message is shown.
- **Blocker.** A non-focal node without edges: "Save changes" is disabled with the explanation "N artifacts are not connected — connect or remove them".
- **Leaving** with unsaved edits — confirmation; agreeing loses the edits. Mechanism: `onBeforeRouteLeave` (another tab or page) and `onBeforeRouteUpdate` ("Focus lineage" changes only the `artifactId` param of the same route) in `LineageView.vue`, plus an explicit confirm in the depth selector handler, which is not a navigation.
- **"Reset positions"** recomputes the auto-layout for the current nodes; does not touch connections; it is enabled whenever the canvas has nodes (today the button is tied to `history.length`) and pushes a history entry like any other edit; saving persists the new coordinates.
- **Canvas identity.** A Vue Flow node's `id` is the server `node_id` for loaded nodes and `artifact:<artifact_id>` for nodes added in this session. `LineageNodeData` carries `nodeId: string | null`, `artifactId: string | null`, `collectionId: string | null`, `collectionName: string | null`, `isDeleted`. `usedArtifactsIds` (the selector's locked list) is the set of non-null `artifactId`s on the canvas. The diff emits a `node_id` reference when `nodeId` is set and an `artifact_id` reference otherwise; "Replace" sets `nodeId = null` and the new `artifactId` on the same canvas node.
- **Keyboard.** `<VueFlow>` gets `:delete-key-code="['Backspace', 'Delete']"` and `:nodes-deletable="false"`: the keys delete a selected edge only; nodes leave the canvas only through Unlink (with its confirmation) and the focal node never does.

### Auto-layout

Pure function in `frontend/src/stores/lineage/layout.ts`. Constants: `LEVEL_WIDTH = 320`, `ROW_HEIGHT = 120`, focal node at `(0, 0)`. Levels from the focal node taking direction into account: nodes from which edges (transitively) lead into the focal node — to the left (`x = -level * LEVEL_WIDTH`); nodes into which edges lead from the focal node — to the right (`x = level * LEVEL_WIDTH`); within a level — `y = index * ROW_HEIGHT` in discovery order (breadth-first, edges in the order received); a node reachable both ways stays where it was discovered first. Layout does not depend on the artifact type. In a partial layout (some nodes have coordinates), unplaced nodes are processed in discovery order; each is put in the column `neighbour.x ± LEVEL_WIDTH` on the side its edge leads to (left if it is the source of the edge to a placed node, right if the target), at `y = neighbour.y` if that column is empty, otherwise `ROW_HEIGHT` below the lowest node already in that column (a column is the set of placed nodes with the same `x`). Canvas direction: source on the left, target on the right, arrow from source to target; node handles are aligned with this.

### Connection validation on the canvas

Not created: a loop; a duplicate pair; the reverse pair; a connection to a deleted node (connecting is disabled on it). The server repeats the checks.

### Node states

| State | Look | Click | Menu | Connecting |
|-------|------|-------|------|------------|
| Live | type icon, name, collection, deployments badge | details panel | Replace, Unlink | enabled |
| Focal | as live + highlight | details panel | none | enabled |
| Deleted (`is_deleted`) | dimmed, dashed border, "Deleted" badge over the type icon; name and collection from the copy | nothing | Replace, Unlink | disabled |

### Details panel

Implemented in `LineageArtifactDetails.vue` (today an empty component); `ArtifactDetailsModal` and its "View artifact" stub are removed. Wiring: `@node-click` on `<VueFlow>` in `LineageArea.vue` → `lineageStore.setDetailedArtifact(nodeData)`. On clicking a live or focal node: type badge, name, collection, creation date, artifact status (from `data`). Link actions: **"Open artifact"** — the artifact page (Overview) built from `data.collection.id` and `artifact_id`, including in another collection of the same orbit; **"Focus lineage"** — this artifact's Lineage tab (hidden for the focal node). A plain click — same tab; ⌘/Ctrl-click and middle click — a new one. The synthesized focal node takes its collection name from `currentArtifact.collection.name` (`ArtifactDetails` has `collection`, not `collection_name`).

### Toolbar and messages

- Depth selector 1–5 (default 2) → reload.
- Empty graph: "No lineage recorded yet — link an artifact to get started".
- `truncated`: "Graph is limited to 200 artifacts — reduce depth to see complete levels".
- Server errors — a toast with the `detail` text. Permissions are not checked in the UI.

### Navigation between collections

The collection page reloads its data when the collection identifier in the URL changes (currently — only on mount); the Lineage tab reloads the graph when the artifact changes.

## API client (`luml_api`)

Methods on the artifact resource (`sdk/python/api/luml_api/resources/artifacts.py`: abstract base, sync and async classes), orbit from the client settings, errors — the existing exceptions by status. Types in `sdk/python/api/luml_api/_types.py`: `LineageNode`, `LineageEdge`, `LineageGraph` mirroring the backend schemas.

| Method | Parameters | Result |
|--------|------------|--------|
| `get_lineage` | `artifact_id: str`, `depth: int = 2` | `LineageGraph` |
| `log_lineage` | `source_artifact_id: str`, `target_artifact_ids: list[str]` | `list[LineageEdge]` |
| `remove_lineage` | `artifact_id: str`, `edge_id: str` | `LineageEdge` |

`create(...)` and `upload(...)` gain `lineage_inputs: list[str] | None = None`. `create` puts the list into the request body only when it is not `None`; `upload` passes it through to `create`, so a rejected id (404) surfaces before the file is transferred to storage.

## Tracker store (`luml` SDK)

The publish flow needs to know which platform artifact a local experiment or model became, per orbit. The table lives in the meta DB (the `migrations/` directory, run by `MetaDBMigrationRunner`, which discovers modules by `VERSION`), not in the per-experiment `exp_migrations/`. New migration `sdk/python/sdk/luml/experiments/backends/migrations/006_remote_artifacts.py` (`VERSION = 6`, `up`/`down` like `005_add_metadata_and_upload_status.py`); `META_DB_LAST_VERSION` in `sdk/python/sdk/tests/experiments/test_migration_runner.py` becomes 6:

```sql
CREATE TABLE IF NOT EXISTS remote_artifacts (
    local_type  TEXT NOT NULL,      -- 'experiment' | 'model'
    local_id    TEXT NOT NULL,
    orbit_id    TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (local_type, local_id, orbit_id)
)
```

Backend (`sqlite.py`, abstract in `_base.py`) and tracker methods:

```python
def set_remote_artifact(self, local_type: str, local_id: str, orbit_id: str, artifact_id: str) -> None  # upsert
def get_remote_artifact(self, local_type: str, local_id: str, orbit_id: str) -> str | None
def delete_remote_artifact(self, local_type: str, local_id: str, orbit_id: str) -> None
```

Rows are not cascaded from experiments/models (the platform artifact outlives the local row); stale rows are cleaned by the publish flow when the platform answers not-found for the remembered id. The key includes the orbit, so an id remembered for one orbit is never sent to another.

## lumlflow publish flow

`ArtifactHandler` in `lumlflow/lumlflow/handlers/luml/artifacts.py`.

**Order.** `_upload_all` uploads the experiment **first** when `with_experiment`, then the models. Every model upload passes `lineage_inputs=[experiment_artifact_id]` when an experiment artifact id is known.

**Resolving the experiment's artifact id** — `_resolve_experiment_artifact_id(data, uploaded: str | None) -> str | None`, always for the orbit of the current job. No platform request is made:

1. The experiment uploaded in this job → its id.
2. `tracker.get_remote_artifact("experiment", experiment_id, data.orbit_id)` → the remembered id, if any.
3. Nothing → `None`: the model is uploaded unlinked.

**Stale mappings.** A remembered id may point to an artifact since deleted on the platform. If the model's create request answers not-found (`NotFoundError` from `luml_api`) and the input was a remembered id, the row is deleted with `delete_remote_artifact` and the upload is retried once without `lineage_inputs`. The platform rejects the input before the file transfer, so the retry costs one extra request. An id obtained in this job is never retried: its not-found propagates as an error.

**Remembering.** After every successful upload: `set_remote_artifact("experiment" | "model", local id, data.orbit_id, artifact.id)`.

**Modes** (`upload_artifact`): `EXPERIMENT` — experiment only; `MODEL` — models, linked to the remembered experiment if any; `AUTO` — one model: embed, and link to the remembered experiment if any; several models: experiment first, then models linked to it. `upload_model` (single model) links to the remembered experiment if any. `upload_file` is unchanged.

**Failures.** Any other error on the model create request fails that model's upload like any other create error; earlier uploads in the job are kept (as today). The completion payload is unchanged.

## Tests and conventions

Each package keeps its own test style: module-level `test_*` functions with `@patch`/fixtures in the backend and `luml_api`; test classes in lumlflow and the `luml` SDK.

- Backend: repositories — integration tests against the real test DB in `backend/tests/integration/repository/test_lineage.py`; handlers — unit tests with patched repositories and a patched `PermissionsHandler` in `backend/tests/unit/handlers/test_lineage.py` (as `test_artifacts.py` does); routes — `backend/tests/unit/api/test_lineage_routes.py` with a `FastAPI` app and the `StubAuthBackend` pattern of `test_orbit_tags_routes.py`, which is also where `created_via` derivation from scopes is tested.
- API client: unit tests with `respx` in `sdk/python/api/tests/unit/test_lineage_resource.py`; sync and async.
- Tracker store: `sdk/python/sdk/tests/experiments/test_remote_artifacts.py` on a temporary sqlite store.
- lumlflow: `lumlflow/tests/test_artifact_handler_lineage.py` with a mocked `luml_api` client (a `MagicMock` whose `artifacts.upload` calls are asserted on) and a temporary tracker, in the style of `TestArtifactHandlerUploadModel` in `test_tui_cloud_publish.py`.
- Frontend: `vitest` in `frontend/src/stores/lineage/__tests__/*.test.ts` against the pure modules — mapping, layout (full and partial), diff with positions, connection validation; type check with `vue-tsc`.

# Scenarios

## Backend — writes

## Scenario: Dataset → experiment → model chain
**Given** live D (dataset), E (experiment), M (model) in one orbit, in different collections, with no lineage
**When** connections D → E and E → M are created by single calls with an API key
**Then** three nodes and two edges appear with `created_via = api` and the user's name; the graph of M at depth 2 has three nodes and two edges

## Scenario: Creation channel by request type
**Given** live A and B
**When** connection A → B is created from a browser session (JWT)
**Then** the edge has `created_via = ui`

## Scenario: Loop
**Given** live A
**When** connection A → A is created
**Then** 400 `Artifact cannot be linked to itself`, no nodes or edges appeared

## Scenario: Duplicate and reverse edge
**Given** edge A → B
**When** A → B is created; then B → A
**Then** 409 `Lineage connection already exists`; 409 `Reverse lineage connection already exists`

## Scenario: Orbit boundary on artifacts
**Given** A in orbit X, B in orbit Y of the same organization (the caller is a member of both), C in another organization, D does not exist
**When** A → B, A → C and A → D are created in orbit X
**Then** each answers 404 `Artifact not found`; no nodes or edges appeared

## Scenario: Orbit boundary on nodes and edges
**Given** node N and edge e in orbit Y; live A in orbit X
**When** in orbit X: a batch creates A → N by `node_id`; a batch deletes e; a single delete of e with A in the path
**Then** 404 `Lineage node not found`; 404 `Lineage connection not found`; 404 `Lineage connection not found`; orbit Y is untouched

## Scenario: Artifact with an unfinished upload
**Given** live A and artifact P in pending-upload status
**When** A → P is created
**Then** the edge is created

## Scenario: Several targets in one call
**Given** live A, B, C
**When** connections A → [B, C, B] are created
**Then** exactly two edges

## Scenario: Edge deletion and node cleanup
**Given** a single edge A → B
**When** the edge is deleted with A in the path
**Then** the edge and both nodes are deleted; the graph of A is empty; A → B can be created again — nodes and edge get new identifiers

## Scenario: Deletion via either end, a foreign one, and a repeat
**Given** edge A → B, artifact C outside the edge
**When** the edge is deleted with B in the path; then with C in the path; then once more with A
**Then** the first deletes; the second and third — 404 `Lineage connection not found`

## Scenario: Batch — all or nothing
**Given** live A, B, C and edge A → B
**When** batch: delete A → B, create B → C and C → C
**Then** 400; A → B is alive; B → C does not exist

## Scenario: Batch — replacing a node while keeping its position
**Given** edge A → B, node B at (300, 100); live B′
**When** batch: delete A → B, create A → B′ (by `artifact_id`), position of B′ = (300, 100)
**Then** node B is removed (no edges), B′ has a new node at (300, 100) with edge A → B′

## Scenario: Batch — positions
**Given** edges A → B and B → C without positions
**When** a batch with positions for all three nodes by `node_id`, plus a position for a nonexistent node
**Then** the three nodes got coordinates; the extra position is ignored; the graph returns the coordinates

## Scenario: Batch — recreating a pair in one request
**Given** edge A → B
**When** batch: delete it and create A → B
**Then** 200; an edge with a new identifier, the same nodes

## Scenario: Edge end reference
**Given** node N of a deleted artifact and live A
**When** a batch creates A → N by `node_id`; then a pair with a reference that has both fields set; then one with neither
**Then** the first is created; the second and third — 422

## Scenario: Empty batch
**Given** any orbit
**When** a batch with empty lists
**Then** 200, both response lists empty

## Scenario: Permissions
**Given** (handler unit test) `PermissionsHandler.check_permissions` patched to raise `InsufficientPermissionsError` for `ARTIFACT`/`UPDATE` and to pass for `ARTIFACT`/`READ` — no built-in orbit role has read without update today
**When** they write, single or batch; they read the graph
**Then** 403 and no repository write is attempted; reading is available

## Scenario: No access to the orbit
**Given** a user who is not a member of the orbit's organization
**When** they read the graph or write
**Then** the same status the artifact endpoints answer for that user today; nothing is revealed about the orbit's artifacts

## Backend — reading the graph

## Scenario: Depth and its bounds
**Given** chain D → E → M → X
**When** the graph of M with `depth = 1`; without `depth`; with 0 and 6
**Then** nodes E, M, X; the default depth 2 adds D; 0 and 6 → 422

## Scenario: Direction-agnostic traversal
**Given** A → M, B → M, M → C
**When** the graph of A with `depth = 2`
**Then** nodes A, M, B, C

## Scenario: Cycle
**Given** A → B, B → C, C → A
**When** the graph of A with `depth = 5`
**Then** three nodes and three edges, each once

## Scenario: Empty graph
**Given** an artifact without a node
**When** its graph is requested
**Then** `nodes` and `edges` are empty, `focal_artifact_id` is set, `truncated = false`

## Scenario: Deleted artifact in the graph
**Given** edge D → M, D deleted physically (node D remained)
**When** the graph of M
**Then** node D: `artifact_id` and `data` empty, `is_deleted = true`, `name`/`type`/`collection_name` from the copy; the edge is in place

## Scenario: Nonexistent focal artifact
**Given** a deleted artifact, or an artifact of another orbit
**When** its graph is requested in this orbit
**Then** 404

## Scenario: Node limit and level 1
**Given** F with 5 neighbours, each with 50 level-2 neighbours; separately G with 300 direct neighbours and nothing beyond; limit 200
**When** the graph of F with `depth = 3`; the graph of G with `depth = 2`
**Then** F: 6 nodes, `truncated = true` (level 2 withheld); G: 301 nodes, `truncated = true` (count over the limit, no level withheld)

## Backend — creation with inputs

## Scenario: Inputs at creation
**Given** live E (experiment) and D (dataset) in the orbit
**When** model M is created with `lineage_inputs = [E, D, E]`
**Then** the create response is as today; edges E → M and D → M exist with `created_via` by the request's auth type; M is `pending_upload`

## Scenario: Rejected input
**Given** artifact Z of another orbit the caller can access; W does not exist
**When** M is created with `lineage_inputs = [Z]`; then with `[W]`
**Then** 404 `Artifact not found` both times; no artifact row, node or edge was created; no upload URL was issued

## Scenario: Linking fails after the row exists
**Given** (handler unit test) the artifact repository creates the row and `LineageHandler.create_links` raises
**When** M is created with `lineage_inputs = [E]`
**Then** `delete_artifact` is called for the new row, the error propagates, no upload URL was issued

## Scenario: Response shape unchanged
**Given** a create request with `lineage_inputs`
**When** it succeeds
**Then** the response, and every listing/details response, has no `lineage_inputs` field; `ArtifactCreate` passed to the repository has no such field

## Scenario: Creation without inputs
**Given** a create request without `lineage_inputs` (or `null`)
**When** it is sent
**Then** behaviour and response are exactly as today

## Backend — artifact deletion

## Scenario: Deleting an artifact with lineage
**Given** A with edge A → B, no deployments or tracks
**When** A is deleted (confirmation or force)
**Then** A's row is deleted physically; node A remains with an empty reference (cleared by the FK) and a copy of name/type/collection refreshed just before the delete; edge A → B is alive

## Scenario: Failed deletion leaves the node attached
**Given** A with an edge; `delete_artifact` raises
**When** A is deleted
**Then** the error propagates; A's node still references A (only the copy was refreshed)

## Scenario: Deleting an artifact without lineage
**Given** artifact A that has no node
**When** A is deleted
**Then** behaviour is as today; no nodes are affected

## Scenario: Existing deletion blockers
**Given** A with an edge and with a deployment
**When** the delete URL is requested
**Then** 409 about deployments, as today

## Scenario: Replacing a deleted node
**Given** node N of a deleted artifact with edges N → B and A → N; live A′
**When** batch: delete both edges, create A′ → B and A → A′, position of A′ = position of N
**Then** N is removed, A′ took its place with the same connections

## UI

## Scenario: Empty tab
**Given** an artifact without lineage
**When** the Lineage tab is opened
**Then** a synthesized focal node, the hint, "Save changes" disabled

## Scenario: Loading with positions
**Given** D → M, E → M, M → X; M at (0, 0), D at (−320, 0), X at (320, 0); E has no coordinates
**When** the tab is opened
**Then** D, M, X at their saved places; E at (−320, 120) — M's left column, one row below D; arrows from source to target; "Save changes" disabled

## Scenario: Full auto-layout
**Given** no node has coordinates; A → M, B → M, M → C, Z → A
**When** the tab of M is opened
**Then** M (0, 0); A (−320, 0); B (−320, 120); C (320, 0); Z (−640, 0)

## Scenario: Creating a connection and saving positions
**Given** an empty graph of M
**When** the user adds D, puts it at (−260, 0), drags a connection D → M, saves
**Then** one batch: `create` [D → M by `artifact_id`], `delete` empty, `positions` — D and M; after reload both nodes are at their places

## Scenario: Moving as an edit
**Given** a loaded graph with no edits
**When** the user drags a node
**Then** "Save changes" is active; saving sends positions; Undo returns the node

## Scenario: Unlink and Replace in the diff
**Given** D → M and M → X loaded
**When** Unlink X, Replace D with D′, Save
**Then** batch: `delete` — both edges; `create` — D′ → M by `artifact_id`; position of D′ equals position of D

## Scenario: Rejected connections
**Given** A → B on the canvas, deleted node N
**When** attempts A → A, A → B, B → A, A → N
**Then** none is created

## Scenario: Unconnected node blocker
**Given** an artifact added without an edge
**When** the user looks at "Save changes"
**Then** disabled with the explanation; after an edge is drawn or the node removed — enabled

## Scenario: Save error
**Given** edits; the server answers 409
**When** saving
**Then** a toast with the message, edits and history intact

## Scenario: Deleting an edge with the keyboard
**Given** edge A → B selected
**When** Delete or Backspace
**Then** the edge disappears from the canvas and will go into `delete`

## Scenario: Keyboard never removes a node
**Given** a node selected (focal or not)
**When** Delete or Backspace
**Then** nothing happens; nodes leave only through Unlink

## Scenario: Reset positions with no edits
**Given** a loaded graph with saved coordinates and no edits
**When** "Reset positions"
**Then** enabled; all nodes take the full auto-layout; "Save changes" becomes active; Undo restores the saved coordinates

## Scenario: Details panel and navigation
**Given** live node D from another collection
**When** click; "Open artifact"; "Focus lineage"
**Then** a panel with type, name, collection, date, status; D's page with D's collection loaded; D's Lineage tab with a recentred graph and empty history

## Scenario: Focal node
**Given** a graph
**When** click on the focal node
**Then** a panel without "Focus lineage"

## Scenario: Deleted node
**Given** a node with `is_deleted`
**When** viewed and clicked
**Then** dimmed, dashed, "Deleted", name and collection from the copy; click without a panel; menu Replace and Unlink; connecting disabled

## Scenario: Leaving with edits
**Given** edits
**When** another tab / a panel link / a depth change
**Then** confirmation; decline — stay, agree — edits lost

## Scenario: Depth change
**Given** depth 2 with no edits
**When** 3 is selected
**Then** a request with `depth = 3`

## Scenario: Truncated graph
**Given** `truncated = true`
**When** rendered
**Then** the limit notice

## Scenario: No permission
**Given** the batch request answers 403
**When** saving
**Then** a toast with the server's `detail`, edits and history kept

## API client

## Scenario: Lineage methods
**Given** a configured client
**When** `get_lineage(id, depth=3)`, `log_lineage(s, [t1, t2])`, `remove_lineage(id, edge)`
**Then** GET `.../artifacts/{id}/lineage?depth=3` → a `LineageGraph` including a node with `data = None`; POST `.../artifacts/{s}/lineage` with `{"target_artifact_ids": [t1, t2]}` → edges; DELETE `.../artifacts/{id}/lineage/{edge}` → an edge

## Scenario: Errors are translated
**Given** responses 404 / 409 / 403
**When** any method
**Then** the corresponding existing exceptions

## Scenario: `lineage_inputs` on upload
**Given** a package on disk
**When** `upload(path, lineage_inputs=[E])`; then `upload(path)`
**Then** the create request body carries `"lineage_inputs": [E]`; without the parameter the field is absent from the body

## Scenario: Rejection at creation
**Given** the server answers 404 to the create request because of an input
**When** `upload(path, lineage_inputs=[Z])`
**Then** the client's not-found exception is raised and no request is made to storage

## Scenario: Async client
**Given** the async client
**When** the same calls
**Then** the same requests and results

## Tracker store

## Scenario: Remembering a platform id
**Given** a fresh store (migration 6 applied)
**When** `set_remote_artifact("experiment", "L", "orbit-1", "a1")`; again with `"a2"`; `get_remote_artifact("experiment", "L", "orbit-1")`; `get_remote_artifact("experiment", "L", "orbit-2")`
**Then** the second call overwrites; `"a2"`; `None`

## Scenario: Deleting a stale mapping
**Given** a stored mapping
**When** `delete_remote_artifact(...)`; then `get_remote_artifact(...)`
**Then** `None`; deleting again is a no-op

## Scenario: Migration is reversible
**Given** a store at version 6
**When** `down` is applied
**Then** the table is gone and the version is 5

## lumlflow

## Scenario: Publish experiment with several models
**Given** experiment L with models m1, m2; `AUTO` mode
**When** the job runs
**Then** the experiment is uploaded first (artifact E); m1 and m2 are uploaded with `lineage_inputs=[E]`; the store remembers E, m1's and m2's platform ids for that orbit

## Scenario: Publish a single model with the experiment already on the platform
**Given** L was published earlier to the same orbit as E (mapping stored); model m3 is published on its own via `upload_model`
**When** the job runs
**Then** m3 is uploaded with `lineage_inputs=[E]`; no experiment upload; no platform request other than the upload itself

## Scenario: Stale mapping
**Given** the stored mapping points to an artifact deleted on the platform
**When** a model of L is published
**Then** the create request answers not-found; the stale row is deleted; the model is uploaded again without `lineage_inputs`; the job completes

## Scenario: Experiment published by another tool
**Given** no mapping; the platform holds an experiment artifact for L uploaded by another tool
**When** a model of L is published
**Then** the model is uploaded without `lineage_inputs`; no platform lookup is attempted

## Scenario: Experiment not on the platform
**Given** no mapping for L in this orbit; `MODEL` mode
**When** the models are published
**Then** they are uploaded without `lineage_inputs`; the job completes

## Scenario: One model in AUTO mode
**Given** experiment L with one model; no mapping for L
**When** `AUTO` publish
**Then** the model is uploaded with the embedded experiment and no `lineage_inputs`, as today; if a mapping for L exists for this orbit, the model additionally links to it

## Scenario: Linking error
**Given** the create request for m2 answers 404 because of `lineage_inputs` pointing at the experiment uploaded in this job
**When** the job runs
**Then** the job reports the error without retrying; the experiment and m1 remain uploaded and remembered

## Scenario: Different orbit
**Given** L published to orbit X
**When** a model of L is published to orbit Y
**Then** the mapping for X is ignored; no id from orbit X is sent; the model is uploaded without `lineage_inputs`

# Tasks

- [x] **Backend: lineage schema and storage**
  - [x] Migration `backend/migrations/versions/034_lineage.py`: `lineage_nodes`, `lineage_edges` with the constraints and indexes from Design
  - [x] ORM `backend/luml/models/lineage.py` (`LineageNodeOrm`, `LineageEdgeOrm` with `to_edge()`, `uuid7` ids) and schemas `backend/luml/schemas/lineage.py`
  - [x] `LineageRepository` in `backend/luml/repositories/lineage.py`: get-or-create a node by artifact (`ON CONFLICT DO NOTHING` + re-select); nodes by ids within the orbit; bulk edge creation; edges by ids within the orbit; edges by pairs in both directions; edge deletion; position writes; `delete_edgeless_nodes(orbit_id)`; level-by-level traversal with the node limit; `refresh_node_copy(artifact_id)` — all operations accept an optional session so `apply_changes` runs in one transaction
  - [x] `ArtifactRepository.get_artifacts_by_ids_in_orbit(orbit_id, ids, session=None)` joined through `CollectionOrm.orbit_id`
  - [x] `backend/tests/integration/repository/test_lineage.py`: node lifecycle, uniqueness, traversal (depth, cycle, limit, level 1), positions, cleanup, orbit scoping

- [x] **Backend: lineage operations and API**
  - [x] `LineageHandler` in `backend/luml/handlers/lineage.py`: `apply_changes` (transaction; deletions → creations → positions → cleanup; all checks and codes from Design), `create_links`, `delete_link` with the ownership check, `get_graph` (empty graph without a node, copied fields for deleted nodes, coordinates, `truncated`); permission checks `ARTIFACT` `READ`/`UPDATE`; orbit resolved inside the organization
  - [x] Router `backend/luml/api/orbits/orbit_lineage.py` (graph, single create, single delete, batch), `created_via` from `request.auth.scopes`, registered in `organization_routes.py`
  - [x] `backend/tests/unit/handlers/test_lineage.py` and `backend/tests/unit/api/test_lineage_routes.py` for the "writes" and "reading the graph" scenarios, including both orbit-boundary scenarios and permissions

- [x] **Backend: inputs at creation and artifact deletion**
  - [x] `ArtifactCreateIn(ArtifactIn)` with `lineage_inputs`; the create route accepts it and passes `via` from `request.auth.scopes`; `ArtifactHandler.create_artifact(..., via)` validates inputs inside the orbit in the path, builds `ArtifactCreate` without the new field, links after the row is created, and deletes the row on linking failure; existing calls in `backend/tests/unit/handlers/test_artifacts.py` updated for the new parameter
  - [x] `refresh_node_copy` before and `delete_edgeless_nodes` after `delete_artifact` in the physical deletion path of `ArtifactHandler`
  - [x] Tests in `backend/tests/unit/handlers/test_artifacts.py` and `backend/tests/integration/repository/test_artifacts.py` for the "creation with inputs" and "artifact deletion" scenarios

- [x] **API client: lineage and inputs on upload**
  - [x] Types `LineageNode`, `LineageEdge`, `LineageGraph` in `_types.py`
  - [x] `get_lineage`, `log_lineage`, `remove_lineage` in the base, sync and async artifact resources, with docstrings in the existing style
  - [x] `lineage_inputs` on `create` and `upload` (sync and async); field omitted when `None`
  - [x] `sdk/python/api/tests/unit/test_lineage_resource.py` (HTTP mocked with `respx`): URLs, bodies, parsing, exceptions, field omitted without inputs, rejection before storage, async variant

- [x] **Tracker store: remembered platform ids**
  - [x] Meta-DB migration `006_remote_artifacts.py` with `up`/`down`; `META_DB_LAST_VERSION` → 6 in `sdk/python/sdk/tests/experiments/test_migration_runner.py`
  - [x] `set_remote_artifact`, `get_remote_artifact`, `delete_remote_artifact` in `_base.py`, `sqlite.py`, and `ExperimentTracker`
  - [x] `sdk/python/sdk/tests/experiments/test_remote_artifacts.py` for the "Tracker store" scenarios

- [x] **lumlflow: ordered publish with linking**
  - [x] `ArtifactHandler`: experiment before models in `_upload_all`; `_resolve_experiment_artifact_id` (job → remembered id for the job's orbit → none) with no platform request; stale remembered id: not-found on create → row deleted, one retry without `lineage_inputs`; `lineage_inputs` on model uploads; `set_remote_artifact` after each upload; `upload_model` uses the same resolution
  - [x] `lumlflow/tests/test_artifact_handler_lineage.py` with a mocked client and a temporary tracker for the "lumlflow" scenarios

- [x] **Frontend: API client and lineage store**
  - [x] Types for `LineageGraph`, `LineageNode`, `LineageEdge`, `LineageNodeData` (with `nodeId`/`artifactId`/`collectionId`), references and batch; client methods at the orbit level in the existing API layer
  - [x] Pure modules `mapping.ts` (graph → canvas, focal synthesis from `currentArtifact.collection.name`, canvas node ids), `layout.ts` (constants, full and partial layout), `diff.ts` (`node_id`/`artifact_id` references, positions of all nodes, Replace as delete + create + position), `validation.ts` (connection rules, unconnected-node blocker)
  - [x] Store delegates to the modules: loading, depth, `truncated`, history (moving and "Reset positions" as edits), keeping edits on error, Unlink, `usedArtifactsIds` from node data
  - [x] `frontend/src/stores/lineage/__tests__/*.test.ts` for the logic-related UI scenarios, against the pure modules

- [ ] **Frontend: Lineage tab interface**
  - [ ] Loading on open and on artifact change; leave confirmation via `onBeforeRouteLeave` + `onBeforeRouteUpdate` and in the depth handler
  - [ ] Node: live / focal / deleted states; menu; handles and arrow direction; `nodes-deletable=false` and both delete keys on `<VueFlow>`
  - [ ] `LineageArtifactDetails.vue` with "Open artifact" and "Focus lineage" links, wired from `@node-click`; `ArtifactDetailsModal` removed
  - [ ] Toolbar: depth, empty state, truncation notice, "Reset positions" enable rule, toasts
  - [ ] Collection page: reload on collection change in the URL
  - [ ] Type check and lint; manual walkthrough of the UI scenarios
