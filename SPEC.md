# Proposals

## Problem

The platform has no way to record or see where an artifact came from: which dataset and experiment a model was produced from, which dataset another dataset was derived from, which model a model was distilled from. Every artifact (`model`, `dataset`, `experiment`) lives on its own; the only implicit link — the experiment snapshot copied into a model package — is not a reference to a platform artifact and does not form a graph.

The lineage UI already exists (the "Lineage" tab on the artifact page, PR #597) but works as a mock: the graph is not loaded from the server, "Save changes" saves nothing, the node details panel is a stub. The SDK client (`luml_api`) has no lineage operations; the `luml` SDK, which creates models, datasets and experiments, knows nothing about what they were derived from — even though that is exactly where the information is at hand.

## Solution

Introduce **Artifact Lineage** — a graph of connections between artifacts of one orbit, populated in two ways:

- **Explicitly** — a person draws a connection in the UI, a script calls `log_lineage` in the API client or passes `lineage_inputs` on upload.
- **Automatically** — an artifact **declares its inputs inside its package** when it is created in the `luml` SDK (`save_sklearn(..., lineage_inputs=[dataset_ref])`; `tracker.log_model` declares its experiment by itself; an experiment declares its datasets). On upload the API client hands the declarations to the platform; the platform finds the declared artifacts in the orbit by their identity (file content or experiment identifier) and draws the edges itself — in any upload order. This is W&B-style automatic lineage without a run context: the connection is declared once, where the data is, and appears on the platform on its own.

The graph model is **nodes and edges**:
- **Node** — an artifact's representative on the orbit canvas: a reference to the artifact, a copy of its name/type/collection in case it is deleted, and coordinates. One canvas per orbit; the graph around an artifact is a window into it. When an artifact is deleted, a node that has edges remains as "Deleted"; deleting the artifact itself stays physical.
- **Edge** — "source → target" between two nodes, with an author and a creation channel (`ui`, `api`, `platform`) — informational only.

All edges are equal and are deleted physically, whoever created them. The UI is wired to the API without changing its interaction model (Link → draw → Save; Undo; Unlink; Replace), persists node positions, and gains deleted-node states, a details panel with navigation, a depth selector and a list of declared-but-not-found inputs.

## Why this approach

Decisions were made after working through the questions in `artifact_lineage_qa.md` and the follow-up discussion:

- **Declared inputs instead of a run context.** W&B derives edges from a Run because everything passes through it and artifacts have a server-side identity `name:version`. Our uploads are independent, but we have a different identity — **file content** (the sha256 the client computes on upload and the platform stores) and the **experiment identifier** (present both in the experiment package and known to the tracker when a model is logged). A declaration inside the package survives any upload order and does not require the client to know anything about the platform at the moment a model is saved.
- **No "manual" vs "automatic" split in permissions.** The platform can be wrong (identical files, an experiment uploaded twice) and so can a person; both must be correctable. The creation channel is stored as information only. An edge deleted by a person is not resurrected by the platform: a declaration is resolved once.
- **Nodes instead of soft-deleted artifacts and snapshots on edges.** Keeping "what was deleted" on the edge while also retaining the artifact row is duplication. The node keeps a copy of the needed fields itself, artifact deletion stays physical and changes nothing in existing reads, and positions get a natural home.
- **Edges are deleted physically.** A deletion history without an audit UI is pure cost. Undo in the editor is local.
- **The backend adapts to the UI that already exists.** An editor with local history and "Save changes" needs transactional application of a set of changes; single-edge calls are needed by the SDK; both are wrappers around one operation.
- **API at the orbit level** — the graph spans collections. Artifact search for "Link an artifact" already works through the orbit listing.
- **Traversal is bounded** by depth and node count and is cycle-safe; of cycles, only the direct reverse edge is rejected.

## Scope

**In scope:** node/edge/declaration model and migration; graph read and write operations with positions; resolution of declared inputs on upload in both directions; retention of nodes for deleted artifacts; wiring and finishing the UI; lineage operations and declaration passing in the API client; input declaration in the `luml` SDK (model and dataset save functions, tracker, experiment export).

**Out of scope:** a run context in the SDK; full acyclicity checking; an audit UI; changing an edge's direction as a separate operation; role-based gating of UI actions (the server answers 403); rendering the edge creation channel in the UI (returned by the API, not drawn); physical cleanup of orphan nodes.

## Stages

1. **Backend** — model, operations, API, declaration resolution, artifact deletion handling, tests.
2. **API client** — lineage methods, reading declarations from the package, `lineage_inputs` on upload.
3. **`luml` SDK** — declaring inputs on save and in the tracker.
4. **UI** — store on the API with positions, node states, details panel, declared inputs.

# Design

## Data model

### Node

An artifact's representative on the orbit canvas.

| Field | Meaning |
|-------|---------|
| `id` | Node identifier — stable for the node's lifetime; edges and the UI refer to it. |
| orbit | The orbit whose canvas the node belongs to. |
| `artifact_id` | Reference to the artifact; cleared when the artifact is deleted. Among nodes with a non-empty reference an artifact appears at most once per orbit. |
| `name`, `type`, `collection_name` | Copy of the artifact's fields. While the artifact is alive, its live values are returned; the copy is refreshed at the moment the artifact is deleted and becomes the only source afterwards. |
| `x`, `y` | Coordinates on the orbit canvas. Empty until someone saves the canvas with this node (e.g. a node created from the SDK). |
| `created_at` | Creation time. |

Lifecycle: a node is created implicitly together with the first edge touching the artifact (by any path — UI, API, platform). A node without edges does not exist: after any write operation, nodes left without edges are removed. When an artifact is deleted, a node with edges remains (reference cleared, copy refreshed) and is shown as "Deleted"; edges to it can still be removed, and the node itself can be replaced by another artifact (in the UI this is "Replace").

### Edge

| Field | Meaning |
|-------|---------|
| `id` | Edge identifier. |
| `source_node_id`, `target_node_id` | End nodes. Direction: the target was produced from the source. |
| `created_by_user` | The user's full name — as on artifacts. |
| `created_via` | Creation channel, informational only: `ui` — user session, `api` — request with an API key, `platform` — resolution of a declared input. Determined by the server from the request's authentication type or the operation's origin. |
| `created_at` | Creation time. |

Integrity: the ends differ; the "source → target" pair is unique; edge deletion is physical; deleting a node deletes its edges.

### Input declaration

"Artifact A was derived from something described like this." Stored with artifact A.

| Field | Meaning |
|-------|---------|
| artifact | Who declared it (A). Deleted together with it. |
| `type`, `name` | Type and name of the declared input — for display. |
| identity kind and value | One of: `sha256` — content hash of the input's file; `experiment_id` — local experiment identifier; `artifact_id` — platform artifact identifier (only from the upload parameter). |
| `resolved_at` | Resolution time; empty while the input has not been found. A resolved declaration is never considered again — an edge deleted by the user is not resurrected. |

### Artifact identity

So that declarations resolve in both directions, every artifact registers its identities within the orbit when created: the `sha256` of its content (all artifacts) and `experiment_id` (experiments — from the package manifest, field `local_experiment_id`). Identities are deleted together with the artifact. They are how an artifact is found in the orbit.

## Permissions

Lineage is part of the artifact: reading the graph — the artifact read permission in the orbit; any write (single, batch) — the artifact update permission in the orbit. Declaration resolution is performed by the platform as part of artifact creation and needs no separate permission.

## API

All endpoints at the orbit level: `/v1/organizations/{organization_id}/orbits/{orbit_id}/...`.

| Method and path | Purpose | Response |
|-----------------|---------|----------|
| `GET .../artifacts/{artifact_id}/lineage?depth=N` | Graph around an artifact. `depth` 1..5, default 2. | Nodes, edges, `focal_artifact_id`, `depth`, `truncated`, `unresolved_inputs` of the focal artifact. |
| `POST .../artifacts/{artifact_id}/lineage` | Create edges from the source artifact to each of `target_artifact_ids`. | Created edges. |
| `DELETE .../artifacts/{artifact_id}/lineage/{edge_id}` | Delete an edge; `artifact_id` is either of its ends. | Deleted edge. |
| `POST .../lineage/batch` | Apply a set of changes in one transaction. | `created`, `deleted`. |

**An edge end reference** in the batch is either `artifact_id` (a live artifact; a node is created if needed) or `node_id` (an existing node, including one of a deleted artifact). Exactly one of the two.

**Batch:** `create` — list of "source, target" reference pairs; `delete` — list of edge identifiers; `positions` — list of "reference, x, y". Any list may be empty.

### Graph contract

**Node:** `id` (node), `artifact_id` (empty for a deleted one), `type`, `name`, `collection_name` (empty if the collection no longer exists), `x`, `y` (empty if never saved), `is_deleted` (the artifact reference is empty), `data` — the artifact in the same shape as in listings (collection name, deployments; tracks are not loaded), empty for a deleted one.

**Edge:** `id`, `source` and `target` (node identifiers), `created_via`, `created_at`.

**Envelope:** `nodes`, `edges`, `focal_artifact_id`, `depth`, `truncated`, `unresolved_inputs` — the focal artifact's declarations without `resolved_at`: `type`, `name`, identity kind and value.

If the focal artifact has no node (no lineage), `nodes` and `edges` are empty; the UI draws the focal node from the artifact already loaded on the page.

### Errors

Body — `{"detail": "<message>"}`; the message names the offending pair or identifier.

| Code | Condition | Message |
|------|-----------|---------|
| 400 | edge ends coincide | `Artifact cannot be linked to itself` |
| 400 | artifact from another orbit | `Artifacts must belong to the same orbit` |
| 403 | no permission | standard |
| 404 | artifact does not exist — as focal, as an end of a new edge, as the artifact in the path of a single delete; node does not exist | `Artifact not found` / `Lineage node not found` |
| 404 | edge does not exist; on single delete — does not belong to the artifact in the path | `Lineage connection not found` |
| 409 | an edge with this pair already exists | `Lineage connection already exists` |
| 409 | an edge with the reverse pair exists | `Reverse lineage connection already exists` |
| 422 | `depth` outside 1..5; body not matching the contract, including a reference with both or neither of `artifact_id`/`node_id` | standard validation |

## The "apply changes" operation

One transaction, all or nothing. Order:

1. **Deletions.** Every edge identifier must exist and belong to the orbit — otherwise 404. The edges are deleted.
2. **Creations.** References are resolved to nodes: `artifact_id` — a live artifact of this orbit (otherwise 404 / 400), a node is created if missing; `node_id` — an existing node of this orbit (otherwise 404). Identical pairs within the request collapse into one. Coinciding ends → 400. A pair that already exists after step 1 → 409; the reverse pair → 409. Edges are created with the author and `created_via` according to the request type.
3. **Positions.** For every reference that resolved to a node, `x`, `y` are written. References to nonexistent nodes are ignored.
4. **Cleanup.** Nodes without edges are removed (their positions are lost).

A single create is a batch with only `create` (source and targets by `artifact_id`); a single delete is a batch with only `delete`, after checking that the edge touches the artifact in the path. The artifact's upload status does not affect whether it can be linked.

## Reading the graph

1. The focal artifact must exist in the orbit — otherwise 404. If it has no node — an empty graph (plus `unresolved_inputs`).
2. Breadth-first traversal by levels, **ignoring direction**, from the focal artifact's node: level 1 — edges touching it; level k — edges touching nodes first discovered on level k−1 and not seen yet. Every edge appears in the result once; the set of seen edges makes the traversal cycle-safe.
3. Node limit — a configuration constant, 200. Level 1 is always returned whole. From level 2 on, a level is added only whole: if it would push the node count over the limit, it is not added and `truncated = true`.
4. Nodes are assembled by one load of artifacts by reference; nodes with an empty reference use the copy.
5. Edges are ordered by creation time, nodes by discovery order.

## Resolving declared inputs

Performed by the platform when an artifact is created (before the file is uploaded: the hash and manifest are already known), within the artifact's orbit:

1. **Register identities** of the new artifact: `sha256`; for an experiment also `experiment_id` from the manifest.
2. **Accept declarations** from the create request (optional field `lineage_inputs`). Declarations with `artifact_id` are checked immediately: the artifact must be alive and in the same orbit — otherwise 404 / 400 and the artifact is not created (a user error, better caught before the file upload). Declarations with `sha256` and `experiment_id` are never errors — they may resolve later. A declaration whose identity matches the artifact's own identity is dropped.
3. **Forward resolution:** each declaration of the new artifact is matched against the identities of the orbit's artifacts. For each matching artifact an edge "matched → new" is created. Several matches (the same file uploaded twice) — edges to all of them. The declaration gets `resolved_at` if at least one matched.
4. **Reverse resolution:** unresolved declarations of the orbit's other artifacts are matched against the new artifact's identities; for matches an edge "new → declaring" is created and the declaration gets `resolved_at`.
5. Edges are created with `created_via = platform`, author — the requesting user. If such an edge already exists (a person linked earlier) it is not duplicated and the declaration counts as resolved. If the reverse edge exists, the platform does not argue with the person: the edge is not created and the declaration stays unresolved.
6. A resolved declaration no longer takes part in resolution: an edge deleted by a person is not restored by the platform; re-uploading the same file yields no new edges for already resolved declarations.

## Artifact deletion

The existing flow (file delete URL with deployment and track checks → confirmation; force delete) does not change. Additionally, at the moment of physical deletion: if the artifact has a node, its name/type/collection copy is refreshed and the reference cleared; a node without edges is deleted; the artifact's declarations and identities are deleted. Existing artifact reads are not affected.

## UI

### Editor model

The PR #597 model is kept: edits accumulate locally, there is Undo, "Save changes" sends everything at once.

- **Loading.** On opening the tab and on a change of the focal artifact in the URL, the graph is requested with the current depth; history is cleared. If the graph is empty, a focal node is synthesized on the canvas from the page's artifact. Nodes with saved coordinates take them; nodes without coordinates are placed by auto-layout relative to already placed neighbours (if nobody has coordinates — auto-layout of the whole graph). The loaded state is remembered for the diff.
- **Edits.** "Link an artifact" adds a node without edges where the user puts it. An edge is drawn by dragging from source to target. "Unlink" removes a node from the canvas together with its edges. "Replace" swaps the node's artifact, keeping edges and position. A single edge is deleted by selecting it and pressing Delete/Backspace. Moving nodes is an edit too. Everything goes into history; Undo steps back.
- **Saving.** The button is active when there are edits and no blockers. Diff against the loaded state: `create` — canvas edges whose pair is not among the loaded ones (references: `node_id` for nodes from the graph, `artifact_id` for added ones); `delete` — loaded edges no longer on the canvas; `positions` — coordinates of **all** canvas nodes. "Replace" is expressed as deletion of the old edges + creation of new ones with the new artifact + the new node's position equal to the old one. One batch request; on success the graph is reloaded and history cleared; on error the edits are kept and the server message is shown.
- **Blocker.** A non-focal node without edges: "Save changes" is disabled with the explanation "N artifacts are not connected — connect or remove them".
- **Leaving** with unsaved edits (another tab, a panel link, a depth change) — confirmation; agreeing loses the edits.
- **"Reset positions"** recomputes the auto-layout for the current nodes; does not touch connections; saving persists the new coordinates.

### Auto-layout

Levels from the focal node taking direction into account: nodes from which edges (transitively) lead into the focal node — to the left, proportionally to the level; nodes into which edges lead from the focal node — to the right; within a level — vertically in discovery order; a node reachable both ways stays where it was discovered first. Layout does not depend on the artifact type. In a partial layout (some nodes have coordinates), an unplaced node is put next to its nearest placed neighbour on the side the edge leads to, below already occupied spots. Canvas direction: source on the left, target on the right, arrow from source to target; node handles are aligned with this.

### Connection validation on the canvas

Not created: a loop; a duplicate pair; the reverse pair; a connection to a deleted node (connecting is disabled on it). The server repeats the checks.

### Node states

| State | Look | Click | Menu | Connecting |
|-------|------|-------|------|------------|
| Live | type icon, name, collection, deployments badge | details panel | Replace, Unlink | enabled |
| Focal | as live + highlight | details panel | none | enabled |
| Deleted (`is_deleted`) | dimmed, dashed border, "Deleted" badge over the type icon; name and collection from the copy | nothing | Replace, Unlink | disabled |

### Details panel

On clicking a live or focal node: type badge, name, collection, creation date, artifact status. Link actions: **"Open artifact"** — the artifact page (Overview), including in another collection of the same orbit; **"Focus lineage"** — this artifact's Lineage tab (hidden for the focal node). A plain click — same tab; ⌘/Ctrl-click and middle click — a new one.

### Toolbar and messages

- Depth selector 1–5 (default 2) → reload.
- Empty graph: "No lineage recorded yet — link an artifact to get started".
- `truncated`: "Graph is limited to 200 artifacts — reduce depth to see complete levels".
- `unresolved_inputs` of the focal artifact non-empty: an indicator "N declared inputs not found in this orbit" with an expandable list "type · name · identity". It is a hint why an expected edge is missing; it has no actions.
- Server errors — a toast with the `detail` text. Permissions are not checked in the UI.

### Navigation between collections

The collection page reloads its data when the collection identifier in the URL changes (currently — only on mount); the Lineage tab reloads the graph when the artifact changes.

## API client (`luml_api`)

Methods on the artifact resource, sync and async clients, orbit from the client settings, errors — the existing exceptions by status.

| Method | Parameters | Result |
|--------|------------|--------|
| `get_lineage` | `artifact_id`, `depth` (2) | graph per contract, including `unresolved_inputs` |
| `log_lineage` | `source_artifact_id`, `target_artifact_ids` | created edges |
| `remove_lineage` | `artifact_id`, `edge_id` | deleted edge |

**Declarations on upload.** While parsing the package (the same archive pass that reads the manifest and metadata), `upload` collects all metadata blocks tagged `dataforce.studio::lineage_inputs:v1`, merges their contents, adds declarations from the optional `lineage_inputs` parameter (a list of artifact identifiers → kind `artifact_id`), removes duplicates by identity and passes the list in the artifact create request. No declarations — the field is not sent. No calls after upload: resolution is done by the platform at creation; an `artifact_id` validation error comes back from the create request before the file is transferred.

## `luml` SDK

The parameter is named `lineage_inputs` everywhere: `inputs` in the save functions and in `log_model` already means sample data for schema inference.

**Declaration block in the package.** A metadata block tagged `dataforce.studio::lineage_inputs:v1` whose content is a list of inputs: `type`, `name`, identity kind and value. There may be several blocks (appended over successive calls); the reader merges them.

**Reference → declaration.** A model or dataset reference: `sha256` of the reference's file content at the moment of declaration, type from the manifest (model — from the reference kind), name from the manifest or the file name. An experiment reference: `experiment_id` from the experiment package manifest, name from the manifest. Documented caveat: the hash is computed over the file "as is" — declare the file that is or will be on the platform (downloaded from it or uploaded unchanged); a file modified after the declaration (e.g. a card added) will not match on the platform and the input stays unresolved — it can be linked manually.

**Declaration points:**
- on all references — method `add_lineage_inputs(refs)`: append a block to an existing package (for packages built otherwise);
- `save_sklearn`, `save_xgboost`, `save_lightgbm`, `save_catboost`, `save_langgraph`, `save_tabular_dataset`, `save_hf_dataset` — optional `lineage_inputs`: a list of references; after the package is built, a block is appended;
- tracker: `start_experiment(..., lineage_inputs=...)` and `add_lineage_inputs(refs, experiment_id=None)` store the experiment's declarations in the local experiment store (a new local migration); experiment export writes them as a block into the experiment package;
- `log_model` — passes `lineage_inputs` through to the save and always adds a declaration of the current experiment (`experiment_id`, experiment name) to the model package; for an already saved reference — appends a block;
- `link_to_model` — besides the snapshot, appends the experiment declaration.

The classic chain needs no explicit link call: `start_experiment(lineage_inputs=[dataset_ref])` → `log_model(model)` → upload the dataset, the experiment and the model in any order → `dataset → experiment → model` on the platform.

## Tests and conventions

- Backend: repositories — integration tests against the real test DB (locally, `pytest` with the test database DSN); handlers and routes — unit tests with mocks. New files — one test class per module.
- API client and `luml` SDK: unit tests (HTTP mocked with `respx` in the client; temporary packages on disk in the SDK); one class per module.
- Frontend: `vitest` on store logic — mapping, layout (full and partial), diff with positions, connection validation; type check with `vue-tsc --noEmit`.

# Scenarios

## Backend — writes

## Scenario: Dataset → experiment → model chain
**Given** live D (dataset), E (experiment), M (model) in one orbit, in different collections, with no lineage
**When** connections D → E and E → M are created by single calls with an API key
**Then** three nodes and two edges appear with `created_via = api` and the user's name; the graph of M at depth 2 has three nodes and two edges

## Scenario: Creation channel by request type
**Given** live A and B
**When** connection A → B is created from a user session
**Then** the edge has `created_via = ui`

## Scenario: Loop
**Given** live A
**When** connection A → A is created
**Then** 400 `Artifact cannot be linked to itself`, no nodes or edges appeared

## Scenario: Duplicate and reverse edge
**Given** edge A → B
**When** A → B is created; then B → A
**Then** 409 `Lineage connection already exists`; 409 `Reverse lineage connection already exists`

## Scenario: Foreign orbit and nonexistent artifact
**Given** A in orbit X, B in orbit Y, C does not exist
**When** A → B and A → C are created in orbit X
**Then** 400 `Artifacts must belong to the same orbit`; 404 `Artifact not found`

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
**When** a batch creates A → N by `node_id`; then a pair with a reference that has both fields set
**Then** the first is created; the second — 422

## Scenario: Empty batch
**Given** any orbit
**When** a batch with empty lists
**Then** 200, both response lists empty

## Scenario: Permissions
**Given** an orbit member with only the artifact read permission
**When** they write, single or batch; they read the graph
**Then** 403; reading is available

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
**Then** `nodes` and `edges` are empty, `unresolved_inputs` holds the artifact's declarations (if any)

## Scenario: Deleted artifact in the graph
**Given** edge D → M, D deleted physically (node D remained)
**When** the graph of M
**Then** node D: `artifact_id` and `data` empty, `is_deleted = true`, `name`/`type`/`collection_name` from the copy; the edge is in place

## Scenario: Nonexistent focal artifact
**Given** a deleted artifact or an artifact of another orbit
**When** its graph is requested
**Then** 404

## Scenario: Node limit and level 1
**Given** F with 5 neighbours, each with 50 level-2 neighbours; separately G with 300 direct neighbours; limit 200
**When** the graph of F with `depth = 3`; the graph of G
**Then** F: 6 nodes, `truncated = true`; G: 301 nodes, `truncated = true`

## Backend — resolving declarations

## Scenario: Forward resolution by hash
**Given** dataset D uploaded (hash H)
**When** model M is created with declaration `sha256 = H`
**Then** edge D → M with `created_via = platform`; the declaration is resolved; `unresolved_inputs` in the graph of M is empty

## Scenario: Reverse resolution
**Given** model M created with declaration `sha256 = H`, no dataset with H in the orbit — the declaration is unresolved
**When** dataset D with hash H is uploaded
**Then** edge D → M; M's declaration is resolved

## Scenario: Experiment in any order
**Given** model M with declaration `experiment_id = X`; then experiment E with `local_experiment_id = X` is uploaded
**When** both are created
**Then** edge E → M. The same result if E is uploaded before M

## Scenario: Classic chain automatically
**Given** experiment E declares dataset D (by hash); model M declares E (by identifier)
**When** D, E, M are uploaded in arbitrary order
**Then** after the last upload the graph of M shows D → E → M, both edges `platform`

## Scenario: Several matches
**Given** one file uploaded as D1 and D2 (hash H)
**When** M is created with declaration H
**Then** edges D1 → M and D2 → M; the declaration is resolved

## Scenario: Resolved once
**Given** M's declaration by hash H resolved by edge D → M
**When** D3 with the same H is uploaded
**Then** no new edge to M

## Scenario: An edge deleted by a person does not return
**Given** edge D → M created by resolution
**When** the user deletes the edge; then another file with D's hash is uploaded
**Then** the edge is not recreated; the declaration stays resolved

## Scenario: Edge already exists or contradicts
**Given** the user created D → M manually; separately, the user created M2 → D2
**When** M is created with a declaration of D's hash; M2 is created with a declaration of D2's hash
**Then** first: no duplicate, the declaration is resolved; second: edge D2 → M2 is not created (the reverse exists), the declaration stays unresolved and is visible in M2's `unresolved_inputs`

## Scenario: Declaration by `artifact_id`
**Given** live D in the orbit; artifact Z in another orbit
**When** M is created with declarations `artifact_id = D` and `artifact_id = Z`
**Then** 400, the artifact is not created. With D only — edge D → M, `created_via = platform`

## Scenario: Self-declaration and duplicates
**Given** an artifact is created with a declaration of its own hash and two identical declarations
**When** it is created
**Then** the self-declaration is dropped; of the identical ones, one is kept

## Scenario: Another orbit does not take part
**Given** a dataset with hash H in orbit Y
**When** M is created in orbit X with declaration H
**Then** no edge; the declaration is unresolved

## Backend — artifact deletion

## Scenario: Deleting an artifact with lineage
**Given** A with edge A → B, no deployments or tracks
**When** A is deleted (confirmation or force)
**Then** A's row is deleted physically; node A remains with an empty reference and a copy of name/type/collection; edge A → B is alive; A's declarations and identities are deleted; A no longer takes part in resolution

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
**Given** D → M, E → M, M → X; D, M, X have saved coordinates, E does not
**When** the tab is opened
**Then** D, M, X at their saved places; E left of M below D; arrows from source to target; "Save changes" disabled

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
**When** Delete
**Then** the edge disappears from the canvas and will go into `delete`

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

## Scenario: Unresolved inputs
**Given** the focal artifact has two unresolved declarations
**When** rendered
**Then** the indicator "2 declared inputs not found in this orbit" with the list "type · name · identity"

## Scenario: No permission
**Given** read-only permission
**When** saving
**Then** a toast about insufficient permissions, edits kept

## API client

## Scenario: Lineage methods
**Given** a configured client
**When** `get_lineage(id, depth=3)`, `log_lineage(s, [t1, t2])`, `remove_lineage(id, edge)`
**Then** GET `.../artifacts/{id}/lineage?depth=3` → a graph with `unresolved_inputs` and a node without `data`; POST `.../artifacts/{s}/lineage` with `{"target_artifact_ids": [t1, t2]}` → edges; DELETE `.../artifacts/{id}/lineage/{edge}` → an edge

## Scenario: Errors are translated
**Given** responses 404 / 409 / 403
**When** any method
**Then** the corresponding existing exceptions

## Scenario: Declarations from the package on upload
**Given** a package with two `lineage_inputs` blocks (the second repeats one input of the first)
**When** `upload(path)`
**Then** the create request carries `lineage_inputs` with the merged list without duplicates; no link calls after upload

## Scenario: The `lineage_inputs` parameter
**Given** a package without blocks
**When** `upload(path, lineage_inputs=[D, E])`
**Then** the create request carries two declarations of kind `artifact_id`; without the parameter and blocks the field is absent

## Scenario: Rejection at creation
**Given** the server answers 400 to the create request because of a declaration
**When** `upload(path, lineage_inputs=[Z])`
**Then** an exception before the file is transferred to storage

## Scenario: Async client
**Given** the async client
**When** the same calls
**Then** the same requests and results

## `luml` SDK

## Scenario: Declaration when saving a model
**Given** dataset reference D (file with hash H)
**When** `save_sklearn(model, inputs=X, lineage_inputs=[D])`
**Then** the model package has a `lineage_inputs` block with one input: `type = dataset`, name from D's manifest, `sha256 = H`

## Scenario: Declaration when saving a dataset
**Given** dataset reference R
**When** `save_tabular_dataset(df, lineage_inputs=[R])`
**Then** a block with input R by hash

## Scenario: Experiment as an input
**Given** an exported experiment package E (`local_experiment_id = X`)
**When** `save_xgboost(..., lineage_inputs=[E])`
**Then** input `type = experiment`, `experiment_id = X`

## Scenario: The tracker declares the experiment itself
**Given** `start_experiment()` returned X
**When** `log_model(model)` — both for a raw model and for an already saved reference; separately `link_to_model(ref)`
**Then** the model package has input `experiment_id = X` with the experiment name; the block is appended, the package content is not damaged

## Scenario: Experiment inputs
**Given** `start_experiment(lineage_inputs=[D])`, then `add_lineage_inputs([D2])`
**When** the experiment is exported
**Then** the experiment package has a block with D and D2 by hash; a repeated export yields the same block

## Scenario: Appending to an existing package
**Given** a package built without inputs
**When** `add_lineage_inputs([D])` twice with the same D
**Then** two blocks with the same input; the client's reader merges them into one

## Scenario: Nothing changes without inputs
**Given** calls without `lineage_inputs`
**When** saving and exporting
**Then** no block is written, the packages are identical to the previous ones

# Tasks

- [ ] **Backend: lineage schema and storage**
  - [ ] Migration: tables for nodes (artifact reference cleared on artifact deletion, copy of name/type/collection, coordinates, uniqueness of a live artifact per orbit), edges (unique pair, no loops, cascade from nodes), input declarations (per artifact; index by identity kind and value within the orbit; `resolved_at`), artifact identities (index by kind and value within the orbit)
  - [ ] ORM models and schemas: node, edge, declaration, identity, edge end reference, batch request and response, graph with `unresolved_inputs`
  - [ ] Lineage repository: get-or-create a node by artifact; nodes by identifiers; bulk edge creation; edges by identifiers; edges by pairs in both directions; edge deletion; position writes; cleanup of edgeless nodes; breadth-first traversal with the limit; an artifact's declarations; the orbit's unresolved declarations by identity; marking resolution; registering and deleting identities; the orbit's artifacts by identity
  - [ ] Repository integration tests: node lifecycle, uniqueness, traversal (depth, cycle, limit, level 1), positions, cleanup, lookup by identity

- [ ] **Backend: lineage operations and API**
  - [ ] Handler: "apply changes" (transaction; deletions → creations → positions → cleanup; all checks and codes from Design; `created_via` from the authentication type); single create; single delete with the ownership check; graph read (empty graph without a node, the three copied fields for deleted nodes, coordinates, `unresolved_inputs`)
  - [ ] Permissions: artifact read and update
  - [ ] Orbit-level routes: graph, single create, single delete, batch
  - [ ] Handler and route unit tests for the "writes" and "reading the graph" scenarios

- [ ] **Backend: declared inputs and artifact deletion**
  - [ ] Optional declarations field in the artifact create request; validation of `artifact_id` declarations before creation; dropping self-declarations and duplicates
  - [ ] On creation: identity registration (hash; an experiment's `experiment_id` from the manifest); forward and reverse resolution with the rules "all matches", "once", "no duplicates", "do not argue with a reverse edge"; `platform` edges
  - [ ] On physical artifact deletion: refresh the copy and clear the reference on a node with edges, delete a node without edges, delete declarations and identities
  - [ ] Unit and integration tests for the "resolving declarations" and "artifact deletion" scenarios

- [ ] **API client: lineage and declarations on upload**
  - [ ] Types for the graph, node, edge, declaration, reference
  - [ ] `get_lineage`, `log_lineage`, `remove_lineage` in the base, sync and async resources, with docstrings
  - [ ] Reading `lineage_inputs` blocks from the package in the same archive pass; merging with the `lineage_inputs` parameter; passing into the create request; `upload` docstring
  - [ ] Unit tests (HTTP mocked): URLs, bodies, response parsing, exceptions, declarations from the package and the parameter, no field without declarations, rejection before the file upload, async variant

- [ ] **`luml` SDK: declaring inputs**
  - [ ] Building a declaration from a reference (file hash, type, name; for an experiment — the identifier from the manifest); `add_lineage_inputs` method on references that appends a block
  - [ ] `lineage_inputs` in the five model save functions and the two dataset ones
  - [ ] Tracker: `lineage_inputs` in `start_experiment`, `add_lineage_inputs` method, storage in the local store (migration), block written on experiment export; automatic experiment declaration in `log_model` and `link_to_model`
  - [ ] Parameter documentation in docstrings with the "hash as is" caveat
  - [ ] Unit tests for the "`luml` SDK" scenarios on temporary packages

- [ ] **Frontend: API client and lineage store**
  - [ ] Types for the graph, references, batch; client methods at the orbit level
  - [ ] Store: loading with focal node synthesis, applying saved coordinates, full and partial auto-layout, state mapping, `unresolved_inputs`, depth, `truncated`
  - [ ] Store: diff with `node_id`/`artifact_id` references, positions of all nodes, Replace as delete + create + position, unconnected-node blocker, keeping edits on error, moving as an edit
  - [ ] Store: connection validation; Unlink; "Reset positions" without losing edits
  - [ ] Store unit tests for the logic-related UI scenarios

- [ ] **Frontend: Lineage tab interface**
  - [ ] Loading on open and on artifact change; leave confirmation with edits
  - [ ] Node: live / focal / deleted states; menu; handles and arrow direction
  - [ ] Details panel with "Open artifact" and "Focus lineage" links
  - [ ] Toolbar: depth, edge deletion with the keyboard, empty state, truncation notice, unresolved-inputs indicator with the list, toasts
  - [ ] Collection page: reload on collection change in the URL
  - [ ] Type check and lint; manual walkthrough of the UI scenarios
