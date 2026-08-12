<template>
  <Dialog v-model:visible="visible" :pt="dialogPt" position="right" :draggable="false">
    <template #header>
      <div class="flex items-center gap-2">
        <component :is="headerIcon" :size="20" color="var(--p-primary-color)" />
        <h3 class="font-mono">{{ cell.slug }}</h3>
      </div>
    </template>
    <template #closeicon>
      <X :size="14" />
    </template>

    <div class="flex flex-col gap-5 pb-2">
      <CellTabStrip :tabs="outputTabs" :selected="activeTab" @select="selectedTab = $event" />

      <div
        class="rounded-md border border-surface-200 dark:border-surface-700 p-3 overflow-auto max-h-[26rem]"
      >
        <RendererHost v-if="selectedOutput" :preview="selectedOutput.preview" density="drawer" />
      </div>

      <div v-if="pagedTotalRows !== null" class="flex flex-col gap-1.5">
        <div class="flex items-center gap-2 flex-wrap">
          <Button text rounded severity="secondary" size="small" aria-label="previous page">
            <template #icon><ChevronLeft :size="14" /></template>
          </Button>
          <span class="text-xs text-muted-color">
            rows 1–{{ Math.min(50, pagedTotalRows).toLocaleString('en-US') }} of
            {{ pagedTotalRows.toLocaleString('en-US') }} · pages served by the kernel
          </span>
          <Button text rounded severity="secondary" size="small" aria-label="next page">
            <template #icon><ChevronRight :size="14" /></template>
          </Button>
        </div>
        <p
          v-if="!kernelStarted"
          class="flex items-center gap-1.5 text-[11px] text-sky-700 dark:text-sky-300"
        >
          <Info :size="12" class="shrink-0" />
          expanding starts the kernel
        </p>
      </div>

      <div v-if="configEntries.length" class="flex flex-col gap-1.5">
        <p class="text-[11px] uppercase tracking-wide text-muted-color">config · params</p>
        <div class="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-1 text-xs">
          <template v-for="[key, value] in configEntries" :key="key">
            <span class="font-mono text-muted-color">{{ key }}</span>
            <span class="font-mono">{{ value }}</span>
          </template>
        </div>
      </div>

      <a
        v-if="hasExperiment"
        href="#"
        class="inline-flex items-center gap-1.5 text-sm text-primary hover:underline self-start"
      >
        <ExternalLink :size="14" />
        see the full experiment → tracker
      </a>

      <div class="flex flex-col gap-1.5">
        <p class="text-[11px] uppercase tracking-wide text-muted-color">download</p>
        <div class="flex items-center gap-2.5 flex-wrap">
          <Button size="small" outlined :label="downloadLabel">
            <template #icon><Download :size="13" /></template>
          </Button>
          <p v-if="selectedOutput?.neverPersisted" class="text-[11px] text-muted-color">
            the value was never persisted — downloading first runs the closure
          </p>
        </div>
      </div>

      <div class="flex flex-col gap-1.5">
        <p class="text-[11px] uppercase tracking-wide text-muted-color">materialization logs</p>
        <pre
          v-if="cell.logs"
          class="font-mono text-xs leading-relaxed rounded-md border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 p-3 overflow-auto max-h-48 whitespace-pre-wrap"
          >{{ cell.logs.trimEnd() }}</pre
        >
        <p v-else class="text-xs text-muted-color">no logs recorded for this materialization</p>
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, Dialog, type DialogPassThroughOptions } from 'primevue'
import { ChevronLeft, ChevronRight, Download, ExternalLink, Info, X } from 'lucide-vue-next'
import { formatCost } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type { FlowCell, ParamValue } from '../../model/types'
import { KIND_ICONS } from '../../ui/kinds'
import RendererHost from '../../renderers/RendererHost.vue'
import CellTabStrip, { type CellTab } from './CellTabStrip.vue'

/**
 * The card expanded into a full-height right drawer: the selected output at
 * drawer density, config, the kernel-paged value for frames, links out to the
 * tracker, and the download row. Expand is the first gesture that may start a
 * kernel — the drawer says so before it does.
 */
const props = defineProps<{
  cell: FlowCell
  kernelStarted?: boolean
  /** Cost carried by materialize-and-download when the bytes were never persisted. */
  materializeSeconds?: number
}>()

const visible = defineModel<boolean>('visible', { default: false })

// Modeled on RightFullHeightDialog, widened to carry a full renderer.
const dialogPt: DialogPassThroughOptions = {
  mask: { class: 'pt-22 pb-8 px-4' },
  root: { class: 'w-full max-w-[44rem] h-full max-h-full! m-0!' },
  header: { class: 'text-lg font-medium uppercase' },
}

const primary = computed(() => primaryOutput(props.cell))

const headerIcon = computed(() => KIND_ICONS[primary.value?.kind ?? 'unknown'])

const outputTabs = computed<CellTab[]>(() =>
  props.cell.outputs.map((output) => ({
    id: `out:${output.name}`,
    label: output.name,
    kind: output.kind,
  })),
)

const selectedTab = ref('')

watch(
  () => [props.cell.slug, visible.value] as const,
  () => {
    selectedTab.value = primary.value ? `out:${primary.value.name}` : ''
  },
  { immediate: true },
)

const activeTab = computed(() =>
  outputTabs.value.some((tab) => tab.id === selectedTab.value)
    ? selectedTab.value
    : (outputTabs.value[0]?.id ?? ''),
)

const selectedOutput = computed(() =>
  props.cell.outputs.find((output) => `out:${output.name}` === activeTab.value),
)

const pagedTotalRows = computed<number | null>(() => {
  const preview = selectedOutput.value?.preview
  if (preview?.type === 'frame' || preview?.type === 'dataset') return preview.totalRows
  return null
})

const configEntries = computed<[string, string][]>(() => {
  const merged = new Map<string, ParamValue>()
  const preview = selectedOutput.value?.preview
  if (preview?.type === 'model' || preview?.type === 'experiment') {
    for (const [key, value] of Object.entries(preview.config)) merged.set(key, value)
  }
  // Declared params win over recorded config on a key collision.
  for (const [key, value] of Object.entries(props.cell.params)) merged.set(key, value)
  return [...merged.entries()].map(([key, value]) => [
    key,
    typeof value === 'string' ? value : JSON.stringify(value),
  ])
})

const hasExperiment = computed(() =>
  props.cell.outputs.some(
    (output) => output.kind === 'experiment' || output.preview.type === 'experiment',
  ),
)

const downloadLabel = computed(() => {
  if (selectedOutput.value?.neverPersisted) {
    const seconds = props.materializeSeconds ?? props.cell.timing?.costSeconds ?? 10
    return `materialize and download · ~${formatCost(seconds)}`
  }
  return 'download'
})
</script>
