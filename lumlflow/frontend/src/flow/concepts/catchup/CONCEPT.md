# Concept 3 — Catch-up first

Route: `/flow/catchup`. Files: `CatchupConcept.vue`, `catchup/tour.ts`, `catchup/staleness.ts`,
`catchup/TourEntryCard.vue`, `catchup/DestinationPane.vue`.

## Mental model

**The workspace is an inbox, not a filesystem.** You return to the session and the first
thing on screen is not the graph — it is an ordered, explained account of what five agents
did to eleven assets across seven branches while you were gone. The graph is a place you
go, one entry at a time, not a thing you sit in front of.

Three surfaces, in order of importance:

1. **Return summary.** "20 changes since you looked away", the agent/branch breakdown, and
   the top three items by review-worthiness. The count is a *door* — clicking it opens the
   catch-up diff. A count that only counts is the thing this concept exists to replace.
2. **The tour.** Coalesced entries, ranked, with the ranking reason printed on every card,
   under a reading order that says what it is ordered by.
3. **The destination.** Deliberately thin — see below.

## What it bets on

**Bet 1: `Transaction.intent` is the only viable grouping key.** Everything else in the log
is a mutation op; "these ten transactions were one sweep" is not recoverable from ops. The
tour groups on `(author, normalizeIntent(intent))`, where `normalizeIntent` collapses
numerals — "Sweep GBM configuration 0/1/2" folds into one family. On the churn fixture the
twelve-transaction burst collapses to a single card:

> **codex-1 — Sweep n_estimators and learning_rate**
> 10 transactions · 3 branches · TrainGBM v2…v4 · HoldoutEval v1 · +1 more assets
> `integrity: divergent pin` `auc 0.842 → 0.851 (+0.009)` `~21m of compute spent here`

**Bet 2: a failed attempt is not a separate thing to review.** A second coalescing pass
folds a group that produced only `status: 'failed'` versions into the next group by the
same author that repaired the same asset — the way a PR timeline hides a broken commit
behind its fix. Steps 8 and 9 of the churn log become one card reading
`TrainGBM v0→v1 · 1 failed attempt`, scored *down* rather than up because it was fixed.
An unrepaired failure scores 46; a repaired one scores 24.

**Bet 3: ranking must be structural and auditable.** `score` is a sum of named reasons, and
the top three are always printed on the card. Contributions: unrepaired failure (46),
repaired failure (24), divergent-pin integrity warning (38), structural rewire/rename/delete
(28), metric movement (18 + magnitude, capped), blast radius (2.5 × `downstreamOf`, capped
at 24), compute spent (8). An entry with none of these gets an explicit
`no downstream effect, no metric moved` chip — the routine label is as load-bearing as the
alarming one, because that is what lets the reader skip with justification instead of
skimming.

**Bet 4: reading order in a DAG is better-defined than in a flat diff.** Recommended order
is two-tier: entries carrying a failure, an integrity warning, or a structural rewire float
into a **Read first** section sorted by score; everything else follows in **dependency
order, upstream first**, ties broken by fan-out. The rationale is printed under the
selector. On churn this puts the human's `RawChurn` dedupe fix (9 assets downstream, depth
0) ahead of the two feature experiments it invalidates — which is the correct causal
reading order and is not what either "newest first" or "biggest diff first" would produce.
Two alternate orders are one click away: pure review-worthiness, and chronological
(labelled as an audit view, since it interleaves five agents).

## Post-hoc, not pre-hoc — and visibly so

This concept is review-shaped, which is dangerous in a product that deliberately rejected
approval gating. Three things in the UI make the difference visible:

- The live presence strip pulses while the tour is open and says outright: *agents are not
  blocked by this review — work lands, then you read it.*
- The tour is computed from a **frozen ceiling** taken when you opened it. Transactions
  that land while you read do **not** reflow the list under you; they queue behind a pill
  ("3 more landed while you were reading — the list did not reflow under you. Fold them
  in →"). Playback keeps running behind the reader; press play mid-review to see it.
- `mark reviewed` is per-entry and purely a reading aid — nothing is accepted, rejected, or
  merged by it. `mark all caught up` calls `markSeen()` and returns you to the summary.

Nothing here can block an agent, and no control in the tour writes to the graph. The only
mutating gestures are *take over this asset* (forks) and *promote to asset* (adds), both of
which show a pre-flight `CostChip` first.

## The destination is intentionally thin

Concept 1 owns the rich canvas; competing with it would waste the bake-off. Diving into an
entry opens a plain topo-ordered list of the assets it touched **plus everything downstream
of them**, each with `StatusBadges`, kind, version tag, docstring, `ArtifactView`, and
collapsed source. Direct touches get a solid border, downstream fallout a dashed one. That
is the whole destination. The budget went into the tour.

## Where editing lives

**In the destination, on the asset, as an explicit takeover of the agent's definition.**
Expanding `source` on any asset offers *take over this asset*, which turns the source into
an editable buffer and shows, before any keystroke commits: the pre-flight cost of
rematerializing just that asset, and the sentence *"writes `Features@next` on a fork of
`main` — claude-1 keeps working on the original."* Editing therefore never contends with a
running agent; it forks. Throwaway exploration does not go here at all — it goes to
`ScratchConsole`, which runs against the cached materialization and only enters the graph
via *promote to asset*. It is shown non-functionally (the textarea is read-only).

## Unsynced badges — a finding about the substrate

`unsyncedCause` from `engine.ts` returns `null` on every asset in every fixture, because it
only fires when a `Materialization.state === 'unsynced'` and no fixture ever emits that
state. `catchup/staleness.ts` consults it first and then falls back to `upstreamUpdates`,
which detects the churn fixture's *real* staleness — the sweep branches forked before the
`RawChurn` dedupe and never took it — with early cutoff already applied. That maps onto the
same taxonomy the badge renders: the pinned asset itself is `definition-changed`; the ten
assets below it are `parent-rematerialized`. The distinction is exactly the point — one
asset was edited, ten merely read different bytes — and it lights up only on the three
sweep branches, which is correct. On `main` and the feature branches the badge is silent.

## What breaks at scale

Run the `large` fixture (~150 assets, 20 branches) and the honest results are:

- **It renders and stays responsive.** 76 unseen transactions coalesce to 32 entries in
  ~10 ms; `downstreamOf` is memoized per `(branch, asset)`. The tour list caps at 20 with
  *show more*; the destination list caps at 25.
- **But the ranking goes flat.** Nearly every entry scores 0 with a `routine` chip, because
  that fixture's log is 150 `create-asset` transactions on `main` with no failures, no
  structural ops, and no prior version to compare metrics against. **Read first** is empty.
  This is partly the fixture, but it exposes a real weakness: on a workload of many small
  independent additions, structural review-worthiness has nothing to grip and the tour
  degenerates into a long dependency-ordered list. Coalescing still helps (150 → 32), and
  the numeral-collapsing is what does most of that work.
- **32 entries is already past comfortable.** At 10–100 actions per prompt and several
  prompts per session, entry count is the scaling variable that will fail first — not
  transaction count, which coalescing handles fine.
- The **compare** tab renders all 20 branches in `DifferenceTable`; it scrolls horizontally
  and is usable but not pleasant beyond ~6 columns.

## What I would do differently

1. **Coalesce a second level: by asset, not only by intent.** At 150 assets the right unit
   is "everything that happened to `Features` while you were away", not "everything one
   agent did under one intent". Two agents editing the same asset under different intents
   is the case most likely to need a human, and the current grouping splits it apart.
2. **Make `intent` hierarchical.** A prompt produces one root intent and 10–100 leaf
   actions; if agents emitted `intent` as a path (`sweep/gbm/lr-0.05`) rather than a
   sentence, coalescing would be exact instead of a string heuristic, and the "fold in
   pending" pill could nest new work under an entry you already opened.
3. **Score novelty, not just structure.** "Nothing moved" and "we have seen this shape of
   change forty times today" are different kinds of routine, and only the second should be
   collapsible by default.
4. **Cut the chronological order.** It was cheap and it demos badly — it is the exact
   unreadable interleaving the concept is arguing against, and having it one click away
   invites people to use it.
5. **Cut the per-entry `reviewed` checkbox in favour of read-position tracking.** Nobody
   ticks boxes; the honest signal is which entries you actually opened.
