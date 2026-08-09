/**
 * The railroad's collapse heuristic, switchable rather than fixed.
 *
 * No single grouping survives every question: "what did agent-2 touch" and
 * "where did AUC move" want different timelines over the same events. Shipping
 * four lenses and letting selection drive the scope is the concept's answer —
 * the lens changes visibility only, never order.
 */
export type RailroadLens = 'asset' | 'author' | 'outcome' | 'all'

export const lensOptions: { id: RailroadLens; label: string; hint: string }[] = [
  { id: 'asset', label: 'this asset', hint: 'Only events that touched the selected asset.' },
  { id: 'author', label: 'by author', hint: 'Only events written by one agent.' },
  { id: 'outcome', label: 'by outcome', hint: 'Only events where a tracked metric moved.' },
  { id: 'all', label: 'everything', hint: 'Every event on this branch lineage.' },
]
