# Proposals

A flow's history is one journal with one step counter. Every transaction gets the next number, whichever lane it lands on, and some land on no lane at all. A lane's own steps are the subset of lines that belong to it:

```
step 48  main     edit score
step 49  main     run score
step 50  main     edit features
step 51  —        env changed (no lane)
step 52  sweep    edit train
step 53  sweep    run train
step 54  main     rewind to 49
step 57  exp/lr   lane started from main
```

Here `main` owns 48, 49, 50 and 54; `sweep` owns 52 and 53. Rewinding a lane names a global step and restores what that lane selected at that moment. A checkpoint marks one of a lane's own steps under a sentence somebody wrote, so it can be found again. Steps are recorded automatically; checkpoints are optional. None of this changes.

Two things are half visible. First, the fork. The store records that `exp/lr` was created at step 57 from `main`. `lumlflow lane new` and `lane list` say "started from main at step 57", and the workbench header says only "started from main · N steps ago", naming no step. But what `exp/lr` copied is `main` as it stood at step 54, its last own line before the fork; `main` did not change between 54 and 57. And `main`'s own timeline shows nothing at all: the fork line belongs to `exp/lr`. So from the parent's side it is not clear where a lane left, and the number the surfaces quote is the moment of the fork rather than the parent's step it came from.

Second, the checkpoint. The workbench has the control, but inside the step timeline popover, two clicks deeper than "new lane" next to it. An agent has no control at all: the daemon has the operation and the workbench uses it, but there is no CLI verb and no MCP tool, so an agent reads a lane's checkpoint in `context` and can never set one.

The proposal finishes the surfaces without changing the model. A fork reads as "started from main's step 54" on every surface that quotes a step — `lane new`'s printed line, `lane list`, the child's header — and `main`'s timeline marks row 54 with the lanes that started there. "Mark this point" moves up beside "new lane". The CLI gains `lumlflow checkpoint` and the MCP server gains a `checkpoint` tool, both calling the daemon operation that exists, and the agent guide names them.

*Note: automatic checkpoints at forks and rewinds were considered and rejected. A rewind already reads back as its own row and the steps it left stay in the history, so a marker would add nothing. A fork is made visible from what the store already records.*

Scope constraint: this is the smallest change that makes the surfaces agree. No new journal ops, no schema change, no new store state, and no daemon change beyond deriving one number, served in the lane tree and the fork reply. Anything that could be done with what the client already receives is done in the client.

# Design

## What the store already records

`Branches.fork` in `lumlflow/flow/store/branches.py` commits one `BranchCreated(branch_id, name, parent_branch_id, fork_step=self._store.next_step)` with `branch=created.branch_id`. Two consequences the design leans on, both verified against the code:

- `fork_step` is the fork transaction's own global step (`FlowStore.commit` assigns `step=self._next_step`, the same number). The `branches` table in `lumlflow/flow/store/index.py` keeps it as `fork_step`; the tree query serves it as `forked_at_step`.
- The fork line is scoped to the **child**. `transactions.branch` holds the child's `branch_id`, so a query for the parent's own lines at or before `fork_step` excludes the fork line by construction.

Every lane, `main` included, owns the line that created it: `FlowStore.init` in `lumlflow/flow/store/flowstore.py` commits `[FlowInit, BranchCreated(main)]` with `branch=main.branch_id` at step 1, and every later fork's first line is its own creation. So the parent's newest own line at or before any fork from it always exists in a journal this store wrote; the fallback below is defensive.

The index keeps `branches(branch_id, name, parent_branch_id, fork_step, archived)` read back as `BranchRow`, and `transactions(step, ts, actor, intent, offline, settled, marker, branch, ops)`. Nothing here changes: no column, no op, no `INDEX_SCHEMA_VERSION` bump (it stays 10).

`Api.checkpoint` in `lumlflow/flow/daemon/api.py` resolves `(session, branch)` through `_read` (so `branch` defaults to the session's lane via `_branch`), refuses a blank `intent` with `FlowError("a checkpoint needs a one-line intent")`, journals a `Checkpointed` marker through `Branches.checkpoint`, and answers `{"branch", "step", "intent", "ts", "settled"}`. The workbench calls it through `useFlowOps.checkpoint(intent, branch)`; nothing else does. The method does not change.

## The parent's step at a fork

The daemon derives one number from the fork record: the parent's step at the fork, which is the newest transaction on the parent lane at or before the fork's global step. In the example above it is 54. When the parent has no line of its own at or before the fork, the fork's own step is used.

One lookup is added to `Index` in `lumlflow/flow/store/index.py`, beside `checkpoint` and `transaction`, in the same `ORDER BY step DESC LIMIT 1` style `checkpoint` uses:

```python
def last_step_on(self, branch_id: str, *, at_or_before: int) -> int | None:
    """The branch's newest own line at or before a global step — what a fork copied."""
    row = self._conn.execute(
        "SELECT step FROM transactions WHERE branch = ? AND step <= ? "
        "ORDER BY step DESC LIMIT 1",
        (branch_id, at_or_before),
    ).fetchone()
    return int(row["step"]) if row is not None else None
```

`_branch()` in `lumlflow/flow/daemon/queries.py` — the per-lane payload `tree()` builds — already resolves `parent = index.branch_by_id(record.parent_branch_id)`. It derives the number from that and adds one key directly after `forked_at_step`:

```python
parent_step: int | None = None
if parent is not None:
    # The fork line is scoped to the child, so `at_or_before=fork_step` never
    # picks it up; a parent with no own line by then falls back to the fork.
    found = index.last_step_on(parent.branch_id, at_or_before=record.fork_step)
    parent_step = record.fork_step if found is None else found
...
    "forked_at_step": record.fork_step,
    "parent_step": parent_step,
```

`parent_step` is `None` on a root lane, exactly as `parent` is. `forked_at_step` stays and keeps its meaning. The two names stay distinct because they answer different questions: when the lane was made, and what it was made from. In the example `exp/lr` carries `forked_at_step` 57 and `parent_step` 54; a lane `sweep/a` forked at 21 from a `sweep` created at 20 with nothing since carries `parent_step` 20, the line that created `sweep`.

`Api.fork`'s reply gains the same number: it answers `{branch, from_branch, forked_at_step, cells}` today and adds `parent_step`, derived with the same lookup after the fork commits (the fork line is the child's, so the answer matches what `tree` will serve). `lumlflow lane new`'s printed line in `lumlflow/flow/cli.py` quotes it — "started `sweep` from `main` at step 54 · 3 cells, no file copied" — so the number `lane new` prints is the number `lane list` shows a moment later. The workbench's toast after a fork names only the lane and its cell count, quotes no step, and does not change.

Surfaces that quote the fork use `parent_step`:

- `render.tree` in `lumlflow/flow/render.py`: the family text becomes `f"started from {branch['parent']} at step {branch['parent_step']}"`; the root-lane text stays "a root lane". `lumlflow lane list` reads "started from main at step 54". The existing `test_starting_from_another_lane_says_which_one_it_started_from` looks for the substring "started from alpha" and keeps passing.
- The workbench lane identifier (below) reads "started from main · step 54 · N steps ago", where N is `headStep - parentStep`, so both numbers on the line share one anchor.

The lane map (`frontend/src/flow/workbench/components/graph/BranchGraph.vue`) keeps laying lanes out on `forkedAtStep`: it is geometry on the global-step axis, quotes no number, and is not touched.

## Types on the client

`frontend/src/flow/api/types.ts` `BranchRecord` gains `parent_step: number | null` after `forked_at_step`, required like every other field of the wire record. `frontend/src/flow/workbench/model/types.ts` `BranchInfo` gains `parentStep: number | null` beside `forkedAtStep`, with a doc comment: the parent's own step this lane copied; `null` on a root lane. `branchInfo()` in `frontend/src/flow/workbench/live/useWorkbench.ts` maps it the way `forkedAtStep` is mapped:

```ts
parentStep: record.parent === null ? null : record.parent_step,
```

`familyLine` in `BranchIdentifier.vue` interpolates the new number, so its root-lane guard widens to `parent === null || forkedAtStep === null || parentStep === null`, which also narrows the type at the interpolation site; without it an inconsistent record would render "step null".

`tsconfig.vitest.json` type-checks `tests/**`, so every typed `BranchRecord` literal gains `parent_step` (`null` on root lanes, a plausible own step of the parent otherwise): `branchRecord()` in `frontend/tests/flow-branch-nav.spec.ts`, `BRANCHES` in `frontend/tests/flow-live-workbench.spec.ts`, `branchRecords()` in `frontend/tests/flow-compare.spec.ts`. The six `BranchInfo` fixtures in `frontend/src/flow/workbench/fixtures/flow.ts` gain `parentStep` (`null` on `main`; for each other lane, a step of `main` at or before its `forkedAtStep`). The `BRANCHES` literal in `frontend/tests/flow-handoff.spec.ts` is untyped and only returned from a `Handlers` function typed `unknown`, so it needs nothing. If the `fork` reply type in `frontend/src/flow/api/client.ts` spells its payload, it gains the key; nothing on the client reads it.

## Where child lanes started, on the parent's timeline

The client already receives the whole tree (`BranchRecord[]` from `tree`) and a bounded journal window — `KEPT_TRANSACTIONS = 200` in `frontend/src/flow/workbench/live/useFlowSession.ts` — where `journalEntry()` maps a `branch_created` op to kind `'fork'` and `entry.branch` is the **child's name** resolved through the `branch_id → name` map. Everything below is client-side. A marker can only decorate a row the timeline holds: a fork whose `parent_step` has left the kept window renders no marker, exactly as the row itself is no longer listed.

**Direct children.** `frontend/src/flow/workbench/components/panel/LeftPanel.vue` already holds `branches` and `viewedBranch`. It computes

```ts
const children = computed(() => props.branches.filter((b) => b.parent === props.viewedBranch))
```

and passes `:children="children"` to `BranchIdentifier`, which adds a `children: BranchInfo[]` prop and forwards it unchanged to `<StepTimeline :children="children">`. Only direct children are in that list: a grandchild's `parent` is the child, so it lands on the child's timeline and nowhere on the grandparent's. The lane map remains the place to see the whole tree. Archived children are marked like any other: they did start there.

**The marker.** `frontend/src/flow/workbench/components/branch/StepTimeline.vue` gains a prop `children?: BranchInfo[]` (default `[]`) and one computed:

```ts
/** Which lanes started from each of this lane's own steps, in tree order. */
const startedHere = computed(() => {
  const at = new Map<number, string[]>()
  for (const child of props.children ?? []) {
    if (child.parentStep === null) continue
    at.set(child.parentStep, [...(at.get(child.parentStep) ?? []), child.name])
  }
  return at
})
```

A row whose `entry.step` is a key of `startedHere` renders one decoration inside its `<Button data-testid="step-row">`, as a third line under `step N · time · actor`: a `<span data-testid="started-here" class="flex items-center gap-1 text-sm text-muted-color">` holding the lucide `Split` glyph (`aria-hidden`, the glyph `JournalFeed.vue` already uses for the `fork` kind) and the text `` `${names.join(', ')} started here` `` — "exp/lr started here", or "exp/a, exp/b started here" when several lanes started on one row. The marker is a decoration: the row keeps its `Dot`/`Flag` glyph, its intent, its `current` tag when it is the head, its `aria-label` (`step N · intent`, unchanged so the existing row-picking tests keep matching), and its pick-and-confirm rewind through the untouched `onPick`/`confirmRewind`. Rewinding a marked row asks the daemon for `rewind {branch, to_step}` exactly as any other row and restores the parent's cells as they stood when the child split; the current row never offers a rewind, marked or not.

The timeline's `entries` stay `onThisBranch` from `LeftPanel` — the viewed lane's own lines — so the fork line (a child's own step) never appears as a row on the parent. The timeline reads the markers off the lane tree, not off the journal.

The activity feed does not change. Widening it to other lanes' fork lines would change what its "since you were here" window means and what `flow-live-workbench.spec.ts` documents as "another branch's work is another branch's"; the marker, the header, and `lane list` already carry the fork on the parent's side.

## Mark this point, from the lane identifier

`frontend/src/flow/workbench/components/panel/BranchIdentifier.vue` carries two actions in its action row: the step count (opens the `Popover` holding `StepTimeline`) and "new lane". A third `Button` goes after "new lane" with the label and glyph the timeline's own control uses: `label="mark this point"`, `<Flag :size="14" />` in the `#icon` slot, `text`, `severity="secondary"`, `size="small"`, `:pt="ACTION_PT"`, `:disabled="busy"`, `aria-haspopup="dialog"`, `:aria-label="`Mark this point on ${branch.name}`"`.

The prompt is the timeline's own; nothing is duplicated. `StepTimeline.vue` adds `defineExpose({ openMark })` — `openMark` already sets `marking`, clears the intent, and focuses the `InputText` labelled "what this point is". `BranchIdentifier` holds a template ref on the timeline (`ref="timeline"`, `const timeline = useTemplateRef<InstanceType<typeof StepTimeline>>('timeline')`) and the new action opens the popover if it is closed, then starts marking:

```ts
async function onMark(event: Event): Promise<void> {
  if (!stepsOpen.value) {
    stepsOpen.value = true
    steps.value?.show(event)
  }
  await nextTick()
  await timeline.value?.openMark()
}
```

The `nextTick` is needed because PrimeVue's `Popover` renders its slot under `v-if="visible"`: the timeline mounts on `show`, and the ref resolves a tick later. The same fact means the timeline unmounts on hide, so a popover reopened from the step count starts on its list, not the form, with no extra state to reset.

From there the gesture is the one that exists: the confirm `Button` disabled while `markIntent.trim()` is empty, `confirmMark` returning on a blank, the `checkpoint` emit, `BranchIdentifier.onCheckpoint` hiding the popover and re-emitting, `LeftPanel` forwarding, and `LiveWorkbench.onCheckpoint` in `frontend/src/flow/workbench/pages/LiveWorkbench.vue` calling `ops.checkpoint(intent, viewedBranch.value)` under the shared `branchBusy` guard. Because the branch sent is `viewedBranch`, marking a lane that is only being viewed marks that lane without touching the files; `switch` is never asked. The timeline keeps its own copy of the control; the two are the same gesture from two places, as "new lane" already is from the switcher and the identifier.

## The checkpoint verb

`lumlflow/flow/cli.py` gains a top-level verb, added to the `register()` tuple directly after `rewind`:

```python
def checkpoint(
    intent: str = typer.Option(
        ..., "-m", "--intent", help="What this point is. Recorded in the journal."
    ),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Mark this point on a lane under a one-line intent. Nothing is copied."""
    params = {"branch": lane, "intent": intent}
    result = _call("checkpoint", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [f"marked `{result['branch']}` at step {result['step']} · {result['intent']}"],
    )
```

`-m` is required at the option level (`typer.Option(...)`, the way `adopt --from` and `agent begin --label` spell a required option) rather than the shared optional `_INTENT`: Typer refuses `lumlflow checkpoint` without it with exit code 2 and `Missing option '-m' / '--intent'` before any daemon call, so the journal gains nothing. A whitespace-only `-m "  "` reaches the daemon, which refuses it as a `FlowError`; an unknown `--lane` is refused the same way with "no lane named …"; `_daemon` turns either into one line and exit code 1 through `_fail`, as for every verb. `_Daemon.call` drops `None` params, so an omitted `--lane` lets the daemon default to the lane on disk. `--json` prints the daemon payload verbatim through `_emit`. The docstring, the help and the printed line contain none of the words `GIT_WORDS` in `tests/daemon/helpers.py` bans; `test_no_visible_help_speaks_the_vocabulary_git_owns` walks every non-hidden command through `_visible_paths`, so the new verb's `--help` is swept automatically.

## The checkpoint tool

`lumlflow/flow/daemon/mcp.py` adds one `_Tool` to `TOOLS`, directly after `rewind`:

```python
_Tool(
    "checkpoint",
    "checkpoint",
    "Mark this point on the lane under your own words, so it can be found "
    "again. Nothing is copied or frozen. `context` reads the lane's latest one "
    "back.",
    (_INTENT,),
    writes=True,
),
```

The default `scope="branch"` appends `_FLOW` and `_BRANCH` to the schema (`lane` and `flow` among the properties, `required` exactly `["intent"]`) and makes `_invoke` default `lane` to the session's lane, the way `rewind` does; `_as_wire` renames `lane` to `branch`, and a `lane` naming no branch fails the tool, not the session, as the existing unknown-lane behaviour has it. `_INTENT` is the shared required argument and `_invoke` treats a whitespace value as blank, so a missing or blank `intent` fails inside the tool with `` FlowError("`checkpoint` needs `intent`") ``, returned as tool output with `isError`, following the existing missing-argument behaviour. `writes=True` is the flag every other mutating tool declares. `INSTRUCTIONS` does not change. The name, description and arguments contain none of `GIT_WORDS`, so `test_no_listed_tool_teaches_the_vocabulary_git_owns` keeps passing, and no `force` is declared, so `test_only_conflict_resolution_tools_declare_force` does too.

## The guide

`CHEATSHEET` in `lumlflow/flow/daemon/docs.py`, served as `lumlflow guide` and the `lumlflow://guide` resource, changes in three places:

- The "## Tools" sentence lists `checkpoint` between `rewind` and `adopt`: `` `new-lane` · `use-lane` · `rewind` · `checkpoint` · `adopt` · `diff` ``.
- One sentence follows that paragraph: "Mark a point with `checkpoint` before a rewrite you may want to come back from, or after a result worth finding again. `context` reports the lane's latest one."
- The "## The same, as verbs" list adds `` `lumlflow checkpoint -m "why"` `` after `` `lumlflow rewind <step>` ``.

None of the new text uses a word `no_git_words` rejects; `test_the_served_guide_never_speaks_the_vocabulary_git_owns` keeps passing.

*Note: the user guide in `docs/user-guide.md` carries a verb table that would also list the new verb. It is out of scope for now.*

## Trade-offs

- `parent_step` is derived on every `tree` read and once per fork, with one branch-filtered scan per lookup — the same shape `Index.checkpoint` already runs per lane (`transactions` has no index on `branch`). `_branch()` already runs `derive_all`, `checkpoint` and `history` per lane, so the cost is in proportion, and no schema, journal or rebuild path moves.
- Markers are computed in the client from the tree it already holds rather than served per row. The tree carries every child's `parent_step`, so nothing further is needed from the daemon; the price is that a marker exists only on rows inside the kept transaction window, which is the timeline's existing boundary.
- The identifier's "mark this point" opens the timeline popover into its existing prompt rather than carrying a second copy of the form. The price is one `defineExpose` and one `nextTick`; the gain is that the field, its label, the blank-intent guard and the emit path exist once and cannot drift.
- `BranchRecord.parent_step` is required, not optional, so the client type mirrors the wire exactly; the price is a one-line addition to each typed test builder.

## Dependencies and checks

No new dependencies. Python, from `lumlflow/`: `uv run pytest tests/flow/test_index.py tests/daemon/test_queries.py tests/daemon/test_cli.py tests/daemon/test_mcp.py tests/daemon/test_docs.py`, `uv run ruff check lumlflow tests`, `uv run ruff format --check lumlflow tests`, `uv run mypy lumlflow/flow`. Frontend, from `lumlflow/frontend`: `npm run type-check`, `npm test`, `npm run lint`.

# Scenarios

## Scenario: the index answers a lane's newest line at or before a step
**Given** an `Index` folded with transactions at steps 1 (branch A), 2 (branch B), 3 (branch A), 4 (no branch) and 5 (branch B)
**When** `last_step_on` is asked for A at or before 5, A at or before 2, B at or before 1 and an unknown branch at or before 5
**Then** it answers 3, 1, `None` and `None`

## Scenario: the tree carries the parent's step
**Given** `main` whose last own transaction is step 54, and `exp/lr` forked from it at global step 57
**When** the lane tree is read
**Then** `exp/lr` carries `forked_at_step` 57 and `parent_step` 54, and `main`, a root lane, carries `parent_step` `None`, as it carries `parent` `None`

## Scenario: the parent's step is its newest line before the fork
**Given** `main` marked at step C, then a checkpoint on `sweep` at step C+1, then `exp/lr` forked from `main` at step D
**When** `parent_step` is derived for `exp/lr`
**Then** it is C — not the line on `sweep` between, and not D — and after `main` gains a later line, re-reading the tree still gives C

## Scenario: a fork right after the parent was created
**Given** a fresh lane `fresh` forked from `main`, and `fresh/a` forked from `fresh` with no transaction on `fresh` in between
**When** `parent_step` is derived for `fresh/a`
**Then** it equals `fresh`'s own `forked_at_step`, the line that created `fresh`

## Scenario: the fork reply and lane list agree on the number
**Given** an initialised flow where `main`'s newest own step is N (read as `main.last_intent.step` from `lumlflow lane list --json`)
**When** `lumlflow lane new sweep` runs and `lumlflow lane list` runs after it
**Then** `lane new` prints "started `sweep` from `main` at step N", the listing reads "started from main at step N" for `sweep` and "a root lane" for `main`, and `lane list --json` shows `parent_step` N with `forked_at_step` greater than N

## Scenario: the child's header quotes the parent's step
**Given** the workbench viewing `exp/lr-sweep`, whose record carries `parent: 'main'`, `forked_at_step: 13`, `parent_step: 12` and `last_intent.step: 13`
**When** the lane identifier is read
**Then** it says "started from main · step 12 · 1 step ago" — the count anchored to `parentStep`, so a swap to `forkedAtStep` would read "0 steps"

## Scenario: the parent's timeline marks where a child started
**Given** the workbench viewing `main` with own lines at 12 and 14, and `exp/lr-sweep` with `parent_step` 12 and `forked_at_step` 13
**When** the step timeline for `main` is opened
**Then** the row for step 12 carries "exp/lr-sweep started here", no other row does, and no row exists for step 13

## Scenario: several lanes from one row
**Given** `exp/lr-sweep` and `exp/b`, both children of `main` with `parent_step` 12
**When** the timeline for `main` is opened
**Then** the row for step 12 reads "exp/lr-sweep, exp/b started here"

## Scenario: only direct children are marked
**Given** `exp/lr-sweep` forked from `main` with `parent_step` 12, and `exp/lr-sweep-2` forked from `exp/lr-sweep` with `parent_step` 13, where step 13 is `exp/lr-sweep`'s own creation line
**When** the timeline for `main` is opened
**Then** `exp/lr-sweep` is named on row 12 and `exp/lr-sweep-2` is named on no row of `main`; viewing `exp/lr-sweep` and opening its timeline names `exp/lr-sweep-2` on its row 13

## Scenario: rewinding the parent to the split
**Given** `main` at head step 14 with a fork marker on row 12
**When** row 12 is picked through its unchanged label "step 12 · added features" and "rewind to step 12" is confirmed
**Then** the confirm read "restores the cells" and the daemon is asked for `rewind` with `branch: 'main'` and `to_step: 12`, exactly as for an unmarked row

## Scenario: the marked row is the current one
**Given** `main` whose head is step 14, and `exp/head` forked from it with `parent_step` 14
**When** the timeline for `main` is opened and row 14 is picked
**Then** row 14 reads "current" and "exp/head started here", and no "rewind to step 14" is offered or sent

## Scenario: marking a point from the lane identifier
**Given** the workbench viewing `main`
**When** the identifier's "Mark this point on main" is pressed, "before I rewrite the scorer" is typed into "what this point is", and "mark this point" is confirmed
**Then** the daemon is asked for `checkpoint` with `branch: 'main'` and that intent exactly once, and once the `checkpointed` transaction arrives on the stream the timeline shows "before I rewrite the scorer" as a flagged row

## Scenario: marking a lane that is not on disk
**Given** the workbench viewing `exp/lr-sweep` while `main` is on disk
**When** "mark this point" is used from the identifier with intent "baseline"
**Then** the daemon is asked for `checkpoint` with `branch: 'exp/lr-sweep'`, and `switch` is never asked

## Scenario: an empty intent cannot be submitted
**Given** the mark form opened from the lane identifier
**When** the intent is "   " and "mark this point" is pressed
**Then** the confirm button is disabled and no `checkpoint` call is made

## Scenario: the timeline keeps its own mark control
**Given** the step timeline opened from the step count
**When** its own "mark this point" is used with an intent
**Then** the daemon is asked for the checkpoint exactly as before the identifier gained the control, and the existing timeline checkpoint tests pass unchanged

## Scenario: the CLI marks the lane on disk
**Given** an initialised flow with `main` on disk and one cell
**When** `lumlflow checkpoint -m "the one that scored"` runs
**Then** it exits 0, prints "marked `main` at step N · the one that scored", leaks no internals, and `lumlflow context --json` reports `checkpoint.step` N and `checkpoint.intent` "the one that scored"

## Scenario: the CLI marks another lane
**Given** lanes `main` on disk and `sweep`
**When** `lumlflow checkpoint --lane sweep -m "baseline"` runs
**Then** `lumlflow lane list --json` shows `sweep.checkpoint` equal to the printed step and `main.checkpoint` different from it

## Scenario: the CLI refuses a missing intent
**Given** an initialised flow
**When** `lumlflow checkpoint` runs without `-m`
**Then** it exits 2, the output names `--intent`, and `lumlflow context --json` lists the same `recent` transactions as before

## Scenario: the CLI passes a blank intent to the daemon's refusal
**Given** an initialised flow
**When** `lumlflow checkpoint -m "   "` runs
**Then** it exits 1 and prints "a checkpoint needs a one-line intent"

## Scenario: the CLI refuses an unknown lane
**Given** an initialised flow with only `main`
**When** `lumlflow checkpoint --lane nowhere -m "x"` runs
**Then** it exits 1, prints "no lane named nowhere" with no traceback, and the journal gains no transaction

## Scenario: the CLI returns JSON
**Given** an initialised flow
**When** `lumlflow checkpoint -m "baseline" --json` runs
**Then** the output parses to an object with keys `branch`, `step`, `intent`, `ts` and `settled`, with `branch` "main" and `intent` "baseline"

## Scenario: the CLI verb speaks no git word
**Given** the sweeps in `test_no_visible_help_speaks_the_vocabulary_git_owns` and `test_no_verb_prints_the_vocabulary_git_owns`
**When** `lumlflow checkpoint --help` and `lumlflow checkpoint -m "worth keeping"` run
**Then** neither output matches `GIT_WORDS`

## Scenario: the MCP tool marks the session's lane
**Given** an MCP session that created a flow, started `sweep` with an intent, and moved onto it with `use-lane`
**When** the `checkpoint` tool is called with `{"intent": "baseline"}`
**Then** the reply has `branch` "sweep", a `step` and `intent` "baseline"; `context` on that session reports `checkpoint.step` equal to it; and `context` with `lane: "main"` reports a different checkpoint or none

## Scenario: the MCP tool refuses a missing intent
**Given** an MCP session on a flow
**When** `checkpoint` is called with `{}`
**Then** the tool result has `isError` and its text contains `` `intent` ``, following the existing missing-argument behaviour

## Scenario: the MCP tool refuses an unknown lane
**Given** an MCP session on a flow with only `main`
**When** `checkpoint` is called with `{"lane": "nowhere", "intent": "x"}`
**Then** the tool result has `isError`, its text names `nowhere`, and the session survives

## Scenario: the tool list carries checkpoint as a write
**Given** `tools/list` and `mcp.TOOLS`
**When** the `checkpoint` entry is read
**Then** it is listed with `required` exactly `["intent"]`, `lane` and `flow` among its properties, no `force`, `writes` true, and its name, description and arguments pass `no_git_words`

## Scenario: the guide names the new surfaces
**Given** `docs.CHEATSHEET`
**When** it is read through `lumlflow guide` or `lumlflow://guide`
**Then** `` `checkpoint` `` appears in the tools list, `lumlflow checkpoint -m "why"` in the verbs list, the phrase "worth finding again" is present, and `no_git_words` still passes

# Tasks

- [x] Derive the parent's step at a fork and quote it everywhere a fork is quoted
  - [x] Add `Index.last_step_on(branch_id: str, *, at_or_before: int) -> int | None` to `lumlflow/flow/store/index.py` beside `checkpoint`, one `SELECT step FROM transactions WHERE branch = ? AND step <= ? ORDER BY step DESC LIMIT 1`
  - [x] In `_branch()` in `lumlflow/flow/daemon/queries.py`, derive `parent_step` from the already-resolved `parent` and `record.fork_step`, falling back to `record.fork_step` when the lookup returns `None`, and add `"parent_step"` to the payload directly after `"forked_at_step"` (`None` on a root lane)
  - [x] In `Api.fork` in `lumlflow/flow/daemon/api.py`, add the same derived `"parent_step"` to the reply after the fork commits
  - [x] In `lumlflow/flow/cli.py`, make `lane new`'s printed line quote `result['parent_step']` instead of `forked_at_step`; change the family f-string in `render.tree` in `lumlflow/flow/render.py` to quote `branch['parent_step']`
  - [x] In `tests/flow/test_index.py`, using the `index` fixture and `tests/flow/helpers.transaction` with `branch=`: fold lines at 1 (A), 2 (B), 3 (A), 4 (no branch), 5 (B) and assert `last_step_on` answers 3, 1, `None` and `None` for A@5, A@2, B@1 and an unknown branch
  - [x] In `tests/daemon/test_queries.py` with `daemon_api`, `api.flow_open`, `api.checkpoint`, `api.fork` and `api.tree`: assert `main["parent_step"] is None`; mark `main` (step C), mark another lane in between, fork `exp/lr` from `main` and assert its reply and the tree both carry `parent_step == C` with `forked_at_step > C`, then mark `main` again and assert the re-read tree still gives C. In a separate test, fork `fresh` from `main` and immediately fork `fresh/a` from `fresh` with no transaction on `fresh` in between, and assert `parent_step == fresh["forked_at_step"]`
  - [x] In `tests/daemon/test_cli.py` with the `cli` fixture: `init churn`, `write_cell score`, read `main.last_intent.step` from `lane list --json` as N, run `lane new sweep`, and assert it prints `at step N`, that `lane list` prints `started from main at step N` and `a root lane`, and that `--json` carries `parent_step == N` and a larger `forked_at_step`; confirm `test_starting_from_another_lane_says_which_one_it_started_from` still passes
  - [x] Run `uv run pytest tests/flow/test_index.py tests/daemon/test_queries.py tests/daemon/test_cli.py`, `uv run ruff check lumlflow tests`, `uv run ruff format --check lumlflow tests`, `uv run mypy lumlflow/flow` in `lumlflow/`
- [x] Carry the parent's step into the workbench and mark where each child lane started on the parent's timeline
  - [x] Add `parent_step: number | null` to `BranchRecord` in `frontend/src/flow/api/types.ts` and `parentStep: number | null` to `BranchInfo` in `frontend/src/flow/workbench/model/types.ts`; map `parentStep: record.parent === null ? null : record.parent_step` in `branchInfo()` in `frontend/src/flow/workbench/live/useWorkbench.ts`
  - [x] Add `parentStep` to the six `BranchInfo` fixtures in `frontend/src/flow/workbench/fixtures/flow.ts` and `parent_step` to `branchRecord()` in `frontend/tests/flow-branch-nav.spec.ts`, `BRANCHES` in `frontend/tests/flow-live-workbench.spec.ts` and `branchRecords()` in `frontend/tests/flow-compare.spec.ts`, keeping every fixture on the invariant `parent_step <= forked_at_step`
  - [x] Change `familyLine` in `frontend/src/flow/workbench/components/panel/BranchIdentifier.vue` to `` `started from ${parent} · step ${parentStep} · ${formatCount(headStep - parentStep, 'step')} ago` ``, widening the root-lane guard to include `parentStep === null`; add a `children: BranchInfo[]` prop forwarded to `StepTimeline`
  - [x] In `frontend/src/flow/workbench/components/panel/LeftPanel.vue` compute `children` (branches whose `parent` is `viewedBranch`) and pass `:children` to `BranchIdentifier`; `onBranch` and `onThisBranch` stay untouched
  - [x] In `frontend/src/flow/workbench/components/branch/StepTimeline.vue` add the `children` prop, the `startedHere` map keyed by `parentStep`, and the `data-testid="started-here"` line with the lucide `Split` glyph and `"{names} started here"` under the `step N · time · actor` line, leaving the row's `aria-label`, `current` tag, `onPick` and `confirmRewind` untouched
  - [x] In `frontend/tests/flow-branch-nav.spec.ts`, add a `describe` on a tree of `main` (root: `parent: null`, `parent_step: null`, `last_intent.step: 14`), `exp/lr-sweep` (`parent: 'main'`, `forked_at_step: 13`, `parent_step: 12`, `last_intent.step: 13`), `exp/b` (`parent: 'main'`, `forked_at_step: 15`, `parent_step: 12`), `exp/head` (`parent: 'main'`, `forked_at_step: 16`, `parent_step: 14`) and `exp/lr-sweep-2` (`parent: 'exp/lr-sweep'`, `forked_at_step: 17`, `parent_step: 13`), with journal lines 12 and 14 on `branch-main` and a `branch_created` line at 13 on `exp/lr-sweep`'s branch id; cover the child header reading the full `started from main · step 12 · 1 step ago`, row 12 reading `exp/lr-sweep, exp/b started here` and no `step 13` row, the grandchild absent from `main`'s timeline and named on `exp/lr-sweep`'s row 13 after `pickBranch('exp/lr-sweep')`, rewind from row 12 via `clickOverlayButton('step 12 · added features')` then `rewind to step 12` asking `rewind` with `to_step: 12`, and the current row 14 reading `current` and `exp/head started here` with no `rewind to step 14`
  - [x] Run `npm run type-check`, `npm test` and `npm run lint` in `lumlflow/frontend`
- [ ] Offer mark this point from the lane identifier
  - [ ] Add `defineExpose({ openMark })` to `frontend/src/flow/workbench/components/branch/StepTimeline.vue`
  - [ ] In `frontend/src/flow/workbench/components/panel/BranchIdentifier.vue` add the third action after "new lane" — label `mark this point`, `Flag` glyph, `ACTION_PT`, `:disabled="busy"`, `aria-haspopup="dialog"`, `aria-label` `Mark this point on {lane}` — put `ref="timeline"` on `StepTimeline`, and add `onMark` which shows the steps popover if closed, awaits `nextTick`, and calls the timeline's `openMark`; leave `onCheckpoint` and the emit chain untouched
  - [ ] In `frontend/tests/flow-branch-nav.spec.ts` under the checkpoint `describe`: click `button[aria-label="Mark this point on main"]`, `typeInto('what this point is', ...)`, `clickOverlayButton('mark this point')`, assert `asked(live, 'checkpoint')` matches `[expect.objectContaining({ branch: 'main', intent })]` with length 1 (the request also carries `flow`, as the existing checkpoint test acknowledges with `objectContaining`), deliver the `checkpointed` transaction and assert the flagged row; `pickBranch('exp/lr-sweep')` first and assert the call carries `branch: 'exp/lr-sweep'` with `asked(live, 'switch')` empty; type `'   '` and assert no call; confirm the existing popover-path checkpoint tests still pass
  - [ ] Run `npm run type-check`, `npm test` and `npm run lint` in `lumlflow/frontend`
- [ ] Add the checkpoint verb to the CLI
  - [ ] Add `checkpoint(intent, flow, lane, as_json)` to `lumlflow/flow/cli.py` beside `rewind`, with a required `-m/--intent` (`typer.Option(...)`), `_FLOW`, `_LANE` and `_JSON`, calling `_call("checkpoint", {"branch": lane, "intent": intent}, flow=flow, as_json=as_json)` and emitting `` marked `{branch}` at step {step} · {intent} ``; add it to the `register()` tuple after `rewind`
  - [ ] In `tests/daemon/test_cli.py`: `init churn`, `write_cell score`, run `checkpoint -m "the one that scored"`, assert exit 0, the printed line, no leaked internals, and that `context --json` reports the same `checkpoint.step` and `checkpoint.intent`; `lane new sweep` then `checkpoint --lane sweep -m "baseline"` and assert from `lane list --json` that `sweep.checkpoint` is the returned step and `main.checkpoint` is not; run `checkpoint` with no `-m`, assert exit 2, `--intent` in the output, and `context --json`'s `recent` unchanged; run `checkpoint -m "   "`, assert exit 1 and `a checkpoint needs a one-line intent`; run `checkpoint --lane nowhere -m "x"`, assert exit 1 and `no lane named nowhere`; run with `--json` and assert the keys `branch`, `step`, `intent`, `ts`, `settled` with `branch == "main"`; add `("checkpoint", "-m", "worth keeping")` to the `spoken` list in `test_no_verb_prints_the_vocabulary_git_owns`
  - [ ] Confirm `test_no_visible_help_speaks_the_vocabulary_git_owns` still passes with the new verb reachable from `--help`
  - [ ] Run `uv run pytest tests/daemon/test_cli.py`, `uv run ruff check lumlflow tests`, `uv run ruff format --check lumlflow tests`, `uv run mypy lumlflow/flow` in `lumlflow/`
- [ ] Serve checkpoint as an MCP tool and name it in the guide
  - [ ] Add the `checkpoint` `_Tool` to `TOOLS` in `lumlflow/flow/daemon/mcp.py` directly after `rewind`, method `checkpoint`, args `(_INTENT,)`, default `branch` scope, `writes=True`
  - [ ] Edit `CHEATSHEET` in `lumlflow/flow/daemon/docs.py`: add `` `checkpoint` `` to the Tools sentence between `rewind` and `adopt`, the sentence on when to mark a point after that paragraph, and `` `lumlflow checkpoint -m "why"` `` to the verbs list after `` `lumlflow rewind <step>` ``
  - [ ] In `tests/daemon/test_mcp.py`, with `talk`, `hello`, `tool`, `answered` and `failed`: `init-flow`, `new-lane {name: "sweep", intent: "trying a sweep"}`, `use-lane {lane: "sweep"}`, `checkpoint {intent: "baseline"}`, `context {}`, `context {lane: "main"}` — assert the checkpoint answer has `branch == "sweep"`, a `step` and `intent == "baseline"`, the session's `context` carries that step, and `main`'s does not; call `checkpoint` with `{}` and assert `` `intent` `` in `failed(...)`; call `checkpoint` with `{"lane": "nowhere", "intent": "x"}` and assert `nowhere` in `failed(...)`; in the `tools/list` test assert `checkpoint` is listed with `inputSchema.required == ["intent"]` and `lane` among its properties; confirm `test_only_conflict_resolution_tools_declare_force` and `test_no_listed_tool_teaches_the_vocabulary_git_owns` still pass
  - [ ] In `tests/daemon/test_docs.py` extend `test_the_served_guide_names_the_current_agent_surface` to assert `"`checkpoint`"`, `'lumlflow checkpoint -m "why"'` and `"worth finding again"` are in `docs.CHEATSHEET`; confirm `test_the_served_guide_never_speaks_the_vocabulary_git_owns` still passes
  - [ ] Run `uv run pytest tests/daemon/test_mcp.py tests/daemon/test_docs.py`, `uv run ruff check lumlflow tests`, `uv run ruff format --check lumlflow tests`, `uv run mypy lumlflow/flow` in `lumlflow/`
