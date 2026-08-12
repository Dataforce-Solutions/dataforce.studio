import type { FlowCell } from '../../model/types'

export type HandoffGesture = 'fix' | 'explain' | 'improve'

/**
 * The context payload handed to the agent (ui-draft §4 / §15) as a compact
 * fenced block an agent CLI can consume. The address is slug + branch + step
 * only — internal ids, hashes, and memo keys never leave the store.
 */
export function buildHandoffPayload(
  cell: FlowCell,
  branch: string,
  gesture: HandoffGesture,
): string {
  const lines = [
    '```lumlflow-context',
    `gesture: ${gesture}`,
    `branch: ${branch}`,
    `cell: ${cell.slug}`,
    `step: ${cell.provenance.step}`,
  ]
  if (cell.doc) lines.push(`doc: ${cell.doc}`)
  if (cell.error) {
    lines.push(`error: ${cell.error.summary}`)
    lines.push('traceback: |')
    for (const row of cell.error.traceback.split('\n')) lines.push(`  ${row}`)
  }
  lines.push('```')
  return lines.join('\n')
}
