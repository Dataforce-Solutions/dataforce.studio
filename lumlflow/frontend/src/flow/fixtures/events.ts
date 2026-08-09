/**
 * The adversarial event log for scenario (a).
 *
 * Written to break concepts rather than flatter them. In order it contains:
 * a cell-by-cell human/agent build, a failed materialization followed by a fix,
 * two agents forking concurrently, a rename mid-flight, a human bugfix to a
 * shared upstream that the already-forked sweep branches never take, a burst of
 * twelve transactions from a sweep agent inside four steps, and a structural
 * rewire that deletes one asset and adds another.
 *
 * If a concept reads well against a log that streams at human pace, it has
 * dodged the problem. The burst is the point.
 */

import type { Transaction } from '../types'
import { churnSession, churnVersions as v } from './churn'

const tx = (
  step: number,
  branchId: string,
  author: string,
  intent: string,
  ops: Transaction['ops'],
  settled = false,
): Transaction => ({ txId: `tx-${step}`, step, branchId, author, intent, ops, settled })

const created = (assetId: string, versionId: string): Transaction['ops'] => {
  const version = churnSession.assets[assetId]?.find((item) => item.versionId === versionId)
  if (!version) return []
  const materialization = churnSession.materializations[versionId]
  const ops: Transaction['ops'] = [{ op: 'create-asset', assetId, version }]
  if (materialization) ops.push({ op: 'materialize', assetId, versionId, result: materialization })
  return ops
}

const edited = (assetId: string, versionId: string): Transaction['ops'] => {
  const version = churnSession.assets[assetId]?.find((item) => item.versionId === versionId)
  if (!version) return []
  const materialization = churnSession.materializations[versionId]
  const ops: Transaction['ops'] = [{ op: 'edit-asset', assetId, version }]
  if (materialization) ops.push({ op: 'materialize', assetId, versionId, result: materialization })
  return ops
}

export const churnTransactions: Transaction[] = [
  tx(1, 'main', 'human', 'Pull the raw churn export', created('a_raw', v.rawV1.versionId), true),
  tx(2, 'main', 'human', 'Look at the raw export', created('a_profile', 'a_profile@v1'), true),
  tx(3, 'main', 'agent-1', 'Chart missingness before cleaning', created('a_missing', 'a_missing@v1')),
  tx(4, 'main', 'agent-1', 'Chart missingness before cleaning', created('a_balance', 'a_balance@v1'), true),
  tx(5, 'main', 'agent-1', 'Clean the raw frame', created('a_clean', v.cleanedV1.versionId), true),
  tx(6, 'main', 'agent-1', 'Build a baseline feature set', created('a_features', v.featuresBase.versionId)),
  tx(7, 'main', 'agent-1', 'Build a baseline feature set', created('a_split', 'a_split@v1'), true),

  // The failure and its fix: two versions of one asset, zero branches.
  tx(8, 'main', 'agent-1', 'Train a gradient boosting baseline', created('a_gbm', v.gbmFailed.versionId)),
  tx(9, 'main', 'agent-1', 'Fix the constructor call and retrain', edited('a_gbm', v.gbmV1.versionId), true),

  tx(10, 'main', 'agent-1', 'Score the baseline on holdout', created('a_eval', v.evalGbm.versionId)),
  tx(11, 'main', 'human', 'Write up the baseline result', created('a_report', 'a_report@v1'), true),

  // Two agents fork within two steps of each other.
  tx(12, 'feat-buckets', 'agent-1', 'Try tenure bucketing', [
    { op: 'fork-branch', branchId: 'feat-buckets', fromBranchId: 'main', name: 'feat/tenure-buckets' },
    ...edited('a_features', v.featuresBuckets.versionId),
  ]),
  tx(14, 'feat-interactions', 'agent-2', 'Try contract-tenure interactions', [
    { op: 'fork-branch', branchId: 'feat-interactions', fromBranchId: 'main', name: 'feat/interactions' },
    ...edited('a_features', v.featuresInteractions.versionId),
  ], true),

  // A rename mid-flight. Identity survives; the label does not.
  tx(18, 'main', 'agent-2', 'Rename Cleaned to CleanChurn for consistency', [
    { op: 'rename-asset', assetId: 'a_clean', from: 'Cleaned', to: 'CleanChurn' },
    ...edited('a_clean', v.cleanedV2.versionId),
  ], true),

  // Sweep forks before the upstream fix lands — this is what creates divergent pins.
  tx(20, 'sweep-600-005', 'agent-3', 'Sweep n_estimators and learning_rate', [
    { op: 'fork-branch', branchId: 'sweep-600-005', fromBranchId: 'main', name: 'sweep/600-0.05' },
  ]),

  tx(22, 'main', 'human', 'Fix duplicate customer rows in the July export', edited('a_raw', v.rawV2.versionId), true),

  // Burst: twelve transactions inside four steps, from one agent.
  ...[
    { step: 26, branch: 'sweep-600-005', version: v.gbmV2 },
    { step: 27, branch: 'sweep-300-01', version: v.gbmV3 },
    { step: 28, branch: 'sweep-900-003', version: v.gbmV4 },
  ].flatMap(({ step, branch, version }) => [
    tx(step, branch, 'agent-3', 'Sweep n_estimators and learning_rate', [
      ...(branch === 'sweep-600-005'
        ? []
        : [{ op: 'fork-branch' as const, branchId: branch, fromBranchId: 'main', name: branch }]),
      ...edited('a_gbm', version.versionId),
    ]),
    tx(step, branch, 'agent-3', 'Sweep n_estimators and learning_rate', edited('a_eval', v.evalGbm.versionId)),
    tx(step, branch, 'agent-3', 'Sweep n_estimators and learning_rate', [
      { op: 'materialize', assetId: 'a_report', versionId: 'a_report@v1', result: churnSession.materializations['a_report@v1'] },
    ], true),
  ]),

  // Structural rewire: one asset deleted, one added, a consumer repointed.
  tx(30, 'model-logreg', 'agent-2', 'Swap GBM for an interpretable baseline', [
    { op: 'fork-branch', branchId: 'model-logreg', fromBranchId: 'main', name: 'model/logreg' },
    ...created('a_logreg', v.logreg.versionId),
    { op: 'delete-asset', assetId: 'a_gbm' },
  ]),
  tx(31, 'model-logreg', 'agent-2', 'Swap GBM for an interpretable baseline', [
    { op: 'rewire-asset', assetId: 'a_eval', depsBefore: ['a_gbm', 'a_split'], depsAfter: ['a_logreg', 'a_split'] },
    ...edited('a_eval', v.evalRewired.versionId),
  ], true),
]

churnSession.transactions = churnTransactions

export const lastStep = churnTransactions.reduce((max, item) => Math.max(max, item.step), 0)
