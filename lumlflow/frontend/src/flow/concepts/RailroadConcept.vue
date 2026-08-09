<template>
  <!--
    Concept 1 — Canvas + focused railroad.

    Structure and time are two surfaces, not one drawing: a spatially stable
    canvas of the selected variant, and a railroad beside it that is a *scoped
    query* over history rather than a second topology. They are joined by
    brushing, which only ever changes what is visible — never where anything sits.
  -->
  <div class="h-full min-h-[44rem] flex flex-col gap-2 p-3">
    <BranchRail
      :session="playback.session.value"
      :branch-id="branchId"
      :compare-ids="compareIds"
      @select="selectBranch"
      @toggle-compare="toggleCompare"
    />

    <CacheSkipBanner
      v-if="announceCache"
      :session="playback.session.value"
      :branch-id="branchId"
    />

    <div class="flex items-center gap-2">
      <PlaybackBar class="flex-1" :playback="playback" />
      <button
        class="px-2 py-1 rounded border text-xs whitespace-nowrap"
        :class="
          playback.unseen.value.length
            ? 'border-primary-500 text-primary-600 dark:text-primary-400'
            : 'border-surface-300 dark:border-surface-600 text-muted-color'
        "
        @click="playback.markSeen()"
      >
        {{ playback.unseen.value.length }} unseen · mark read
      </button>
    </div>

    <div
      class="flex-1 min-h-0 flex rounded border border-surface-200 dark:border-surface-700 overflow-hidden"
    >
      <div class="flex-1 min-w-0">
        <AssetCanvas
          :session="playback.session.value"
          :full-session="session"
          :branch-id="branchId"
          :layout="layout"
          :pulses="pulses"
          :selected-asset-id="selectedAssetId"
          :filter-root-id="filterRootId"
          :marked-asset-ids="markedAssetIds"
          @select="selectAsset"
          @filter="filterRootId = $event"
        />
      </div>
      <div class="w-64 shrink-0">
        <RailroadTimeline
          :session="playback.session.value"
          :full-session="session"
          :branch-id="branchId"
          :selected-asset-id="selectedAssetId"
          :selected-tx-id="selectedTxId"
          :lens="lens"
          :agent-filter="agentFilter"
          @update:lens="lens = $event"
          @update:agent-filter="agentFilter = $event"
          @select-checkpoint="selectCheckpoint"
        />
      </div>
      <div class="w-80 shrink-0">
        <AssetInspector
          :session="playback.session.value"
          :branch-id="branchId"
          :asset-id="selectedAssetId"
        />
      </div>
    </div>

    <div class="shrink-0">
      <div class="flex items-center gap-1 text-xs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="px-2 py-1 rounded border"
          :class="
            drawer === tab.id
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-surface-300 dark:border-surface-600 text-muted-color'
          "
          @click="drawer = drawer === tab.id ? null : tab.id"
        >
          {{ tab.label }}
        </button>
        <span class="ml-2 text-[11px] text-muted-color">
          editing lives in the right-hand panel — nodes never expand
        </span>
      </div>

      <div
        v-if="drawer"
        class="mt-2 max-h-96 overflow-auto rounded border border-surface-200 dark:border-surface-700 p-3"
      >
        <DifferenceTable
          v-if="drawer === 'compare'"
          :session="playback.session.value"
          :branch-ids="compareIds"
        />
        <ExportPreview v-else :session="playback.session.value" :branch-id="branchId" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CacheSkipBanner from '../components/CacheSkipBanner.vue'
import DifferenceTable from '../components/DifferenceTable.vue'
import ExportPreview from '../components/ExportPreview.vue'
import PlaybackBar from '../components/PlaybackBar.vue'
import AssetCanvas from './railroad/AssetCanvas.vue'
import BranchRail from './railroad/BranchRail.vue'
import AssetInspector from './railroad/AssetInspector.vue'
import RailroadTimeline from './railroad/RailroadTimeline.vue'
import { buildLayout } from './railroad/layout'
import type { RailroadLens } from './railroad/lens'
import { usePulses } from './railroad/usePulses'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'
import type { AgentId, AssetId, BranchId } from '../types'

const { session: sessionRef } = useWorkspace()
const session = sessionRef.value
const playback = usePlayback(session)

const branchId = ref<BranchId>(session.headBranchId)
const compareIds = ref<BranchId[]>([session.headBranchId])
const selectedAssetId = ref<AssetId | null>(null)
const filterRootId = ref<AssetId | null>(null)
const selectedTxId = ref<string | null>(null)
const lens = ref<RailroadLens>('all')
const agentFilter = ref<AgentId>(Object.keys(session.agents)[0] ?? 'human')
const drawer = ref<'compare' | 'export' | null>(null)
const announceCache = ref(false)

const tabs = [
  { id: 'compare' as const, label: 'compare variants' },
  { id: 'export' as const, label: 'freeze & export' },
]

const layout = computed(() => buildLayout(session))
const { pulses } = usePulses(playback.session, branchId, playback.step)

const selectedTx = computed(() =>
  selectedTxId.value
    ? (session.transactions.find((tx) => tx.txId === selectedTxId.value) ?? null)
    : null,
)

/** Railroad → canvas: the checkpoint's own ops are what "changed here" means. */
const markedAssetIds = computed<AssetId[]>(() => {
  if (!selectedTx.value) return []
  return [...new Set(selectedTx.value.ops.flatMap((op) => ('assetId' in op ? [op.assetId] : [])))]
})

let bannerTimer: ReturnType<typeof setTimeout> | null = null
const selectBranch = (next: BranchId): void => {
  if (next === branchId.value) return
  branchId.value = next
  if (!compareIds.value.includes(next)) compareIds.value = [...compareIds.value, next]
  // Cached work emits no events, so a switch that is 90% cache reads as a dead
  // screen unless the skip set is announced up front.
  announceCache.value = true
  if (bannerTimer) clearTimeout(bannerTimer)
  bannerTimer = setTimeout(() => {
    announceCache.value = false
  }, 8000)
}

const toggleCompare = (id: BranchId): void => {
  compareIds.value = compareIds.value.includes(id)
    ? compareIds.value.filter((entry) => entry !== id)
    : [...compareIds.value, id]
  if (!compareIds.value.length) compareIds.value = [branchId.value]
}

/** Canvas → railroad: selecting an asset re-scopes history to that asset in place. */
const selectAsset = (assetId: AssetId): void => {
  selectedAssetId.value = assetId
  lens.value = 'asset'
}

const selectCheckpoint = (txId: string): void => {
  selectedTxId.value = txId
  const tx = session.transactions.find((entry) => entry.txId === txId)
  if (tx) playback.seek(tx.step)
}

// Playing forward invalidates a pinned checkpoint selection: the canvas is
// showing the live head again, so the "changed here" marks must go.
watch(playback.playing, (playing) => {
  if (playing) selectedTxId.value = null
})
</script>
