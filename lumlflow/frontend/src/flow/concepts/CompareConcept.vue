<template>
  <!--
    Concept 2 — Compare and compose workspace.

    The bet: fan out → compare → keep the winner → export is why the product
    exists, so comparison is the architecture rather than a panel. There is no
    "the workspace, plus a diff view". The selection of 2–5 variants *is* the
    workspace, and every surface below is a projection of it.
  -->
  <div class="p-4 space-y-3">
    <PlaybackBar :playback="playback" />

    <VariantRail v-model="selected" :session="session" />

    <div class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div class="space-y-3 min-w-0">
        <CacheSkipBanner :session="session" :branch-id="comparison.pathSeed.value" />

        <FanGraph
          :session="session"
          :stages="comparison.stages.value"
          :branch-ids="branchIds"
          :shared-asset-ids="comparison.sharedAssetIds.value"
          :asserted-combinations="comparison.assertedCombinations.value"
          :path="comparison.path.value"
          :conflicts="comparison.conflicts.value"
          :unsynced-cause="unsyncedCause"
          :correlated-branch-ids="comparison.correlatedBranchIds"
          @commit="onCommit"
          @inspect="onInspect"
        />

        <ArtifactCompare
          v-model:baseline-id="baselineId"
          :session="session"
          :branch-ids="branchIds"
        />
      </div>

      <div class="space-y-3 min-w-0">
        <ActivityTicker
          :session="session"
          :branch-ids="branchIds"
          :step="playback.step.value"
          :unseen="playback.unseen.value"
          @mark-seen="playback.markSeen()"
        />

        <PathPanel
          :session="session"
          :branch-ids="branchIds"
          :nodes="comparison.nodes.value"
          :path="comparison.path.value"
          :path-seed="comparison.pathSeed.value"
          :is-novel="comparison.isNovel.value"
          :matching-branch-id="comparison.matchingBranchId.value"
          :conflicts="comparison.conflicts.value"
          :cost="comparison.cost.value"
          :unsynced-cause="unsyncedCause"
          :inspected-asset-id="inspectedAssetId"
          :shared-count="comparison.sharedAssetIds.value.length"
          @seed="onSeed"
          @export="exportOpen = true"
        />
      </div>
    </div>

    <section class="border border-surface-300 dark:border-surface-600 rounded p-3">
      <h3 class="font-medium text-sm mb-2">Every difference, including the ones with no shape</h3>
      <DifferenceTable :key="branchIds.join()" :session="session" :branch-ids="branchIds" />
    </section>

    <section class="space-y-2">
      <ScratchConsole :asset-name="scratchAssetName" @promote="onPromote" />
      <p v-if="promoted" class="text-xs text-muted-color">
        Would promote <span class="font-mono">{{ promoted }}</span> to a new asset downstream of
        <span class="font-mono">{{ scratchAssetName }}</span> on the committed path — which opens a
        new fan point here, present in this slice and absent from every other variant.
      </p>
    </section>

    <section
      v-if="exportOpen"
      class="border border-surface-300 dark:border-surface-600 rounded p-3"
    >
      <div class="flex items-center gap-2 mb-3">
        <h3 class="font-medium text-sm">Export</h3>
        <span class="text-xs text-muted-color">
          {{ comparison.isNovel.value ? 'a composed slice, not any branch' : 'an existing branch' }}
        </span>
        <button
          class="ml-auto text-xs px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600"
          @click="exportOpen = false"
        >
          close
        </button>
      </div>
      <ExportPreview :session="composedSession" branch-id="__composed" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ActivityTicker from './compare/ActivityTicker.vue'
import ArtifactCompare from './compare/ArtifactCompare.vue'
import CacheSkipBanner from '../components/CacheSkipBanner.vue'
import DifferenceTable from '../components/DifferenceTable.vue'
import ExportPreview from '../components/ExportPreview.vue'
import FanGraph from './compare/FanGraph.vue'
import PathPanel from './compare/PathPanel.vue'
import PlaybackBar from '../components/PlaybackBar.vue'
import ScratchConsole from '../components/ScratchConsole.vue'
import VariantRail from './compare/VariantRail.vue'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'
import { unsyncedCause as engineUnsyncedCause } from '../engine'
import { ABSENT, MAX_VARIANTS, useComparison } from './compare/useComparison'
import type { AssetId, BranchId, FlowSession, UnsyncedCause, VersionId } from '../types'

const { session: fixture } = useWorkspace()

const playback = usePlayback(fixture.value, { autoplay: false })
const session = computed(() => playback.session.value)

/** Branches the human picked. Survives playback; filtered to what exists yet. */
const selected = ref<BranchId[]>(defaultSelection(fixture.value))

function defaultSelection(source: FlowSession): BranchId[] {
  const ids = Object.keys(source.branches)
  const head = source.headBranchId
  return [head, ...ids.filter((id) => id !== head)].slice(0, MAX_VARIANTS)
}

const branchIds = computed(() => {
  const live = selected.value.filter((id) => session.value.branches[id])
  if (live.length >= 2) return live
  return Object.keys(session.value.branches).slice(0, Math.max(2, live.length + 1))
})

const comparison = useComparison(session, branchIds)

const baselineId = ref<BranchId>(branchIds.value[0])
const inspectedAssetId = ref<AssetId | null>(null)
const exportOpen = ref(false)
const promoted = ref('')
/** True once the human cherry-picked. Before that the path just tracks a branch. */
const composed = ref(false)

/**
 * Keep the committed path standing on ground that still exists.
 *
 * Until the human swaps something, the path simply follows its seed branch, so
 * it stays current while the log plays. After a swap it is the human's, and is
 * only re-seeded when a variant leaves the comparison or playback rewinds past a
 * version it had committed.
 */
const ensurePath = (): void => {
  const seedValid = branchIds.value.includes(comparison.pathSeed.value)
  const versionsValid = Object.entries(comparison.path.value).every(
    ([assetId, versionId]) =>
      versionId === ABSENT ||
      (session.value.assets[assetId] ?? []).some((v) => v.versionId === versionId),
  )
  if (!branchIds.value.includes(baselineId.value)) baselineId.value = branchIds.value[0]
  if (!composed.value || !seedValid || !versionsValid) {
    comparison.seedPath(seedValid ? comparison.pathSeed.value : baselineId.value)
    if (!seedValid) composed.value = false
  }
}

watch([branchIds, () => playback.step.value], ensurePath, { immediate: true })

const onCommit = (assetId: AssetId, key: VersionId | typeof ABSENT): void => {
  composed.value = true
  comparison.commit(assetId, key)
}

const onSeed = (branchId: BranchId): void => {
  composed.value = false
  comparison.seedPath(branchId)
}

/**
 * Staleness of the *committed path*, which is what these badges annotate.
 *
 * A cherry-pick creates staleness that no branch has, so the composed answer
 * wins where it has one. With nothing swapped the path is just its seed branch,
 * and the engine's per-branch answer takes over — a sweep branch reads
 * `RawChurn: changed` there without anyone touching anything, which is the
 * divergent pin stated as a badge.
 */
const unsyncedCause = (assetId: AssetId): UnsyncedCause | null =>
  comparison.unsyncedCause(assetId) ??
  engineUnsyncedCause(session.value, comparison.pathSeed.value, assetId)

const onInspect = (assetId: AssetId, key: VersionId | typeof ABSENT): void => {
  inspectedAssetId.value = key === ABSENT ? null : assetId
}

const scratchAssetName = computed(() => {
  const assetId = inspectedAssetId.value
  if (!assetId) return session.value.branches[comparison.pathSeed.value]?.name ?? 'path'
  return session.value.assets[assetId]?.at(-1)?.definition.name ?? assetId
})

const onPromote = (expression: string): void => {
  promoted.value = expression
}

/**
 * Export freezes the composed path, not a branch — so the path is presented to
 * the shared ExportPreview as the branch it would become.
 */
const composedSession = computed<FlowSession>(() => {
  const selection: Record<AssetId, VersionId> = {}
  for (const [assetId, versionId] of Object.entries(comparison.path.value)) {
    if (versionId !== ABSENT) selection[assetId] = versionId
  }
  return {
    ...session.value,
    branches: {
      ...session.value.branches,
      __composed: {
        branchId: '__composed',
        name: comparison.matchingBranchId.value
          ? (session.value.branches[comparison.matchingBranchId.value]?.name ?? 'composed')
          : 'composed slice',
        parentBranchId: comparison.pathSeed.value,
        forkedAtStep: playback.step.value,
        selection,
        pins: {},
        color: '#0ea5e9',
        archived: false,
      },
    },
  }
})
</script>
