/**
 * Coalescing and ranking for the catch-up tour.
 *
 * The make-or-break mechanic of concept 3. Agents emit 10–100 actions per human
 * prompt, so an enumerated transaction list is unreadable by construction. Three
 * passes turn the log into something with a human-sized number of entries:
 *
 *   1. group by (author, normalized intent) — `Transaction.intent` is the only
 *      grouping key that survives, because "these nine edits were one sweep" is
 *      not recoverable from the mutation ops;
 *   2. fold a failed-only group into the group that repaired it, the way a PR
 *      timeline hides a force-pushed broken commit behind its fix;
 *   3. score each entry structurally — blast radius, metric movement, failure,
 *      integrity, structural rewire — so the reader is told where to look and
 *      *why*, rather than being handed a flat diff.
 */

import {
  divergence,
  downstreamOf,
  integrityWarnings,
  topoOrder,
  versionsOf,
} from '../../engine'
import type {
  AssetId,
  AssetVersion,
  BranchId,
  FlowSession,
  Transaction,
} from '../../types'

export type ReasonCode =
  | 'failure'
  | 'integrity'
  | 'structural'
  | 'metric-moved'
  | 'blast-radius'
  | 'cost'
  | 'routine'

export interface RankReason {
  code: ReasonCode
  label: string
  points: number
}

export interface MetricMove {
  assetId: AssetId
  assetName: string
  metric: string
  before: number
  after: number
}

export interface AssetTouch {
  assetId: AssetId
  name: string
  versions: AssetVersion[]
  failed: number
  downstreamCount: number
}

export interface TourEntry {
  key: string
  author: string
  /** Display intent. Numerals collapse to `…` when several intents fold together. */
  intent: string
  rawIntents: string[]
  transactions: Transaction[]
  branchIds: BranchId[]
  touches: AssetTouch[]
  metricMoves: MetricMove[]
  structuralNotes: string[]
  failedVersions: AssetVersion[]
  /** True when a failed-only group was folded into this one. */
  repairedFailure: boolean
  firstStep: number
  lastStep: number
  /** Position of the shallowest touched asset in the head branch's topo order. */
  depth: number
  fanOut: number
  score: number
  reasons: RankReason[]
  headline: string
  detail: string
}

/**
 * Sweep intents differ only by the number they mention ("configuration 0/1/2"),
 * so the literal string is a poor key at scale. Collapsing numerals is what lets
 * the 150-asset fixture coalesce into a readable number of entries.
 */
export function normalizeIntent(intent: string): string {
  return intent.replace(/\b\d+(\.\d+)?\b/g, '…')
}

function assetIdsOf(tx: Transaction): AssetId[] {
  const ids: AssetId[] = []
  for (const op of tx.ops) {
    if ('assetId' in op) ids.push(op.assetId)
  }
  return ids
}

function versionsProducedBy(tx: Transaction): AssetVersion[] {
  const out: AssetVersion[] = []
  for (const op of tx.ops) {
    if (op.op === 'create-asset' || op.op === 'edit-asset') out.push(op.version)
  }
  return out
}

function structuralNotesOf(tx: Transaction): string[] {
  const notes: string[] = []
  for (const op of tx.ops) {
    if (op.op === 'rename-asset') notes.push(`renamed ${op.from} → ${op.to}`)
    if (op.op === 'delete-asset') notes.push(`dropped ${op.assetId}`)
    if (op.op === 'rewire-asset') {
      notes.push(`rewired ${op.assetId}: ${op.depsBefore.join(', ')} → ${op.depsAfter.join(', ')}`)
    }
    if (op.op === 'fork-branch') notes.push(`forked ${op.name}`)
  }
  return notes
}

interface RawGroup {
  key: string
  author: string
  normalized: string
  rawIntents: Set<string>
  transactions: Transaction[]
}

function coalesceByIntent(transactions: Transaction[]): RawGroup[] {
  const groups = new Map<string, RawGroup>()
  for (const tx of transactions) {
    const normalized = normalizeIntent(tx.intent)
    const key = `${tx.author}::${normalized}`
    let group = groups.get(key)
    if (!group) {
      group = { key, author: tx.author, normalized, rawIntents: new Set(), transactions: [] }
      groups.set(key, group)
    }
    group.rawIntents.add(tx.intent)
    group.transactions.push(tx)
  }
  return [...groups.values()]
}

/**
 * Second coalescing pass: an attempt that only ever produced failed versions is
 * not a separate thing to review — it is the first half of the fix that follows.
 * Fold it into the next group by the same author touching the same asset.
 */
function foldFailedAttempts(groups: RawGroup[]): { groups: RawGroup[]; repaired: Set<string> } {
  const ordered = [...groups].sort(
    (a, b) => Math.min(...a.transactions.map((t) => t.step)) - Math.min(...b.transactions.map((t) => t.step)),
  )
  const repaired = new Set<string>()
  const dropped = new Set<string>()

  for (const [index, group] of ordered.entries()) {
    const produced = group.transactions.flatMap(versionsProducedBy)
    if (!produced.length || produced.some((v) => v.status !== 'failed')) continue

    const failedAssetIds = new Set(produced.map((v) => v.assetId))
    const successor = ordered
      .slice(index + 1)
      .find(
        (candidate) =>
          candidate.author === group.author &&
          candidate.transactions
            .flatMap(versionsProducedBy)
            .some((v) => failedAssetIds.has(v.assetId) && v.status === 'ok'),
      )
    if (!successor) continue

    successor.transactions.push(...group.transactions)
    group.rawIntents.forEach((intent) => successor.rawIntents.add(intent))
    repaired.add(successor.key)
    dropped.add(group.key)
  }

  return { groups: ordered.filter((group) => !dropped.has(group.key)), repaired }
}

function metricMovesFor(
  session: FlowSession,
  produced: AssetVersion[],
): MetricMove[] {
  const moves: MetricMove[] = []
  for (const version of produced) {
    const after = session.materializations[version.versionId]?.metrics
    if (!after) continue
    const history = versionsOf(session, version.assetId)
    const index = history.findIndex((v) => v.versionId === version.versionId)
    const previous = history
      .slice(0, Math.max(0, index))
      .reverse()
      .find((v) => session.materializations[v.versionId]?.metrics)
    const before = previous ? session.materializations[previous.versionId]?.metrics : undefined
    if (!before) continue
    for (const [metric, value] of Object.entries(after)) {
      const baseline = before[metric]
      if (baseline === undefined || baseline === value) continue
      moves.push({
        assetId: version.assetId,
        assetName: version.definition.name,
        metric,
        before: baseline,
        after: value,
      })
    }
  }
  return moves
}

function scoreEntry(entry: TourEntry, session: FlowSession, headBranchId: BranchId): void {
  const reasons: RankReason[] = []

  if (entry.failedVersions.length) {
    const label = entry.repairedFailure
      ? `${entry.failedVersions.length} failed attempt, fixed in the same intent`
      : `${entry.failedVersions.length} materialization failed and was not retried`
    reasons.push({ code: 'failure', label, points: entry.repairedFailure ? 24 : 46 })
  }

  const compareIds = [...new Set([headBranchId, ...entry.branchIds])].filter(
    (id) => session.branches[id],
  )
  if (compareIds.length > 1) {
    for (const warning of integrityWarnings(session, compareIds)) {
      reasons.push({
        code: 'integrity',
        label: `integrity: ${warning.kind.replace('-', ' ')}`,
        points: warning.kind === 'divergent-pin' ? 38 : 16,
      })
    }
  }

  if (entry.structuralNotes.some((note) => !note.startsWith('forked'))) {
    reasons.push({
      code: 'structural',
      label: `graph shape changed — ${entry.structuralNotes.filter((n) => !n.startsWith('forked'))[0]}`,
      points: 28,
    })
  }

  const biggestMove = entry.metricMoves
    .slice()
    .sort((a, b) => Math.abs(b.after - b.before) - Math.abs(a.after - a.before))[0]
  if (biggestMove) {
    const delta = biggestMove.after - biggestMove.before
    reasons.push({
      code: 'metric-moved',
      label: `${biggestMove.metric} ${biggestMove.before.toFixed(3)} → ${biggestMove.after.toFixed(3)} (${delta >= 0 ? '+' : ''}${delta.toFixed(3)})`,
      points: 18 + Math.min(20, Math.abs(delta) * 400),
    })
  }

  if (entry.fanOut > 0) {
    reasons.push({
      code: 'blast-radius',
      label: `${entry.fanOut} asset${entry.fanOut === 1 ? '' : 's'} downstream`,
      points: Math.min(24, entry.fanOut * 2.5),
    })
  }

  // Entry-scoped, not slice-scoped: what *this* work would cost to reproduce.
  const cost = entry.touches
    .flatMap((touch) => touch.versions)
    .reduce((sum, version) => sum + (session.materializations[version.versionId]?.costSeconds ?? 0), 0)
  if (cost > 300) {
    reasons.push({
      code: 'cost',
      label: `~${Math.round(cost / 60)}m of compute spent here`,
      points: 8,
    })
  }

  if (!reasons.length) {
    reasons.push({ code: 'routine', label: 'no downstream effect, no metric moved', points: 0 })
  }

  entry.reasons = reasons.sort((a, b) => b.points - a.points)
  entry.score = reasons.reduce((sum, reason) => sum + reason.points, 0)
}

export function buildTour(
  session: FlowSession,
  transactions: Transaction[],
  headBranchId: BranchId,
): TourEntry[] {
  if (!transactions.length) return []

  const order = topoOrder(session, headBranchId)
  const depthOf = new Map(order.map((assetId, index) => [assetId, index]))

  const downstreamCache = new Map<string, number>()
  const downstreamCount = (branchId: BranchId, assetId: AssetId): number => {
    const cacheKey = `${branchId}::${assetId}`
    const hit = downstreamCache.get(cacheKey)
    if (hit !== undefined) return hit
    const value = session.branches[branchId] ? downstreamOf(session, branchId, assetId).length : 0
    downstreamCache.set(cacheKey, value)
    return value
  }

  const { groups, repaired } = foldFailedAttempts(coalesceByIntent(transactions))

  const entries = groups.map((group) => {
    // Folding failed attempts appends out of order; sort before deriving anything
    // so version runs read v0→v1 rather than v1→v0.
    const txs = group.transactions.slice().sort((a, b) => a.step - b.step)
    const produced = txs.flatMap(versionsProducedBy)
    const branchIds = [...new Set(txs.map((tx) => tx.branchId))]
    const steps = txs.map((tx) => tx.step)

    const byAsset = new Map<AssetId, AssetVersion[]>()
    for (const assetId of txs.flatMap(assetIdsOf)) {
      if (!byAsset.has(assetId)) byAsset.set(assetId, [])
    }
    const seenVersionIds = new Set<string>()
    for (const version of produced) {
      if (seenVersionIds.has(version.versionId)) continue
      seenVersionIds.add(version.versionId)
      byAsset.get(version.assetId)?.push(version)
    }

    const probeBranch = branchIds.find((id) => session.branches[id]) ?? headBranchId
    const touches: AssetTouch[] = [...byAsset.entries()].map(([assetId, versions]) => ({
      assetId,
      name: versions[versions.length - 1]?.definition.name ?? versionsOf(session, assetId)[0]?.definition.name ?? assetId,
      versions,
      failed: versions.filter((v) => v.status === 'failed').length,
      downstreamCount: downstreamCount(probeBranch, assetId),
    }))

    const entry: TourEntry = {
      key: group.key,
      author: group.author,
      intent: group.rawIntents.size > 1 ? group.normalized : [...group.rawIntents][0],
      rawIntents: [...group.rawIntents],
      transactions: txs,
      branchIds,
      touches: touches.sort((a, b) => (depthOf.get(a.assetId) ?? 999) - (depthOf.get(b.assetId) ?? 999)),
      metricMoves: metricMovesFor(session, produced),
      structuralNotes: [...new Set(txs.flatMap(structuralNotesOf))],
      failedVersions: produced.filter((v) => v.status === 'failed'),
      repairedFailure: repaired.has(group.key),
      firstStep: Math.min(...steps),
      lastStep: Math.max(...steps),
      depth: Math.min(...touches.map((t) => depthOf.get(t.assetId) ?? 999), 999),
      fanOut: Math.max(0, ...touches.map((t) => t.downstreamCount)),
      score: 0,
      reasons: [],
      headline: '',
      detail: '',
    }

    entry.headline = `${session.agents[entry.author]?.label ?? entry.author} — ${entry.intent}`
    entry.detail = describe(entry, session)
    scoreEntry(entry, session, headBranchId)
    return entry
  })

  return entries
}

/** The one-line coalesced summary: what the PR-timeline collapse actually says. */
function describe(entry: TourEntry, session: FlowSession): string {
  const parts: string[] = []
  const txCount = entry.transactions.length
  parts.push(`${txCount} transaction${txCount === 1 ? '' : 's'}`)
  if (entry.branchIds.length > 1) parts.push(`${entry.branchIds.length} branches`)
  else parts.push(session.branches[entry.branchIds[0]]?.name ?? entry.branchIds[0])

  for (const touch of entry.touches.slice(0, 2)) {
    const tags = [...new Set(touch.versions.map((v) => v.versionId.split('@')[1] ?? v.versionId))]
    if (tags.length > 2) parts.push(`${touch.name} ${tags[0]}…${tags[tags.length - 1]}`)
    else if (tags.length) parts.push(`${touch.name} ${tags.join('→')}`)
    else parts.push(touch.name)
  }
  if (entry.touches.length > 2) parts.push(`+${entry.touches.length - 2} more assets`)
  if (entry.failedVersions.length) {
    parts.push(`${entry.failedVersions.length} failed attempt${entry.failedVersions.length === 1 ? '' : 's'}`)
  }
  return parts.join(' · ')
}

export type ReadingOrder = 'recommended' | 'risk' | 'time'

export interface OrderedTour {
  /** Entries the reader should not skim past, whatever the dependency order says. */
  readFirst: TourEntry[]
  rest: TourEntry[]
  explanation: string
}

const READ_FIRST_CODES = new Set<ReasonCode>(['failure', 'integrity', 'structural'])
const READ_FIRST_SCORE = 50

/** Attention allocation: which regions deserve scrutiny, which are routine. */
function isReadFirst(entry: TourEntry): boolean {
  return (
    entry.score >= READ_FIRST_SCORE ||
    entry.reasons.some((reason) => READ_FIRST_CODES.has(reason.code))
  )
}

export function orderTour(entries: TourEntry[], mode: ReadingOrder): OrderedTour {
  if (mode === 'time') {
    return {
      readFirst: [],
      rest: [...entries].sort((a, b) => a.firstStep - b.firstStep),
      explanation:
        'Chronological — what actually happened, in the order it landed. Use this to audit, not to catch up: it interleaves five agents.',
    }
  }

  if (mode === 'risk') {
    return {
      readFirst: [],
      rest: [...entries].sort((a, b) => b.score - a.score),
      explanation:
        'Review-worthiness only — failures, integrity warnings, structural rewires, metric movement, then fan-out. Highest first.',
    }
  }

  const readFirst = entries.filter(isReadFirst).sort((a, b) => b.score - a.score)
  const readFirstKeys = new Set(readFirst.map((entry) => entry.key))
  const rest = entries
    .filter((entry) => !readFirstKeys.has(entry.key))
    .sort((a, b) => (a.depth === b.depth ? b.score - a.score : a.depth - b.depth))

  return {
    readFirst,
    rest,
    explanation:
      'Failures, integrity warnings and structural rewires float to the top; everything else is in dependency order, upstream first, so a change reads before the changes it caused. Ties break on fan-out.',
  }
}

/** Assets the reader lands on when they dive in: what changed, plus what it moved. */
export function destinationAssets(
  session: FlowSession,
  entry: TourEntry,
  branchId: BranchId,
): { assetId: AssetId; direct: boolean }[] {
  if (!session.branches[branchId]) return []
  const direct = new Set(entry.touches.map((touch) => touch.assetId))
  const affected = new Set<AssetId>(direct)
  for (const assetId of direct) {
    downstreamOf(session, branchId, assetId).forEach((id) => affected.add(id))
  }
  return topoOrder(session, branchId)
    .filter((assetId) => affected.has(assetId))
    .map((assetId) => ({ assetId, direct: direct.has(assetId) }))
}

/** Branches an entry makes worth comparing: the ones it touched, plus the trunk. */
export function comparisonBranches(session: FlowSession, entry: TourEntry): BranchId[] {
  return [...new Set([session.headBranchId, ...entry.branchIds])].filter(
    (id) => session.branches[id],
  )
}

export function divergentAssetCount(session: FlowSession, branchIds: BranchId[]): number {
  if (branchIds.length < 2) return 0
  return divergence(session, branchIds).filter((entry) => entry.kind !== 'none').length
}
