import type { ArtifactValue, AssetVersion, FlowSession, Materialization } from '../../types'

/**
 * A materialization can carry several outputs (model, checkpoint, run, metrics).
 * "First value wins" showed a parameter listing where the training run was —
 * the card body should be the most readable output, not the first-declared one.
 */
const BODY_PRIORITY: ArtifactValue['type'][] = [
  'experiment',
  'eval',
  'plot',
  'frame',
  'note',
  'metric',
  'model',
]

export function primaryArtifactValue(
  materialization: Materialization | undefined,
): ArtifactValue | null {
  const values = Object.values(materialization?.values ?? {})
  if (!values.length) return null
  return [...values].sort(
    (a, b) => BODY_PRIORITY.indexOf(a.type) - BODY_PRIORITY.indexOf(b.type),
  )[0]
}

export interface ExperimentRef {
  href: string
  label: string
}

/**
 * An experiment materialized in a flow *is* a tracked experiment, so the card
 * links out to the tracker rather than re-embedding it. The group is the flow's
 * project; the run id is the run name (or, for evals, the materialized version) —
 * in a real integration the materialization would record the tracker's run id.
 */
export function experimentRef(
  session: FlowSession,
  version: AssetVersion,
  value: ArtifactValue | null,
): ExperimentRef | null {
  if (value?.type === 'experiment') {
    return {
      href: `/experiments/${encodeURIComponent(session.projectName)}/${encodeURIComponent(value.runName)}`,
      label: 'Open full experiment',
    }
  }
  if (value?.type === 'eval') {
    return {
      href: `/experiments/${encodeURIComponent(session.projectName)}/${encodeURIComponent(version.versionId)}/evals`,
      label: 'Open full evaluation',
    }
  }
  return null
}
