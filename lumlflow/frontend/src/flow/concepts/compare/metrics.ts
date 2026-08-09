/**
 * Metric polarity, so a delta can be signed *and* coloured.
 *
 * `+0.03` is not good news for log loss. Colour has to follow the direction the
 * metric wants to move, or the comparison surface is actively misleading in
 * exactly the situation it exists for.
 */

import { resolveSlice } from '../../engine'
import type { BranchId, FlowSession } from '../../types'

/** Substrings that flip polarity when the fixture does not declare it. */
const LOWER_IS_BETTER = [
  'loss',
  'error',
  'err',
  'rmse',
  'mae',
  'mse',
  'latency',
  '_ms',
  'cost',
  'refusal',
  'drift',
  'fpr',
  'regret',
]

export interface MetricRow {
  name: string
  higherIsBetter: boolean
  byBranch: Record<BranchId, number | null>
}

/**
 * Declared polarity wins: `MetricValue.higherIsBetter` is in the object model
 * precisely so this is not a guess. The name heuristic is the fallback for
 * metrics that only ever appear in a `Materialization.metrics` bag.
 */
function polarityOf(session: FlowSession, branchIds: BranchId[], name: string): boolean {
  for (const branchId of branchIds) {
    for (const version of Object.values(resolveSlice(session, branchId))) {
      for (const value of Object.values(session.materializations[version.versionId]?.values ?? {})) {
        if (value.type === 'metric' && value.name === name) return value.higherIsBetter
      }
    }
  }
  const lowered = name.toLowerCase()
  return !LOWER_IS_BETTER.some((token) => lowered.includes(token))
}

export function metricRows(session: FlowSession, branchIds: BranchId[]): MetricRow[] {
  const byBranch: Record<BranchId, Record<string, number>> = {}
  for (const branchId of branchIds) {
    const merged: Record<string, number> = {}
    for (const version of Object.values(resolveSlice(session, branchId))) {
      Object.assign(merged, session.materializations[version.versionId]?.metrics ?? {})
    }
    byBranch[branchId] = merged
  }

  const names = new Set<string>()
  Object.values(byBranch).forEach((metrics) => Object.keys(metrics).forEach((n) => names.add(n)))

  return [...names].sort().map((name) => ({
    name,
    higherIsBetter: polarityOf(session, branchIds, name),
    byBranch: Object.fromEntries(
      branchIds.map((branchId) => [branchId, byBranch[branchId]?.[name] ?? null]),
    ),
  }))
}

/** Signed delta plus whether the sign is good news for this metric. */
export function deltaOf(
  row: MetricRow,
  branchId: BranchId,
  referenceId: BranchId,
): { value: number; favourable: boolean } | null {
  const value = row.byBranch[branchId]
  const reference = row.byBranch[referenceId]
  if (value === null || reference === null || value === undefined || reference === undefined) {
    return null
  }
  const delta = value - reference
  return { value: delta, favourable: row.higherIsBetter ? delta >= 0 : delta <= 0 }
}
