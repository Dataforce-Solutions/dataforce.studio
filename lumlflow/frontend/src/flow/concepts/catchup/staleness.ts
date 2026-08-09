/**
 * Unsynced cause for the destination list.
 *
 * `unsyncedCause` in engine.ts is the authority and is consulted first, but it
 * only fires when a materialization is literally in the `unsynced` state — and
 * no fixture ever emits that state, so on this data it returns null everywhere.
 * The interesting staleness in the churn fixture is instead the divergent pin:
 * the sweep branches forked before the `RawChurn` dedupe fix and never took it.
 *
 * `upstreamUpdates` already detects exactly that, with early cutoff, so we reuse
 * it and map it onto the same taxonomy StatusBadges renders — which keeps the
 * distinction the badge exists for: the *pinned asset itself* has a changed
 * definition, everything below it merely reads a different materialization.
 */

import { unsyncedCause, upstreamUpdates } from '../../engine'
import type { AssetId, BranchId, FlowSession, UnsyncedCause } from '../../types'

export type CauseMap = Record<AssetId, UnsyncedCause>

export function causesForBranch(session: FlowSession, branchId: BranchId): CauseMap {
  const causes: CauseMap = {}
  if (!session.branches[branchId]) return causes

  for (const update of upstreamUpdates(session, branchId)) {
    causes[update.assetId] = 'definition-changed'
    for (const affected of update.affects) {
      if (!causes[affected]) causes[affected] = 'parent-rematerialized'
    }
  }

  for (const assetId of Object.keys(session.branches[branchId].selection)) {
    const fromEngine = unsyncedCause(session, branchId, assetId)
    if (fromEngine) causes[assetId] = fromEngine
  }

  return causes
}
