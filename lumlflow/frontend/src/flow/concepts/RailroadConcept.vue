<template>
  <!--
    Concept 1 — Canvas + focused railroad.

    Two surfaces joined by brushing: a flow of assets that grows downward, and a
    history view beside it that is a scoped query rather than a second topology.
    Output-first — the materialization is the body of every card, because in
    DS/ML the artifact of record is the finding and the code is scaffolding.
  -->
  <div class="h-[calc(100vh-190px)] flex flex-col gap-6">
    <div class="flex items-center gap-4 flex-wrap">
      <Select
        v-model="branchId"
        :options="branchOptions"
        option-label="label"
        option-value="value"
        class="w-64"
      />

      <SelectButton
        v-model="view"
        :options="viewOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
      />

      <PlaybackBar class="flex-1 min-w-72" :playback="playback" />

      <Button label="Freeze & export" severity="secondary" outlined @click="exportOpen = true" />
    </div>

    <Message v-if="cacheHits" severity="success" :closable="false" class="shrink-0">
      Reusing {{ cacheHits }} materializations from cache — nothing recomputes on this switch.
    </Message>

    <div class="flex-1 min-h-0 flex gap-6">
      <Card class="flex-1 min-w-0" :pt="framePt">
        <template #content>
          <FlowCanvas
            v-if="view === 'canvas'"
            :session="playback.session.value"
            :branch-id="branchId"
            :layout="layout"
            :selected-asset-id="selectedAssetId"
            :phases="phases"
            @select="selectAsset"
            @expand="expand"
          />
          <NotebookView
            v-else
            :session="playback.session.value"
            :branch-id="branchId"
            :layout="layout"
            :selected-asset-id="selectedAssetId"
            @select="selectAsset"
            @expand="expand"
          />
        </template>
      </Card>

      <Card class="w-80 shrink-0" :pt="framePt">
        <template #content>
          <div class="h-full p-4">
            <RailroadTimeline
              v-model:lens="lens"
              :session="playback.session.value"
              :branch-id="branchId"
              :selected-asset-id="selectedAssetId"
              :selected-tx-id="selectedTxId"
              @select="selectCheckpoint"
            />
          </div>
        </template>
      </Card>
    </div>

    <Dialog
      v-model:visible="dialogOpen"
      :header="expandedVersion?.definition.name"
      maximizable
      modal
      :style="{ width: '72rem', maxWidth: '92vw' }"
    >
      <div v-if="expandedValue" class="p-2">
        <ArtifactView :value="expandedValue" />
      </div>
    </Dialog>

    <Dialog
      v-model:visible="exportOpen"
      header="Freeze this slice as an artifact"
      modal
      :style="{ width: '64rem', maxWidth: '92vw' }"
    >
      <ExportPreview :session="playback.session.value" :branch-id="branchId" />
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, Card, Dialog, Message, Select, SelectButton, type CardPassThroughOptions } from 'primevue'
import ArtifactView from '../components/ArtifactView.vue'
import ExportPreview from '../components/ExportPreview.vue'
import PlaybackBar from '../components/PlaybackBar.vue'
import FlowCanvas from './railroad/FlowCanvas.vue'
import NotebookView from './railroad/NotebookView.vue'
import RailroadTimeline from './railroad/RailroadTimeline.vue'
import { buildFlowLayout } from './railroad/flowLayout'
import { usePulses } from './railroad/usePulses'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'
import { cacheSkipSet, resolveSlice } from '../engine'
import type { ArtifactValue, AssetId, BranchId } from '../types'

const { session: sessionRef } = useWorkspace()
const session = sessionRef.value
const playback = usePlayback(session)

const branchId = ref<BranchId>(session.headBranchId)
const view = ref<'canvas' | 'notebook'>('canvas')
const lens = ref<'branch' | 'asset' | 'all'>('branch')
const selectedAssetId = ref<AssetId | null>(null)
const selectedTxId = ref<string | null>(null)
const expandedAssetId = ref<AssetId | null>(null)
const exportOpen = ref(false)
const cacheHits = ref(0)

const framePt: CardPassThroughOptions = {
  body: { class: 'h-full p-0 overflow-hidden' },
  content: { class: 'h-full overflow-hidden' },
}

const viewOptions = [
  { label: 'Canvas', value: 'canvas' },
  { label: 'Notebook', value: 'notebook' },
]

const branchOptions = computed(() =>
  Object.values(playback.session.value.branches).map((branch) => ({
    label: branch.name,
    value: branch.branchId,
  })),
)

const layout = computed(() => buildFlowLayout(session))

const { pulses } = usePulses(playback.session, branchId, playback.step)
const phases = computed(() =>
  Object.fromEntries(Object.entries(pulses.value).map(([assetId, pulse]) => [assetId, pulse.kind])),
)

const dialogOpen = computed({
  get: () => expandedAssetId.value !== null,
  set: (open: boolean) => {
    if (!open) expandedAssetId.value = null
  },
})

const expandedVersion = computed(() =>
  expandedAssetId.value
    ? (resolveSlice(playback.session.value, branchId.value)[expandedAssetId.value] ?? null)
    : null,
)

const expandedValue = computed<ArtifactValue | null>(() => {
  if (!expandedVersion.value) return null
  const values = Object.values(
    playback.session.value.materializations[expandedVersion.value.versionId]?.values ?? {},
  )
  return (values[0] as ArtifactValue | undefined) ?? null
})

const selectAsset = (assetId: AssetId): void => {
  selectedAssetId.value = assetId
  lens.value = 'asset'
}

const expand = (assetId: AssetId): void => {
  expandedAssetId.value = assetId
}

const selectCheckpoint = (txId: string): void => {
  selectedTxId.value = txId
  const tx = session.transactions.find((entry) => entry.txId === txId)
  if (tx) playback.seek(tx.step)
}

// Cached work emits no events, so a branch switch that is mostly cache would
// otherwise land on a still screen and read as broken.
let banner: ReturnType<typeof setTimeout> | null = null
watch(branchId, (next) => {
  cacheHits.value = cacheSkipSet(playback.session.value, next).length
  if (banner) clearTimeout(banner)
  banner = setTimeout(() => {
    cacheHits.value = 0
  }, 6000)
})

watch(playback.playing, (playing) => {
  if (playing) selectedTxId.value = null
})
</script>
