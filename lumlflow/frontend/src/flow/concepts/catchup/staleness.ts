/**
 * Batched staleness lookup for the destination list.
 *
 * No logic of its own — `engine.unsyncedCause` is the authority, and all three
 * concepts must render one definition of stale or the bake-off compares
 * different numbers rather than different designs. This exists only so the
 * template resolves each branch's slice once instead of once per asset.
 */

import { unsyncedCause } from '../../engine'
import type { AssetId, BranchId, FlowSession, UnsyncedCause } from '../../types'

export type CauseMap = Record<AssetId, UnsyncedCause>

export function causesForBranch(session: FlowSession, branchId: BranchId): CauseMap {
  const causes: CauseMap = {}
  const branch = session.branches[branchId]
  if (!branch) return causes

  for (const assetId of Object.keys(branch.selection)) {
    const cause = unsyncedCause(session, branchId, assetId)
    if (cause) causes[assetId] = cause
  }
  return causes
}
