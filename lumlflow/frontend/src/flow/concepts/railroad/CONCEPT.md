# Concept 1 — Canvas + focused railroad

Route: `/flow/railroad`

## The mental model

Two surfaces, joined by brushing, never merged into one drawing.

**Left: the canvas.** One variant at a time, laid out once and never again. Positions come
from the *union* of every version of every asset in the session (`layout.ts`), not from the
selected branch and not from the current playback step. Switch branches, seek to step 8, filter
to a family — every node keeps its pixel. The consequence is that motion on the canvas carries
exactly one meaning: *something happened here*. It is never the layout re-solving.

**Right: the railroad.** History as a *scoped query* over the event log, not a second topology.
It covers the selected branch's lineage plus the forks cut off it, always in step order, and
collapses under a switchable lens: `this asset` / `by author` / `by outcome` / `everything`.

**Between them: brushing.** Click a node → the railroad re-scopes to that asset's history.
Click a checkpoint → the canvas seeks there and marks what that transaction touched. Both
directions change *visibility only*. Nothing moves.

## What the concept bets on

1. **Structure × time is navigable if history is scoped, not drawn.** Every attempt to render
   the full asset-version lattice ends in a hairball. Here the second dimension is a filtered
   list beside a stable picture, and selection is what scopes it.
2. **Layout stability is worth a lot of whitespace.** Nodes are placed by longest-path layer over
   the union graph, so a branch that deletes `TrainGBM` leaves a hole where `TrainGBM` was, and
   an asset that does not exist yet at this step simply is not drawn. Holes are information.
3. **Motion is an attention channel with a budget.** Spent only on reactlog's phases:
   `invalidating` (edges visibly tear apart, node desaturates) is a distinct phase from
   `materializing` (edge redraws). `usePulses.ts` synthesises this sequence on each step,
   because a settled fixture only stores resting states. Seek to step 22 (the `RawChurn` data
   fix) to watch the whole graph below it tear down and rebuild.
4. **A lens that can hide "where am I" is a trap.** The current checkpoint, every branch head,
   the live head and every fork point stay visible in all four lenses (jj's `@`). Collapsed runs
   carry authors, assets touched and a metric delta — never a bare count.

## Where editing lives

**A side panel, on the right. Nodes never expand.** Stated in the UI (bottom bar and the empty
inspector), and load-bearing rather than cosmetic: an inline editor is a node that changes size,
and a node that changes size moves its neighbours, which is precisely what the stable canvas
exists to prevent. The panel shows the agent-authored definition read-only by default; **take
over** makes it editable and prices the edit before you commit it — a definition change
recomputes this asset and everything below it, everything else stays cached.

## What is real vs. what is faked

Everything numeric comes from `engine.ts`: `preflightCost`, `upstreamUpdates` (with early
cutoff), `divergence`, `integrityWarnings`, `cacheSkipSet`, `checkpoints`. Faked: taking over an
edit does not produce a version, `accept` on an upstream update is inert, `promote to asset`
renders the proposal and its cost instead of mutating the graph.

Staleness comes straight from `engine.unsyncedCause`, which now derives it per (branch, asset)
against the branch's own baseline. The canvas renders the three causes distinctly via the shared
`StatusBadges`, and the fixture makes the case for keeping them apart on its own: `main` reads
clean; `feat/tenure-buckets` shows `Features` as **changed** with `TrainTestSplit` below it as
merely **rematerialized**; `model/logreg` shows `HoldoutEval` as **rewired**; the sweep branches
show the divergent `RawChurn` pin as **changed** with five downstream assets as
**rematerialized**. One edited asset, everything under it downstream noise — collapse the two
labels and every one of those branches reads as six equally alarming problems.

## What breaks at scale

Tried on the `large` fixture (94 assets, 20 branches). It renders and stays usable, but:

- **The canvas becomes a scroll surface, not an overview.** ~13 columns wide; wide layers wrap
  into sub-columns of 11 so the 40 diagnostics do not produce a 2,500px column. You navigate by
  hover-highlight and double-click-to-family, not by looking. There is no minimap and no zoom
  control — with more time, both, plus semantic zoom that collapses a wrapped sub-column into one
  "18 EDA plots" node until you enter it.
- **The fan-out from `Split` to twenty models is a hairball.** Twenty near-parallel bezier curves
  from one port. Bundled edges, or a port-per-consumer, would fix it; neither is done.
- **`everything` lens on 96 events is a 5,000px scroll.** This is the honest answer, not a
  regression: the other three lenses are the response, and `by outcome` cuts it to the handful of
  events where AUC moved. But the default lens on a large session should probably not be
  `everything`.
- **`resolveSlice` is O(assets) and several derived views call it.** `unsyncedCause` resolves two
  slices per asset and `upstreamUpdates` runs per branch chip on every render — on the large
  fixture that is roughly 20 × O(assets) and 94 × 2 × O(assets) per frame. Fine at this size,
  not fine at ten times it; the engine would want a memoised slice cache keyed by (branch, step).

## What I would do differently with more time

- **Semantic zoom on the canvas**, so the stable layout survives past ~100 nodes. This is the
  single biggest gap, and the concept's bet does not really pay off until it exists.
- **A real fork affordance.** You can select and compare variants but not cut one from a
  checkpoint — the gesture the whole model is built around is missing from the prototype.
- **Diff the definition in the inspector**, not just show the current source. "What did the agent
  actually change" currently requires reading two versions side by side, which you cannot do.
- **Make the railroad's collapsed-run expansion animate.** It changes in place as promised, but
  instantly, so the "expand where it sits" property is asserted rather than felt.
- **Rethink `by outcome` when there is no target metric.** It currently means "any transaction
  that carried metrics", which on the large fixture is most experiment transactions. A chosen
  target metric plus a magnitude threshold would make it a genuine lens rather than a filter.
