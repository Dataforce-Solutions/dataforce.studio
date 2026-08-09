/**
 * Interface compatibility between asset versions.
 *
 * Cherry-picking composes a slice nobody ever ran, so the composed path can be
 * *interface-incompatible* in a way no existing branch is. Two rules:
 *
 * 1. Derived, from the object model: a committed version whose `deps` name an
 *    asset the path does not contain. This is what the structural rewire
 *    produces — `HoldoutEval@v2` reads `TrainLogReg`, so composing it on top of
 *    a sweep's GBM leaves a dangling dep.
 *
 * 2. Declared, in `declaredRequirements` below. The fixture cannot encode "this
 *    version needs *that* upstream version" — nothing in `AssetVersion` says so
 *    — and a merge model that silently pretends composition always works is the
 *    thing worth not demoing. So the requirement is fabricated here, explicitly,
 *    rather than hidden in the fixture. In a real system it would come from the
 *    same place a type error does: the declared input schema of `materialize()`.
 */

import type { AssetId, FlowSession, VersionId } from '../../types'

export const ABSENT = '__absent__' as const

/** One selected version per asset, or ABSENT — the shape a composed slice has. */
export type ComposedPath = Record<AssetId, VersionId | typeof ABSENT>

export interface Requirement {
  /** The version that imposes the requirement. */
  versionId: VersionId
  /** The upstream asset it constrains. */
  onAssetId: AssetId
  /** Versions of that upstream it can consume. */
  allowedVersionIds: VersionId[]
  reason: string
}

/**
 * Fabricated, and deliberately plausible: `Features@v2` calls `pd.qcut(tenure, 8)`,
 * which raises on non-unique bin edges. The July export double-counts ~4% of rows,
 * so bucketing only works against the deduplicated `RawChurn@v2`. The sweep
 * branches pin `RawChurn@v1`, which makes this reachable by direct manipulation:
 * take the bucketed features from one branch and the raw pin from another.
 */
const declaredRequirements: Requirement[] = [
  {
    versionId: 'a_features@v2',
    onAssetId: 'a_raw',
    allowedVersionIds: ['a_raw@v2'],
    reason: 'tenure bucketing needs deduplicated rows — qcut raises on non-unique bin edges',
  },
]

export interface PathConflict {
  /** Asset whose committed version cannot be satisfied. */
  assetId: AssetId
  versionId: VersionId
  /** Upstream asset that is wrong or missing. */
  onAssetId: AssetId
  message: string
  kind: 'missing-dependency' | 'incompatible-version'
}

const nameOf = (session: FlowSession, assetId: AssetId, path: ComposedPath): string => {
  const committed = path[assetId]
  const versions = session.assets[assetId] ?? []
  const hit = versions.find((version) => version.versionId === committed) ?? versions.at(-1)
  return hit?.definition.name ?? assetId
}

const tagOf = (versionId: VersionId): string => versionId.split('@')[1] ?? versionId

export function pathConflicts(session: FlowSession, path: ComposedPath): PathConflict[] {
  const conflicts: PathConflict[] = []

  for (const [assetId, versionId] of Object.entries(path)) {
    if (versionId === ABSENT) continue
    const version = (session.assets[assetId] ?? []).find((item) => item.versionId === versionId)
    if (!version) continue

    for (const depId of version.definition.deps) {
      if (path[depId] && path[depId] !== ABSENT) continue
      conflicts.push({
        assetId,
        versionId,
        onAssetId: depId,
        kind: 'missing-dependency',
        message: `\`${version.definition.name}\` ${tagOf(versionId)} reads \`${nameOf(session, depId, path)}\`, which this path does not contain.`,
      })
    }

    for (const requirement of declaredRequirements) {
      if (requirement.versionId !== versionId) continue
      const committed = path[requirement.onAssetId]
      if (!committed || committed === ABSENT) continue
      if (requirement.allowedVersionIds.includes(committed)) continue
      conflicts.push({
        assetId,
        versionId,
        onAssetId: requirement.onAssetId,
        kind: 'incompatible-version',
        message: `\`${version.definition.name}\` ${tagOf(versionId)} expects \`${nameOf(session, requirement.onAssetId, path)}\` ${requirement.allowedVersionIds.map(tagOf).join(' or ')}, the current path has ${tagOf(committed)} — ${requirement.reason}.`,
      })
    }
  }

  return conflicts
}
