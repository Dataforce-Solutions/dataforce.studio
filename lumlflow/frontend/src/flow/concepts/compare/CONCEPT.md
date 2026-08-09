# Concept 2 — Compare and compose workspace

Route: `/flow/compare`. Owned files: `concepts/CompareConcept.vue`, `concepts/compare/*`.

## Mental model

**The selection of 2–5 branches _is_ the workspace.** There is no "the workspace,
and also a diff view" — there is no view of a single branch at all. You pick the
variants you are supervising, and every surface below is a projection of that
selection:

- the **fan graph** shows *where* they differ, and only there;
- the **result panes** show *what* the difference did to the numbers;
- the **difference table** is the exhaustive fallback for differences that have
  no shape (renames, absences, params);
- the **committed path** is the one slice you are keeping, and the thing export
  freezes.

The verbs are pick a winner, cherry-pick across, export the winner. Each maps to
one gesture: click a branch under *pick winner*, click a ghosted variant in the
graph, press *export this path*.

## What it bets on

**Fan out → compare → keep the winner → export is the reason the product
exists**, so comparison should be the architecture rather than a panel. Three
sub-bets carry it:

### 1. Fan on definition divergence, collapse materialization divergence

Under `version = hash(source + params + upstream versions)`, divergence is
transitively closed downstream. Every asset below `Features` really is a
different materialization in every branch. Drawing that faithfully is a wall:
five branches × everything downstream, and the shape carries no information,
because the *code* is identical — only the inputs moved.

So the graph fans only where `DivergenceKind === 'definition'`, and collapses
`'materialization'` into a single node carrying N result chips. On the churn
fixture with five variants that is **5 code fans and 6 value fans**; on the
`large` fixture with five of twenty branches it is **1 code fan and 67 value
fans** — one fan point, `Features`, and everything else a chip row. That ratio is
the whole argument.

The result chips are grouped by an *effective content key*
(`useComparison.ts: effectiveKey`) — the version folded with the keys of every
upstream. This is derived, not decorative: the fixture's branches literally share
`TrainTestSplit@v1`, but four of the five selected slices feed it a different
`Features`, so the node honestly reads **"value fan · 4 distinct results"**. The
same key drives the composed path's cache arithmetic, so "branches that share an
unchanged asset share the same cached materialization" is computed, not asserted.

### 2. Correlation highlight, because the canvas otherwise lies

Five variants over the churn fixture produce fans of width 2, 3, 3, 2, 2 — the
canvas lays out **72 combinations when only 5 were ever run**. That number is
printed above the graph, and hovering any variant greys every variant in every
other fan that never co-occurred with it in a real slice. Without this the
layout is a claim about the search space that is false by an order of magnitude.

### 3. Swap-to-compose, with conflicts surfaced

Clicking a ghosted variant swaps it onto the committed path. This composes a
slice nobody ran, so it can be interface-incompatible in a way no branch is. Two
detectors, in `compat.ts`:

- **Derived, from the object model**: a committed version whose `deps` name an
  asset the path does not contain. Reachable in the fixture via the structural
  rewire — take `model/logreg`'s `HoldoutEval@v2` onto a path that still has
  `TrainGBM`, and you get *"`HoldoutEval` v2 reads `TrainLogReg`, which this path
  does not contain."*
- **Declared, and deliberately fabricated**: nothing in `AssetVersion` can say
  "this version needs *that* upstream version", so the requirement is written
  down explicitly in `declaredRequirements` rather than smuggled into the
  fixture. `Features@v2` calls `pd.qcut(tenure, 8)`, which raises on non-unique
  bin edges, so bucketing only works against the deduplicated `RawChurn@v2`. Take
  the bucketed features from `feat/tenure-buckets` and the stale pin from a sweep
  branch and you get *"`Features` v2 expects `RawChurn` v2, the current path has
  v1 — tenure bucketing needs deduplicated rows."* The node turns red, the
  incoming edge turns red, and **export is disabled**.

A merge model that silently pretends composition always works is the thing worth
not demoing.

## Where editing lives

**In the variant inspector, opened from a fan point — never a file tree, never a
global editor pane.** Clicking any variant chip opens that version's source in
the path panel, with its author, its intent, and its failure message if it has
one. It is read-only with a disabled *take over* button, because the human cannot
steer agents from the UI: taking over is an explicit detach of that agent from
that asset, after which the definition opens in your editor against the live
kernel. Saving authors a *new version* and widens the fan — it never overwrites
what the agent produced. The panel says so.

The reasoning: in a comparison-first workspace the only time you want to read
code is when you are asking "why is this variant different", and that question is
always asked *at a fan point about one version*. Scoping the editor to that makes
the code panel small enough to live inside the comparison instead of replacing it.

## Mandatory list — where each thing is

| # | Where |
|---|---|
| 1 Live playback | `PlaybackBar` at the top; every surface is a projection of `playback.session`. Branches that have not forked yet drop out of the rail, agents on them read *off-screen*, and the fan graph shrinks to whatever exists. `ActivityTicker` groups the whole step by intent, so a burst reads as one row with a count rather than 12 lost rows. |
| 2 Changed vs rematerialized | `StatusBadges` in three places: per-branch in the rail (from `engine.unsyncedCause`), on fan-graph nodes and on the committed path (from the path-derived cause). The composed answer wins where it has one; with nothing swapped the engine's per-branch answer takes over, and a sweep branch reads `RawChurn: changed` without anyone touching it — the divergent pin as a badge. |
| 3 Cache-hit announcement | `CacheSkipBanner` above the graph, keyed to the winner branch. Selecting five variants materializes nothing, and a silent screen after five clicks reads as broken. |
| 4 Pre-flight cost | `CostChip` per selected variant in the rail, on the committed path, and inside `ExportPreview`. The path's cost uses the same cached-and-materialized test `preflightCost` uses, so the numbers next to each other are comparable. Swapping `Features` and the stale raw pin together moves the path from *instant* to *recomputes 5 · ~4m*. |
| 5 N-way comparison | `DifferenceTable` full width, plus the metric matrix in the results pane. `IntegrityWarnings` renders above both. |
| 6 Export / freeze | *export this path* opens `ExportPreview` against a synthetic `__composed` branch built from the path, so the linear document renders the composed slice, not a branch — with what is frozen and what is left behind. Blocked while conflicts exist. |
| 7 Scratch console | `ScratchConsole` scoped to the inspected asset; promoting explains that it would open a new fan point present in this slice and absent from every other variant. |
| 8 Where editing lives | Above. |
| 9 Agent presence | Avatars on branch chips in the rail, an agent list with *what each is touching right now* and an *off-screen* marker for agents working outside the comparison, and author-coloured dots on every committed path entry. |
| 10 `large` fixture | Renders. See below. |

## What breaks at scale

- **`large` renders, with two caps.** Stages longer than 6 collapsed nodes are
  truncated with a *+N more value fans downstream* chip (`show every value fan`
  expands), and the committed-path list keeps every fan point but truncates the
  value-only tail at 14. Without the first cap, the diagnostics stage alone is 41
  nodes. Derivation cost is not the problem — the full model for 5 of 20 branches
  computes in ~20 ms.
- **The fan graph's layout is stages, not a real DAG layout.** Nodes are grouped
  by longest-path depth and edges are implied by a `reads …` line plus one
  connector per stage gap. This is honest for the fixtures, which are near-chains,
  and it would misrepresent a genuinely wide graph — two unrelated sub-DAGs at
  the same depth look like siblings. A real layout is the first thing I would add.
- **Variant chips do not scale past 5**, which is the point, but *fan width* is
  not capped independently. A single asset with 5 distinct definitions across 5
  branches produces a 5-wide fan, and the correlation greying is doing a lot of
  work at that width.
- **The rail shows all 20 branches unsorted.** At 20 it wraps to three rows and is
  already the least legible thing on screen; at 200 it needs search and grouping
  by `sweepGroup`.

## What I would do differently

1. **Sort and group the branch rail** by lineage and `sweepGroup`, with the
   metric that is currently only visible after selection shown on the chip. The
   selection step is where the 1-in-20 decision actually happens, and I gave it
   the least design.
2. **Make the conflict rule part of the object model.** `declaredRequirements`
   works for a demo but it is a lookup table beside the data. The real version is
   a declared input schema on `materialize()`, so the conflict is a type error
   with a source location rather than a sentence I wrote.
3. **Let the fan graph show the *count* of downstream distinct results on the
   fan itself.** Right now you learn that `Features` has 3 definitions from the
   fan and that `TrainTestSplit` has 4 distinct results from the node below it;
   those are the same fact and should be one glyph.
4. **Drop the difference table to a drawer.** It is mandatory and it is the right
   exhaustive fallback, but full-width at the bottom it competes with the results
   pane for the same attention and wins on visual weight while losing on value.
5. **A path history.** Cherry-picking is destructive right now — *pick winner*
   is the only undo. Three swaps deep you cannot remember what you started from.
