import { checkpoints } from '../../engine'
import type { AssetId, BranchId, FlowSession, Transaction } from '../../types'

/**
 * Geometry for the drawn rail.
 *
 * Every position is a pure function of the full session — never of the current
 * selection or playback step — so choosing a stop can change emphasis and
 * visibility but can never move a pixel. Lanes are branches, time flows down,
 * and a row exists per step that carries something worth stopping at:
 * checkpoints (settled transactions), fork points, lane heads, and folded runs
 * of routine work in between.
 */

export const ROW_HEIGHT = 44
export const PAD_TOP = 30
export const PAD_BOTTOM = 30
export const PAD_LEFT = 26
export const LABEL_WIDTH = 228
export const LABEL_GAP = 16

export interface RailStop {
  key: string
  branchId: BranchId
  step: number
  x: number
  y: number
  /** `checkpoint` is a settled state worth returning to; `run` folds routine work. */
  kind: 'checkpoint' | 'run'
  label: string
  /** Who and what, for the tooltip — a bare count is not scent. */
  detail: string
  txCount: number
  failed: boolean
  laneHead: boolean
  liveHead: boolean
}

export interface RailLane {
  branchId: BranchId
  name: string
  color: string
  x: number
  topY: number
  bottomY: number
  /** Step at which this lane exists at all — used to dim not-yet-forked lanes. */
  startStep: number
  fork: { parentX: number; y: number } | null
}

export interface RailLayout {
  lanes: RailLane[]
  stops: RailStop[]
  /** Sorted (step, y) pairs — the playback marker interpolates over these. */
  stepYs: { step: number; y: number }[]
  labelX: number
  width: number
  height: number
  laneGap: number
}

interface StepGroup {
  step: number
  txs: Transaction[]
}

const opAssetIds = (tx: Transaction): AssetId[] =>
  tx.ops.flatMap((op) => ('assetId' in op ? [op.assetId] : []))

const hasFailure = (txs: Transaction[]): boolean =>
  txs.some((tx) => tx.ops.some((op) => op.op === 'materialize' && op.result.state === 'failed'))

const isLandmark = (txs: Transaction[], settled: Set<string>): boolean =>
  txs.some(
    (tx) =>
      settled.has(tx.txId) ||
      tx.ops.some((op) => op.op === 'fork-branch' || op.op === 'rename-asset'),
  )

export function buildRailLayout(session: FlowSession): RailLayout {
  const branches = Object.values(session.branches)
    .filter((branch) => !branch.archived)
    .sort((a, b) => a.forkedAtStep - b.forkedAtStep || a.branchId.localeCompare(b.branchId))

  // Past ~8 forks the lanes compress so the label column stays in view; the
  // stress fixture trades per-lane air for a rail that still fits its card.
  const laneGap = branches.length > 8 ? 12 : 24
  const laneXById = new Map<BranchId, number>()
  branches.forEach((branch, index) => laneXById.set(branch.branchId, PAD_LEFT + index * laneGap))

  const settled = new Set(checkpoints(session).map((tx) => tx.txId))

  const groupsByBranch = new Map<BranchId, StepGroup[]>()
  for (const tx of session.transactions) {
    if (!laneXById.has(tx.branchId)) continue
    const groups = groupsByBranch.get(tx.branchId) ?? []
    const last = groups[groups.length - 1]
    if (last && last.step === tx.step) last.txs.push(tx)
    else groups.push({ step: tx.step, txs: [tx] })
    groupsByBranch.set(tx.branchId, groups)
  }
  for (const groups of groupsByBranch.values()) groups.sort((a, b) => a.step - b.step)

  const agentLabel = (agentId: string): string => session.agents[agentId]?.label ?? agentId
  const assetName = (assetId: AssetId): string =>
    session.assets[assetId]?.at(-1)?.definition.name ?? assetId

  // A fork with no transactions of its own still selected different versions;
  // its head sits where the newest of those versions was authored, so the lane
  // spans the work it actually contains rather than collapsing to the fork point.
  const stubHeadStep = (branch: (typeof branches)[number]): number => {
    const parent = branch.parentBranchId ? session.branches[branch.parentBranchId] : null
    let head = branch.forkedAtStep
    for (const [assetId, versionId] of Object.entries(branch.selection)) {
      if (parent && parent.selection[assetId] === versionId) continue
      const version = session.assets[assetId]?.find((v) => v.versionId === versionId)
      if (version) head = Math.max(head, version.createdAtStep)
    }
    return head
  }

  interface PendingStop {
    branchId: BranchId
    step: number
    kind: 'checkpoint' | 'run'
    label: string
    detail: string
    txCount: number
    failed: boolean
    laneHead: boolean
  }

  const pending: PendingStop[] = []
  for (const branch of branches) {
    const groups = groupsByBranch.get(branch.branchId) ?? []

    if (!groups.length) {
      if (branch.parentBranchId === null) continue
      pending.push({
        branchId: branch.branchId,
        step: stubHeadStep(branch),
        kind: 'checkpoint',
        label: branch.name,
        detail: `forked from ${session.branches[branch.parentBranchId]?.name ?? '?'}`,
        txCount: 0,
        failed: false,
        laneHead: true,
      })
      continue
    }

    let run: StepGroup[] = []
    const flushRun = (): void => {
      if (!run.length) return
      const txs = run.flatMap((group) => group.txs)
      const authors = [...new Set(txs.map((tx) => agentLabel(tx.author)))]
      const assets = [...new Set(txs.flatMap(opAssetIds).map(assetName))]
      pending.push({
        branchId: branch.branchId,
        step: run[run.length - 1].step,
        kind: 'run',
        label: txs.length === 1 ? txs[0].intent : `${txs.length} edits · ${authors.join(', ')}`,
        detail: `${authors.join(', ')} · ${assets.slice(0, 3).join(', ')}`,
        txCount: txs.length,
        failed: hasFailure(txs),
        laneHead: false,
      })
      run = []
    }

    groups.forEach((group, index) => {
      const last = index === groups.length - 1
      if (isLandmark(group.txs, settled) || last) {
        flushRun()
        const primary =
          group.txs.find((tx) => settled.has(tx.txId)) ?? group.txs[group.txs.length - 1]
        const authors = [...new Set(group.txs.map((tx) => agentLabel(tx.author)))]
        pending.push({
          branchId: branch.branchId,
          step: group.step,
          kind: 'checkpoint',
          label: primary.intent,
          detail: authors.join(', '),
          txCount: group.txs.length,
          failed: hasFailure(group.txs),
          laneHead: last,
        })
      } else {
        run.push(group)
      }
    })
  }

  const rowSteps = [...new Set([...pending.map((stop) => stop.step), ...branches.filter((b) => b.parentBranchId !== null).map((b) => b.forkedAtStep)])].sort((a, b) => a - b)
  const yByStep = new Map<number, number>()
  rowSteps.forEach((step, index) => yByStep.set(step, PAD_TOP + index * ROW_HEIGHT))
  const rowY = (step: number): number => yByStep.get(step) ?? PAD_TOP

  const liveStep = pending.reduce((max, stop) => Math.max(max, stop.step), 0)
  const stops: RailStop[] = pending.map((stop) => ({
    ...stop,
    key: `${stop.branchId}@${stop.step}`,
    x: laneXById.get(stop.branchId) ?? PAD_LEFT,
    y: rowY(stop.step),
    liveHead: stop.laneHead && stop.step === liveStep,
  }))

  const lanes: RailLane[] = branches.map((branch) => {
    const x = laneXById.get(branch.branchId) ?? PAD_LEFT
    const own = stops.filter((stop) => stop.branchId === branch.branchId)
    const parentX = branch.parentBranchId ? laneXById.get(branch.parentBranchId) : undefined
    const forkY = branch.parentBranchId !== null ? rowY(branch.forkedAtStep) : null
    const childForkYs = branches
      .filter((child) => child.parentBranchId === branch.branchId)
      .map((child) => rowY(child.forkedAtStep))
    const ownYs = own.map((stop) => stop.y)
    const topY = forkY ?? (ownYs.length ? Math.min(...ownYs) : PAD_TOP)
    const bottomY = Math.max(topY, ...ownYs, ...childForkYs)
    return {
      branchId: branch.branchId,
      name: branch.name,
      color: branch.color,
      x,
      topY,
      bottomY,
      startStep: branch.parentBranchId === null ? 0 : branch.forkedAtStep,
      fork: forkY !== null && parentX !== undefined ? { parentX, y: forkY } : null,
    }
  })

  const laneAreaWidth = PAD_LEFT + branches.length * laneGap
  const maxY = rowSteps.length ? PAD_TOP + (rowSteps.length - 1) * ROW_HEIGHT : PAD_TOP

  return {
    lanes,
    stops,
    stepYs: rowSteps.map((step) => ({ step, y: rowY(step) })),
    labelX: laneAreaWidth + LABEL_GAP,
    width: laneAreaWidth + LABEL_GAP + LABEL_WIDTH,
    height: maxY + PAD_BOTTOM,
    laneGap,
  }
}
