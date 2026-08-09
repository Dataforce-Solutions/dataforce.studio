import { resolveSlice } from '../../engine'
import type { AssetId, BranchId, FlowSession } from '../../types'

/**
 * Vertical flow layout.
 *
 * The primary axis is *down*, like a notebook: dependency depth becomes a row,
 * and assets only spread sideways when they genuinely sit at the same depth.
 * A left-to-right pipeline layout reads as infrastructure; a document that
 * flows downward reads as work.
 *
 * Positions come from the union of every version in the session rather than
 * from the selected branch, so switching branches or seeking through the log
 * never moves a card that both states share.
 */

export const CARD_WIDTH = 440
export const CARD_HEIGHT = 460
export const COLUMN_GAP = 48
export const ROW_GAP = 88
export const MAX_PER_LINE = 3

export interface FlowNode {
  assetId: AssetId
  x: number
  y: number
  depth: number
}

export interface FlowLayout {
  nodes: Record<AssetId, FlowNode>
  order: AssetId[]
  width: number
  height: number
}

function unionDeps(session: FlowSession): Record<AssetId, AssetId[]> {
  const deps: Record<AssetId, Set<AssetId>> = {}
  for (const [assetId, versions] of Object.entries(session.assets)) {
    deps[assetId] = deps[assetId] ?? new Set()
    for (const version of versions) {
      for (const dep of version.definition.deps) deps[assetId].add(dep)
    }
  }
  return Object.fromEntries(Object.entries(deps).map(([id, set]) => [id, [...set]]))
}

/** Longest path from a root, so a card always sits below everything it reads. */
function depths(session: FlowSession, deps: Record<AssetId, AssetId[]>): Record<AssetId, number> {
  const depth: Record<AssetId, number> = {}
  const visiting = new Set<AssetId>()

  const resolve = (assetId: AssetId): number => {
    if (depth[assetId] !== undefined) return depth[assetId]
    if (visiting.has(assetId)) return 0
    visiting.add(assetId)
    const parents = (deps[assetId] ?? []).filter((id) => session.assets[id])
    depth[assetId] = parents.length ? Math.max(...parents.map(resolve)) + 1 : 0
    visiting.delete(assetId)
    return depth[assetId]
  }

  Object.keys(session.assets).forEach(resolve)
  return depth
}

export function buildFlowLayout(session: FlowSession): FlowLayout {
  const deps = unionDeps(session)
  const depth = depths(session, deps)

  const byDepth = new Map<number, AssetId[]>()
  for (const assetId of Object.keys(session.assets)) {
    const level = depth[assetId] ?? 0
    const bucket = byDepth.get(level) ?? []
    bucket.push(assetId)
    byDepth.set(level, bucket)
  }
  for (const bucket of byDepth.values()) bucket.sort()

  const levels = [...byDepth.keys()].sort((a, b) => a - b)
  const widest = Math.max(
    1,
    ...levels.map((level) => Math.min(MAX_PER_LINE, byDepth.get(level)?.length ?? 1)),
  )
  const width = widest * CARD_WIDTH + (widest - 1) * COLUMN_GAP

  const nodes: Record<AssetId, FlowNode> = {}
  const order: AssetId[] = []
  let y = 0

  for (const level of levels) {
    const bucket = byDepth.get(level) ?? []
    // A depth with more assets than fit on one line wraps within its own band
    // rather than widening the whole canvas — the EDA fringe is 18 plots deep.
    for (let start = 0; start < bucket.length; start += MAX_PER_LINE) {
      const line = bucket.slice(start, start + MAX_PER_LINE)
      const lineWidth = line.length * CARD_WIDTH + (line.length - 1) * COLUMN_GAP
      const offset = (width - lineWidth) / 2
      line.forEach((assetId, index) => {
        nodes[assetId] = {
          assetId,
          x: offset + index * (CARD_WIDTH + COLUMN_GAP),
          y,
          depth: level,
        }
        order.push(assetId)
      })
      y += CARD_HEIGHT + ROW_GAP
    }
  }

  return { nodes, order, width, height: Math.max(0, y - ROW_GAP) }
}

/** Assets present in this branch, in reading order — used by the notebook view. */
export function readingOrder(
  session: FlowSession,
  branchId: BranchId,
  layout: FlowLayout,
): AssetId[] {
  const slice = resolveSlice(session, branchId)
  return layout.order.filter((assetId) => slice[assetId])
}
