<template>
  <!--
    Concept 1 — Canvas + drawn rail.

    Two surfaces: a stable flow of output-first asset cards, and a drawn rail
    beside it that is both the fork navigator and the time scrubber. There is no
    fork dropdown and no slider — selecting a point on the rail is how you move
    through both dimensions.
  -->
  <div class="h-[calc(100vh-190px)] flex gap-6">
    <Card class="w-[470px] shrink-0" :pt="framePt">
      <template #content>
        <div class="h-full flex flex-col">
          <div class="flex items-center gap-3 px-5 pt-5 pb-4">
            <span
              class="w-3 h-3 rounded-full shrink-0"
              :style="{ background: currentBranch?.color }"
            />
            <h3 class="text-lg font-medium truncate flex-1">{{ currentBranch?.name }}</h3>
            <Button
              text
              rounded
              severity="secondary"
              aria-label="Previous checkpoint"
              @click="stepBy(-1)"
            >
              <template #icon><ChevronUp :size="18" /></template>
            </Button>
            <Button
              text
              rounded
              severity="secondary"
              :aria-label="playback.playing.value ? 'Pause' : 'Play'"
              @click="playback.toggle()"
            >
              <template #icon>
                <Pause v-if="playback.playing.value" :size="18" />
                <Play v-else :size="18" />
              </template>
            </Button>
            <Button
              text
              rounded
              severity="secondary"
              aria-label="Next checkpoint"
              @click="stepBy(1)"
            >
              <template #icon><ChevronDown :size="18" /></template>
            </Button>
          </div>
          <RailroadTimeline
            class="flex-1 min-h-0"
            :session="session"
            :current-branch-id="branchId"
            :current-step="playback.step.value"
            @select="selectStop"
          />
        </div>
      </template>
    </Card>

    <div class="flex-1 min-w-0 flex flex-col gap-6">
      <div class="flex items-center gap-4">
        <SelectButton
          v-model="view"
          :options="viewOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
        />
        <span class="flex-1" />
        <Button label="Freeze & export" severity="secondary" outlined @click="exportOpen = true" />
      </div>

      <Message v-if="cacheHits" severity="success" :closable="false" class="shrink-0">
        Reusing {{ cacheHits }} materialization{{ cacheHits === 1 ? '' : 's' }} from cache —
        nothing recomputes here.
      </Message>

      <Card class="flex-1 min-h-0" :pt="framePt">
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
    </div>

    <Dialog
      v-model:visible="dialogOpen"
      :header="expandedVersion?.definition.name"
      maximizable
      modal
      :style="{ width: '72rem', maxWidth: '92vw' }"
    >
      <div v-if="expandedValue" class="p-2 flex flex-col gap-4">
        <a
          v-if="expandedRef"
          :href="expandedRef.href"
          class="inline-flex items-center gap-1.5 text-sm text-primary hover:underline self-start"
        >
          <ExternalLink :size="14" />
          {{ expandedRef.label }}
        </a>
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
import { Button, Card, Dialog, Message, SelectButton, type CardPassThroughOptions } from 'primevue'
import { ChevronDown, ChevronUp, ExternalLink, Pause, Play } from 'lucide-vue-next'
import ArtifactView from '../components/ArtifactView.vue'
import ExportPreview from '../components/ExportPreview.vue'
import FlowCanvas from './railroad/FlowCanvas.vue'
import NotebookView from './railroad/NotebookView.vue'
import RailroadTimeline from './railroad/RailroadTimeline.vue'
import { experimentRef, primaryArtifactValue } from './railroad/artifact'
import { buildFlowLayout } from './railroad/flowLayout'
import { usePulses } from './railroad/usePulses'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'
import { cacheSkipSet, resolveSlice } from '../engine'
import type { AssetId, BranchId } from '../types'

const { session: sessionRef } = useWorkspace()
const session = sessionRef.value
const playback = usePlayback(session)

const branchId = ref<BranchId>(session.headBranchId)
const view = ref<'canvas' | 'notebook'>('canvas')
const selectedAssetId = ref<AssetId | null>(null)
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

const currentBranch = computed(() => playback.session.value.branches[branchId.value])

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

const expandedValue = computed(() =>
  expandedVersion.value
    ? primaryArtifactValue(playback.session.value.materializations[expandedVersion.value.versionId])
    : null,
)

const expandedRef = computed(() =>
  expandedVersion.value ? experimentRef(session, expandedVersion.value, expandedValue.value) : null,
)

const selectAsset = (assetId: AssetId): void => {
  selectedAssetId.value = assetId
}

const expand = (assetId: AssetId): void => {
  expandedAssetId.value = assetId
}

const selectStop = (stopBranchId: BranchId, step: number): void => {
  branchId.value = stopBranchId
  playback.seek(step)
}

const eventSteps = [...new Set(session.transactions.map((tx) => tx.step))].sort((a, b) => a - b)

const stepBy = (direction: 1 | -1): void => {
  const current = playback.step.value
  const next =
    direction === 1
      ? eventSteps.find((step) => step > current)
      : [...eventSteps].reverse().find((step) => step < current)
  if (next !== undefined) playback.seek(next)
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
</script>
