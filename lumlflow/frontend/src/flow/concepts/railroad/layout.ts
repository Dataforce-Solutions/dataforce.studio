/**
 * Spatially stable canvas layout.
 *
 * Positions are computed once from the *union* of every version of every asset
 * in the session — not from the selected branch, not from the current playback
 * step. That is the whole bet of this concept: a node keeps its pixel for the
 * entire session, so motion on the canvas only ever means "something happened
 * here", never "the layout re-solved". The cost is that a branch which deletes
 * an asset leaves a hole, and the hole is the point.
 */

import type { AssetId, FlowSession } from '../../types'

export const NODE_WIDTH = 154
export const NODE_HEIGHT = 48
export const COLUMN_GAP = 200
export const ROW_GAP = 64
export const MAX_ROWS_PER_COLUMN = 11
const MARGIN = 24

export interface LayoutNode {
  assetId: AssetId
  x: number
  y: number
  layer: number
}

export interface CanvasLayout {
  nodes: Record<AssetId, LayoutNode>
  order: AssetId[]
  width: number
  height: number
}

/** Union of the deps declared by any version of each asset. */
function unionGraph(session: FlowSession): Record<AssetId, AssetId[]> {
  const graph: Record<AssetId, AssetId[]> = {}
  for (const [assetId, versions] of Object.entries(session.assets)) {
    const deps = new Set<AssetId>()
    for (const version of versions) {
      for (const dep of version.definition.deps) {
        if (session.assets[dep]) deps.add(dep)
      }
    }
    graph[assetId] = [...deps]
  }
  return graph
}

/** Longest path from a root, so an asset always sits right of everything it reads. */
function layerOf(graph: Record<AssetId, AssetId[]>): Record<AssetId, number> {
  const depth: Record<AssetId, number> = {}
  const inProgress = new Set<AssetId>()

  const visit = (assetId: AssetId): number => {
    if (depth[assetId] !== undefined) return depth[assetId]
    if (inProgress.has(assetId)) return 0 // defensive: fixtures are acyclic
    inProgress.add(assetId)
    const deps = graph[assetId] ?? []
    const value = deps.length ? Math.max(...deps.map(visit)) + 1 : 0
    inProgress.delete(assetId)
    depth[assetId] = value
    return value
  }

  Object.keys(graph).forEach(visit)
  return depth
}

export function buildLayout(session: FlowSession): CanvasLayout {
  const graph = unionGraph(session)
  const depth = layerOf(graph)

  const firstStep: Record<AssetId, number> = {}
  for (const [assetId, versions] of Object.entries(session.assets)) {
    firstStep[assetId] = versions[0]?.createdAtStep ?? 0
  }

  const byLayer = new Map<number, AssetId[]>()
  for (const assetId of Object.keys(graph)) {
    const layer = depth[assetId] ?? 0
    const bucket = byLayer.get(layer) ?? []
    bucket.push(assetId)
    byLayer.set(layer, bucket)
  }

  const nodes: Record<AssetId, LayoutNode> = {}
  const order: AssetId[] = []
  let column = 0
  let maxRows = 0

  for (const layer of [...byLayer.keys()].sort((a, b) => a - b)) {
    const bucket = (byLayer.get(layer) as AssetId[]).sort((a, b) =>
      firstStep[a] === firstStep[b] ? a.localeCompare(b) : firstStep[a] - firstStep[b],
    )
    // Wide layers (40 diagnostics off one leaderboard) wrap into sub-columns
    // rather than producing a 2500px column nobody can scan.
    const columnCount = Math.max(1, Math.ceil(bucket.length / MAX_ROWS_PER_COLUMN))
    const perColumn = Math.ceil(bucket.length / columnCount)

    bucket.forEach((assetId, index) => {
      const subColumn = Math.floor(index / perColumn)
      const row = index % perColumn
      nodes[assetId] = {
        assetId,
        layer,
        x: MARGIN + (column + subColumn) * COLUMN_GAP,
        y: MARGIN + row * ROW_GAP,
      }
      order.push(assetId)
      maxRows = Math.max(maxRows, row + 1)
    })
    column += columnCount
  }

  return {
    nodes,
    order,
    width: MARGIN * 2 + Math.max(1, column) * COLUMN_GAP,
    height: MARGIN * 2 + Math.max(1, maxRows) * ROW_GAP,
  }
}

/** Ancestors ∪ descendants ∪ self, over the union graph — the reactlog family tree. */
export function familyOf(
  session: FlowSession,
  assetId: AssetId,
): { ancestors: Set<AssetId>; descendants: Set<AssetId>; all: Set<AssetId> } {
  const graph = unionGraph(session)
  const children: Record<AssetId, AssetId[]> = {}
  for (const [id, deps] of Object.entries(graph)) {
    for (const dep of deps) {
      children[dep] = children[dep] ?? []
      children[dep].push(id)
    }
  }

  const walk = (start: AssetId, edges: Record<AssetId, AssetId[]>): Set<AssetId> => {
    const seen = new Set<AssetId>()
    const queue = [...(edges[start] ?? [])]
    while (queue.length) {
      const current = queue.shift() as AssetId
      if (seen.has(current)) continue
      seen.add(current)
      queue.push(...(edges[current] ?? []))
    }
    return seen
  }

  const ancestors = walk(assetId, graph)
  const descendants = walk(assetId, children)
  return {
    ancestors,
    descendants,
    all: new Set<AssetId>([assetId, ...ancestors, ...descendants]),
  }
}
