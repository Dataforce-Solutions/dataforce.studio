/**
 * Unsynced detection, extended to the case the fixtures actually contain.
 *
 * `engine.unsyncedCause` reads `Materialization.state === 'unsynced'`, and no
 * fixture ever stores that state — a finished session only records settled
 * materializations. But the drift is still there in the data and is exactly
 * detectable: a materialization records `inputVersionIds`, so when a branch
 * selects a *different version of a direct parent* than the one this
 * materialization consumed, this asset is out of sync with its own branch.
 *
 * Two rules are preserved from the engine deliberately:
 *
 *  - Non-transitive (Dagster). Only *direct* parents count. On feat/tenure-buckets
 *    that means TrainTestSplit reads unsynced and TrainGBM does not — TrainGBM's
 *    own parent (Split) has not moved version.
 *  - The cause classification is the engine's, unchanged, so `changed` and
 *    `rematerialized` mean here exactly what they mean everywhere else.
 *
 * A parent whose versions appear nowhere in `inputVersionIds` is left alone
 * rather than assumed stale: fixture materializations record inputs partially,
 * and guessing would light up the canvas with false positives.
 */

import { resolveSlice, unsyncedCause, versionsOf } from '../../engine'
import type { AssetId, AssetVersion, BranchId, FlowSession, UnsyncedCause } from '../../types'

function classify(session: FlowSession, version: AssetVersion): UnsyncedCause {
  const previous = versionsOf(session, version.assetId).find(
    (candidate) => candidate.createdAtStep < version.createdAtStep,
  )
  if (previous && previous.definitionHash !== version.definitionHash) return 'definition-changed'
  if (previous && previous.definition.deps.join() !== version.definition.deps.join()) {
    return 'deps-rewired'
  }
  return 'parent-rematerialized'
}

function driftedFromInputs(
  session: FlowSession,
  slice: Record<AssetId, AssetVersion>,
  version: AssetVersion,
): boolean {
  const materialization = session.materializations[version.versionId]
  if (!materialization || materialization.state !== 'materialized') return false
  const consumed = new Set(materialization.inputVersionIds)

  return version.definition.deps.some((dep) => {
    const selected = slice[dep]
    if (!selected || consumed.has(selected.versionId)) return false
    return versionsOf(session, dep).some((candidate) => consumed.has(candidate.versionId))
  })
}

/** Batched: one `resolveSlice` for the whole canvas rather than one per node. */
export function unsyncedCauses(
  session: FlowSession,
  branchId: BranchId,
): Record<AssetId, UnsyncedCause | null> {
  const slice = resolveSlice(session, branchId)
  const result: Record<AssetId, UnsyncedCause | null> = {}
  for (const [assetId, version] of Object.entries(slice)) {
    result[assetId] =
      unsyncedCause(session, branchId, assetId) ??
      (driftedFromInputs(session, slice, version) ? classify(session, version) : null)
  }
  return result
}

export function railroadUnsyncedCause(
  session: FlowSession,
  branchId: BranchId,
  assetId: AssetId,
): UnsyncedCause | null {
  return unsyncedCauses(session, branchId)[assetId] ?? null
}
