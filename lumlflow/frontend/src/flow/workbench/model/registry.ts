import type { AssetKind, CellOutput, FlowCell } from './types'

/**
 * Which output opens first matters more than it looks: a training cell that
 * returns {model, run, checkpoint, curves} must open on the experiment, not on
 * whichever key came first (ui-draft.md §4).
 */
const PRIMARY_RANKING: AssetKind[] = [
  'experiment',
  'eval',
  'plot',
  'frame',
  'dataset',
  'note',
  'metric',
  'model',
  'image',
  'html',
  'text',
  'checkpoint',
  'unknown',
]

export function rankOf(kind: AssetKind): number {
  const index = PRIMARY_RANKING.indexOf(kind)
  return index === -1 ? PRIMARY_RANKING.length : index
}

export function primaryOutput(cell: FlowCell): CellOutput | null {
  if (cell.outputs.length === 0) return null
  if (cell.primaryOutput) {
    const declared = cell.outputs.find((output) => output.name === cell.primaryOutput)
    if (declared) return declared
  }
  return [...cell.outputs].sort((a, b) => rankOf(a.kind) - rankOf(b.kind))[0]
}

export const KIND_LABELS: Record<AssetKind, string> = {
  frame: 'frame',
  plot: 'plot',
  metric: 'metric',
  note: 'note',
  eval: 'eval',
  model: 'model',
  dataset: 'dataset',
  experiment: 'experiment',
  checkpoint: 'checkpoint',
  image: 'image',
  text: 'text',
  html: 'html',
  unknown: 'asset',
}

/** Producer slug of a reference string: 'features.train_split' → 'features'. */
export function producerOf(reference: string): string {
  const dot = reference.indexOf('.')
  return dot === -1 ? reference : reference.slice(0, dot)
}

/** Edges of a branch slice, derived from declared wiring. */
export function sliceEdges(cells: FlowCell[]): { from: string; to: string }[] {
  const slugs = new Set(cells.map((cell) => cell.slug))
  const edges: { from: string; to: string }[] = []
  for (const cell of cells) {
    for (const reference of cell.consumes) {
      const from = producerOf(reference)
      if (slugs.has(from) && from !== cell.slug) edges.push({ from, to: cell.slug })
    }
  }
  return edges
}

/**
 * Stable topological order for the notebook view: dependencies first, ties
 * broken on authoring step so cards never reorder when an unrelated cell lands.
 */
export function topologicalOrder(cells: FlowCell[]): FlowCell[] {
  const bySlug = new Map(cells.map((cell) => [cell.slug, cell]))
  const edges = sliceEdges(cells)
  const incoming = new Map<string, Set<string>>()
  for (const cell of cells) incoming.set(cell.slug, new Set())
  for (const edge of edges) incoming.get(edge.to)?.add(edge.from)

  const ready = (): FlowCell[] =>
    [...incoming.entries()]
      .filter(([, deps]) => deps.size === 0)
      .map(([slug]) => bySlug.get(slug) as FlowCell)
      .sort((a, b) => a.provenance.step - b.provenance.step)

  const ordered: FlowCell[] = []
  while (incoming.size > 0) {
    const batch = ready()
    if (batch.length === 0) {
      // Cycle or dangling reference: append the rest in authoring order.
      ordered.push(
        ...[...incoming.keys()]
          .map((slug) => bySlug.get(slug) as FlowCell)
          .sort((a, b) => a.provenance.step - b.provenance.step),
      )
      break
    }
    for (const cell of batch) {
      ordered.push(cell)
      incoming.delete(cell.slug)
      for (const deps of incoming.values()) deps.delete(cell.slug)
    }
  }
  return ordered
}
