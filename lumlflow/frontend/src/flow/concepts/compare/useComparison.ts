/**
 * The derived model behind "the workspace is the comparison".
 *
 * Everything that is a shared derived view (divergence, cost, integrity, unsynced)
 * comes from engine.ts. What lives here is the part that only exists because this
 * concept lets you *compose* a slice that no branch ever ran:
 *
 * - the scoped fan graph: fan on definition divergence, collapse materialization
 *   divergence into one node carrying N result chips;
 * - effective content keys, so a collapsed node can honestly say how many
 *   *distinct* results hide behind it, and so cache hits for a composed path are
 *   computed the way the kernel would compute them;
 * - the committed path, its conflicts, its cost, and its staleness.
 */

import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { divergence, resolveSlice } from '../../engine'
import { ABSENT, pathConflicts, type ComposedPath, type PathConflict } from './compat'
import type {
  AgentId,
  AssetId,
  AssetVersion,
  BranchId,
  DivergenceKind,
  FlowSession,
  PreflightCost,
  UnsyncedCause,
  VersionId,
} from '../../types'

export { ABSENT } from './compat'
export type { ComposedPath, PathConflict } from './compat'

/** Supervision ceiling. Selecting from 20 is fine; comparing 20 at once is not. */
export const MAX_VARIANTS = 5
export const MIN_VARIANTS = 2

export interface Variant {
  /** versionId, or ABSENT for branches in which the asset does not exist. */
  key: VersionId | typeof ABSENT
  tag: string
  intent: string
  author: AgentId
  failed: boolean
  branchIds: BranchId[]
}

export interface ResultGroup {
  /** Effective content key: versionId folded with the keys of every upstream. */
  key: string
  branchIds: BranchId[]
  label: string
  metric: { name: string; value: number } | null
}

export interface FanNode {
  assetId: AssetId
  name: string
  kind: Extract<DivergenceKind, 'definition' | 'materialization'>
  depth: number
  /** Deps restricted to the scoped sub-DAG, hopping over unchanged assets. */
  scopedDeps: AssetId[]
  variants: Variant[]
  results: ResultGroup[]
}

export interface ComparisonModel {
  slices: ComputedRef<Record<BranchId, Record<AssetId, AssetVersion>>>
  nodes: ComputedRef<FanNode[]>
  stages: ComputedRef<FanNode[][]>
  sharedAssetIds: ComputedRef<AssetId[]>
  /** Combinations the canvas would assert if every fan were independent. */
  assertedCombinations: ComputedRef<number>
  path: Ref<ComposedPath>
  pathSeed: Ref<BranchId>
  seedPath: (branchId: BranchId) => void
  commit: (assetId: AssetId, key: VersionId | typeof ABSENT) => void
  isNovel: ComputedRef<boolean>
  matchingBranchId: ComputedRef<BranchId | null>
  conflicts: ComputedRef<PathConflict[]>
  cost: ComputedRef<PreflightCost>
  unsyncedCause: (assetId: AssetId) => UnsyncedCause | null
  correlatedBranchIds: (assetId: AssetId, key: VersionId | typeof ABSENT) => BranchId[]
}

const tagOf = (versionId: string): string => versionId.split('@')[1] ?? versionId

export function useComparison(
  session: Ref<FlowSession>,
  branchIds: Ref<BranchId[]>,
): ComparisonModel {
  const slices = computed(() => {
    const out: Record<BranchId, Record<AssetId, AssetVersion>> = {}
    for (const branchId of branchIds.value) out[branchId] = resolveSlice(session.value, branchId)
    return out
  })

  /** Deps unioned across the selected variants — a rewire adds edges, never drops them. */
  const unionDeps = computed(() => {
    const out: Record<AssetId, Set<AssetId>> = {}
    for (const slice of Object.values(slices.value)) {
      for (const version of Object.values(slice)) {
        out[version.assetId] = out[version.assetId] ?? new Set()
        version.definition.deps.forEach((dep) => out[version.assetId].add(dep))
      }
    }
    return out
  })

  /**
   * Effective content key — `hash(version, upstream keys)` in spirit.
   *
   * This is the number the kernel would actually address a materialization by,
   * and it is why two branches that differ only above `Features` still share
   * every cached materialization below an asset they both left alone.
   */
  const effectiveKey = (
    slice: Record<AssetId, AssetVersion>,
    assetId: AssetId,
    memo: Map<AssetId, string>,
    seen: Set<AssetId> = new Set(),
  ): string => {
    const cached = memo.get(assetId)
    if (cached) return cached
    if (seen.has(assetId)) return '∅'
    seen.add(assetId)
    const version = slice[assetId]
    if (!version) return '∅'
    const upstream = [...(unionDeps.value[assetId] ?? [])]
      .sort()
      .map((dep) => effectiveKey(slice, dep, memo, seen))
      .join(',')
    const key = `${version.versionId}(${upstream})`
    memo.set(assetId, key)
    return key
  }

  const keysByBranch = computed(() => {
    const out: Record<BranchId, Map<AssetId, string>> = {}
    for (const [branchId, slice] of Object.entries(slices.value)) {
      const memo = new Map<AssetId, string>()
      Object.keys(slice).forEach((assetId) => effectiveKey(slice, assetId, memo))
      out[branchId] = memo
    }
    return out
  })

  const divergenceByAsset = computed(() => {
    const out: Record<AssetId, DivergenceKind> = {}
    for (const entry of divergence(session.value, branchIds.value)) out[entry.assetId] = entry.kind
    return out
  })

  /**
   * Scope: fan points, plus everything downstream of one.
   *
   * Assets that no selected variant touched, and that sit above every fan, are
   * not drawn at all — they are the shared trunk and drawing them is what turns a
   * comparison into a graph screenshot.
   */
  const scopedIds = computed(() => {
    const definitionFans = Object.keys(divergenceByAsset.value).filter(
      (assetId) => divergenceByAsset.value[assetId] === 'definition',
    )
    const scoped = new Set<AssetId>(definitionFans)
    const queue = [...definitionFans]
    while (queue.length) {
      const current = queue.shift() as AssetId
      for (const [assetId, deps] of Object.entries(unionDeps.value)) {
        if (!deps.has(current) || scoped.has(assetId)) continue
        scoped.add(assetId)
        queue.push(assetId)
      }
    }
    for (const [assetId, kind] of Object.entries(divergenceByAsset.value)) {
      if (kind === 'materialization') scoped.add(assetId)
    }
    return scoped
  })

  const sharedAssetIds = computed(() =>
    Object.keys(divergenceByAsset.value).filter((assetId) => !scopedIds.value.has(assetId)),
  )

  /** First scoped ancestors, hopping over unchanged assets so the graph stays short. */
  const scopedDepsOf = (assetId: AssetId): AssetId[] => {
    const out = new Set<AssetId>()
    const queue = [...(unionDeps.value[assetId] ?? [])]
    const seen = new Set<AssetId>(queue)
    while (queue.length) {
      const current = queue.shift() as AssetId
      if (scopedIds.value.has(current)) {
        out.add(current)
        continue
      }
      for (const dep of unionDeps.value[current] ?? []) {
        if (seen.has(dep)) continue
        seen.add(dep)
        queue.push(dep)
      }
    }
    return [...out]
  }

  const nameOf = (assetId: AssetId): string => {
    for (const slice of Object.values(slices.value)) {
      if (slice[assetId]) return slice[assetId].definition.name
    }
    return assetId
  }

  const variantsOf = (assetId: AssetId): Variant[] => {
    const byKey = new Map<string, Variant>()
    for (const branchId of branchIds.value) {
      const version = slices.value[branchId]?.[assetId]
      const key: VersionId | typeof ABSENT = version?.versionId ?? ABSENT
      const existing = byKey.get(key)
      if (existing) {
        existing.branchIds.push(branchId)
        continue
      }
      byKey.set(key, {
        key,
        tag: version ? tagOf(version.versionId) : 'absent',
        intent: version?.intent ?? 'not present in this variant',
        author: version?.authoredBy ?? 'human',
        failed: version?.status === 'failed',
        branchIds: [branchId],
      })
    }
    return [...byKey.values()]
  }

  const headlineMetric = (
    versionId: VersionId | undefined,
  ): { name: string; value: number } | null => {
    const metrics = versionId ? session.value.materializations[versionId]?.metrics : undefined
    const entries = Object.entries(metrics ?? {})
    return entries.length ? { name: entries[0][0], value: entries[0][1] } : null
  }

  const resultsOf = (assetId: AssetId): ResultGroup[] => {
    const byKey = new Map<string, ResultGroup>()
    for (const branchId of branchIds.value) {
      const version = slices.value[branchId]?.[assetId]
      const key = keysByBranch.value[branchId]?.get(assetId) ?? '∅'
      const existing = byKey.get(key)
      if (existing) {
        existing.branchIds.push(branchId)
        continue
      }
      byKey.set(key, {
        key,
        branchIds: [branchId],
        label: version ? tagOf(version.versionId) : 'absent',
        metric: headlineMetric(version?.versionId),
      })
    }
    return [...byKey.values()]
  }

  const nodes = computed<FanNode[]>(() => {
    const list = [...scopedIds.value].map((assetId) => ({
      assetId,
      name: nameOf(assetId),
      kind: (divergenceByAsset.value[assetId] === 'definition'
        ? 'definition'
        : 'materialization') as FanNode['kind'],
      depth: 0,
      scopedDeps: scopedDepsOf(assetId),
      variants: variantsOf(assetId),
      results: resultsOf(assetId),
    }))

    // Longest path, memoized on the node. The stack is a cycle guard and has to
    // be popped: a diamond (HoldoutEval reads both TrainGBM and TrainTestSplit)
    // revisits a node that is still on the stack of an unrelated branch of the
    // search, and treating that as a cycle silently flattens the whole graph.
    const byId = new Map(list.map((node) => [node.assetId, node]))
    const depthOf = (assetId: AssetId, stack: Set<AssetId>): number => {
      const node = byId.get(assetId)
      if (!node) return 0
      if (node.depth) return node.depth
      if (stack.has(assetId)) return 0
      stack.add(assetId)
      const parents = node.scopedDeps.map((dep) => depthOf(dep, stack))
      stack.delete(assetId)
      node.depth = parents.length ? Math.max(...parents) + 1 : 0
      return node.depth
    }
    list.forEach((node) => depthOf(node.assetId, new Set()))
    return list.sort((a, b) => a.depth - b.depth || a.name.localeCompare(b.name))
  })

  const stages = computed(() => {
    const grouped = new Map<number, FanNode[]>()
    for (const node of nodes.value) {
      grouped.set(node.depth, [...(grouped.get(node.depth) ?? []), node])
    }
    return [...grouped.entries()].sort((a, b) => a[0] - b[0]).map(([, group]) => group)
  })

  const assertedCombinations = computed(() =>
    nodes.value
      .filter((node) => node.kind === 'definition')
      .reduce((product, node) => product * Math.max(1, node.variants.length), 1),
  )

  // --- the committed path ---------------------------------------------------

  const path = ref<ComposedPath>({})
  const pathSeed = ref<BranchId>(branchIds.value[0] ?? '')

  const seedPath = (branchId: BranchId): void => {
    pathSeed.value = branchId
    const next: ComposedPath = {}
    const assetIds = new Set<AssetId>()
    Object.values(slices.value).forEach((slice) => Object.keys(slice).forEach((id) => assetIds.add(id)))
    for (const assetId of assetIds) {
      next[assetId] = slices.value[branchId]?.[assetId]?.versionId ?? ABSENT
    }
    path.value = next
  }

  const commit = (assetId: AssetId, key: VersionId | typeof ABSENT): void => {
    path.value = { ...path.value, [assetId]: key }
  }

  const pathSlice = computed(() => {
    const slice: Record<AssetId, AssetVersion> = {}
    for (const [assetId, versionId] of Object.entries(path.value)) {
      if (versionId === ABSENT) continue
      const version = (session.value.assets[assetId] ?? []).find((v) => v.versionId === versionId)
      if (version) slice[assetId] = version
    }
    return slice
  })

  const pathKeys = computed(() => {
    const memo = new Map<AssetId, string>()
    Object.keys(pathSlice.value).forEach((assetId) => effectiveKey(pathSlice.value, assetId, memo))
    return memo
  })

  const matchingBranchId = computed(() => {
    for (const branch of Object.values(session.value.branches)) {
      const selection = branch.selection
      const committed = Object.entries(path.value).filter(([, v]) => v !== ABSENT)
      if (Object.keys(selection).length !== committed.length) continue
      if (committed.every(([assetId, versionId]) => selection[assetId] === versionId)) {
        return branch.branchId
      }
    }
    return null
  })

  const isNovel = computed(() => matchingBranchId.value === null)

  const conflicts = computed(() => pathConflicts(session.value, path.value))

  /**
   * Cost of materializing the composed path.
   *
   * A slice is a cache hit exactly when some branch already materialized this
   * asset under the same effective key — which is the "shared node, shared
   * materialization" claim stated as arithmetic rather than as a promise.
   */
  const knownKeys = computed(() => {
    const known = new Set<string>()
    for (const branchId of Object.keys(session.value.branches)) {
      const slice = resolveSlice(session.value, branchId)
      const memo = new Map<AssetId, string>()
      for (const assetId of Object.keys(slice)) {
        const key = effectiveKey(slice, assetId, memo)
        const materialization = session.value.materializations[slice[assetId].versionId]
        // Same test `preflightCost` applies, so the composed path's number is
        // comparable with the per-branch numbers shown next to it.
        if (materialization?.state === 'materialized' && materialization.cached) {
          known.add(`${assetId}::${key}`)
        }
      }
    }
    return known
  })

  const cost = computed<PreflightCost>(() => {
    const cachedAssetIds: AssetId[] = []
    const recomputeAssetIds: AssetId[] = []
    let totalSeconds = 0
    for (const [assetId, version] of Object.entries(pathSlice.value)) {
      const key = pathKeys.value.get(assetId) ?? '∅'
      if (knownKeys.value.has(`${assetId}::${key}`)) {
        cachedAssetIds.push(assetId)
      } else {
        recomputeAssetIds.push(assetId)
        totalSeconds += session.value.materializations[version.versionId]?.costSeconds ?? 0
      }
    }
    return { cachedAssetIds, recomputeAssetIds, totalSeconds }
  })

  /**
   * Staleness of the composed path relative to the branch it was seeded from.
   *
   * Same non-transitive rule as the engine, applied to a slice that does not
   * exist yet: an asset you swapped reads "changed"; one that merely sits below a
   * swap reads "rematerialized" and is drawn quietly, because it is not news.
   */
  const unsyncedCause = (assetId: AssetId): UnsyncedCause | null => {
    const seedSlice = slices.value[pathSeed.value]
    if (!seedSlice) return null
    const committed = pathSlice.value[assetId]
    const seeded = seedSlice[assetId]
    if (!committed || !seeded) return committed || seeded ? 'deps-rewired' : null

    if (committed.definition.deps.join() !== seeded.definition.deps.join()) return 'deps-rewired'
    if (committed.definitionHash !== seeded.definitionHash) return 'definition-changed'

    const seedKeys = keysByBranch.value[pathSeed.value]
    for (const dep of committed.definition.deps) {
      if ((pathKeys.value.get(dep) ?? '∅') !== (seedKeys?.get(dep) ?? '∅')) {
        return 'parent-rematerialized'
      }
    }
    return null
  }

  /** Branches whose slice contains this exact variant — the correlation set. */
  const correlatedBranchIds = (assetId: AssetId, key: VersionId | typeof ABSENT): BranchId[] =>
    branchIds.value.filter(
      (branchId) => (slices.value[branchId]?.[assetId]?.versionId ?? ABSENT) === key,
    )

  return {
    slices,
    nodes,
    stages,
    sharedAssetIds,
    assertedCombinations,
    path,
    pathSeed,
    seedPath,
    commit,
    isNovel,
    matchingBranchId,
    conflicts,
    cost,
    unsyncedCause,
    correlatedBranchIds,
  }
}
