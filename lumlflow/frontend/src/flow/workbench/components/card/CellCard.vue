<template>
  <article
    class="rounded-lg border bg-surface-0 dark:bg-surface-900 flex flex-col min-w-0"
    :class="[
      loudError
        ? 'border-red-300 dark:border-red-500/40'
        : 'border-surface-200 dark:border-surface-700',
      selected ? 'ring-2 ring-primary-500' : '',
    ]"
  >
    <header class="flex flex-col gap-1" :class="headerPad">
      <div class="flex items-start gap-2.5 min-w-0">
        <div class="flex items-center gap-x-2.5 gap-y-1 flex-wrap min-w-0 flex-1">
          <h3
            class="font-mono font-semibold"
            :class="density === 'canvas' ? 'text-base' : 'text-sm'"
          >
            {{ cell.slug }}
          </h3>
          <KindBadge v-if="primary" :kind="primary.kind" />
          <StatusChip :status="cell.status" :stale="cell.stale" />
          <MetaBadge v-if="cell.timing?.cached" variant="cached" />
          <MetaBadge v-if="cell.timing?.olderEnv" variant="older-env" />
          <MetaBadge v-if="cell.externalInput" variant="external" />
        </div>
        <div v-if="cell.timing" class="text-xs text-muted-color shrink-0 text-right pt-0.5">
          <template v-if="cell.status === 'running'">~</template
          >{{ formatCost(cell.timing.costSeconds)
          }}<template v-if="cell.timing.finishedAgo"> · {{ cell.timing.finishedAgo }}</template>
        </div>
      </div>
      <p class="text-xs text-muted-color">{{ cell.doc }}</p>
    </header>

    <div class="flex flex-col" :class="bodyPad">
      <div
        v-if="cell.flag"
        class="flex items-center gap-2 flex-wrap rounded-md border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 px-3 py-2"
      >
        <TriangleAlert :size="13" class="text-amber-600 dark:text-amber-400 shrink-0" />
        <span
          class="text-xs text-amber-800 dark:text-amber-200 flex-1 min-w-40"
          v-html="flagHtml"
        />
        <Button
          v-if="cell.flag.didYouMean"
          size="small"
          text
          severity="warn"
          label="apply suggestion"
          @click="applySuggestion"
        />
      </div>

      <ConflictMenu v-if="cell.conflict" @resolve="emit('resolve-conflict', $event)" />

      <div
        v-if="loudError"
        class="flex items-center gap-2 flex-wrap rounded-md border border-red-300 bg-red-50 dark:border-red-500/40 dark:bg-red-500/10 px-3 py-2"
      >
        <CircleAlert :size="14" class="text-red-600 dark:text-red-400 shrink-0" />
        <code class="font-mono text-xs text-red-800 dark:text-red-200 flex-1 min-w-40">
          {{ cell.error!.summary }}
        </code>
        <SendToAgentButton
          :cell="cell"
          :branch="branchName"
          gesture="fix"
          label="Fix this"
          severity="danger"
          @send-to-agent="emit('send-to-agent', $event)"
        />
      </div>

      <CellTabStrip :tabs="tabs" :selected="activeTab" @select="selectedTab = $event" />

      <div class="min-w-0">
        <template v-if="selectedOutput">
          <div
            v-if="cell.status === 'unmaterialized'"
            class="rounded-md border border-dashed border-surface-200 dark:border-surface-700 px-3 py-6 text-center text-xs text-muted-color"
          >
            not materialized on this branch — no baseline to preview; run computes it
          </div>
          <div v-else class="overflow-auto" :class="density === 'canvas' ? 'max-h-72' : 'max-h-80'">
            <RendererHost :preview="selectedOutput.preview" :density="density" />
          </div>
        </template>
        <CodeView
          v-else-if="activeTab === 'code'"
          :cell="cell"
          :density="density"
          @edit="emit('edit', $event)"
          @edit-params="emit('edit-params', $event)"
        />
        <ConsoleView v-else-if="activeTab === 'console'" :lines="cell.console ?? []" />
        <LogsView v-else-if="activeTab === 'logs'" :logs="cell.logs" :error="cell.error" />

        <!-- Demoted agent failure, notebook density only: code is the subject, so
             the summary may sit under it — quiet, no red wash. -->
        <p
          v-if="quietError && activeTab === 'code'"
          class="mt-2 border-l-2 border-red-300 dark:border-red-500/40 pl-2 font-mono text-[11px] text-muted-color"
        >
          {{ cell.error!.summary }}
        </p>

        <!-- Notebook accent: source open under the header, outputs below. -->
        <div
          v-if="density === 'notebook' && activeTab === 'code' && primary && !cell.isNote"
          class="mt-3 border-t border-surface-200 dark:border-surface-700 pt-2.5"
        >
          <div class="flex items-center gap-1.5 mb-1.5">
            <KindBadge :kind="primary.kind" icon-only :icon-size="12" />
            <span class="font-mono text-[11px] text-muted-color">{{ primary.name }}</span>
          </div>
          <div class="max-h-64 overflow-auto">
            <RendererHost :preview="primary.preview" density="notebook" />
          </div>
        </div>
      </div>
    </div>

    <footer
      class="flex items-center justify-between gap-3 flex-wrap border-t border-surface-100 dark:border-surface-800"
      :class="footerPad"
    >
      <ProvenanceLine
        :provenance="cell.provenance"
        :repaired-attempts="cell.error?.repairedAttempts"
        class="flex-1 min-w-0"
      />
      <CellOpRow
        :cell="cell"
        :density="density"
        :awaiters="awaiters"
        :preflight="preflight"
        :branch="branchName"
        @run="emit('run', $event)"
        @stop="emit('stop')"
        @expand="emit('expand')"
        @navigate="emit('navigate', $event)"
        @send-to-agent="emit('send-to-agent', $event)"
        @rename="emit('rename')"
        @delete="emit('delete')"
        @duplicate="emit('duplicate')"
      />
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button } from 'primevue'
import { CircleAlert, TriangleAlert } from 'lucide-vue-next'
import { formatCost } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type { FlowCell, ParamValue, Preflight } from '../../model/types'
import KindBadge from '../../ui/KindBadge.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import StatusChip from '../../ui/StatusChip.vue'
import RendererHost from '../../renderers/RendererHost.vue'
import SendToAgentButton from '../handoff/SendToAgentButton.vue'
import CellOpRow from './CellOpRow.vue'
import CellTabStrip, { type CellTab } from './CellTabStrip.vue'
import CodeView from './CodeView.vue'
import ConflictMenu from './ConflictMenu.vue'
import ConsoleView from './ConsoleView.vue'
import LogsView from './LogsView.vue'
import ProvenanceLine from './ProvenanceLine.vue'
import { inlineCodeHtml } from './inlineCode'

/**
 * One card per cell — the product's central component. A tab strip over the
 * assets the cell produced plus code and logs, at two densities: canvas leads
 * with outputs, notebook leads with code. Same card, different accent.
 */
const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
  selected?: boolean
  /** Demo-only: other branches awaiting the in-flight run (drives stop wording). */
  awaiters?: number
  /** Daemon-served run closure; defaults to this cell alone when absent. */
  preflight?: Preflight
  /** Branch context for handoff payloads; the design system defaults to main. */
  branch?: string
}>()

const emit = defineEmits<{
  expand: []
  run: [payload: { force: boolean }]
  stop: []
  rename: []
  delete: []
  duplicate: []
  navigate: [payload: { view: 'canvas' | 'notebook'; slug: string }]
  'send-to-agent': [payload: string]
  'resolve-conflict': [choice: 'overwrite' | 'fork']
  edit: [payload: { source: string }]
  'edit-params': [params: Record<string, ParamValue>]
}>()

const branchName = computed(() => props.branch ?? 'main')

const headerPad = computed(() => (props.density === 'canvas' ? 'px-4 pt-3' : 'px-3 pt-2.5'))
const bodyPad = computed(() =>
  props.density === 'canvas' ? 'px-4 pb-3 pt-2 gap-2.5' : 'px-3 pb-2.5 pt-1.5 gap-2',
)
const footerPad = computed(() => (props.density === 'canvas' ? 'px-4 py-2' : 'px-3 py-1.5'))

const primary = computed(() => primaryOutput(props.cell))

// --- errors: authorship decides the volume --------------------------------

const loudError = computed(() => props.cell.error?.author === 'user')
const quietError = computed(
  () => props.cell.error?.author === 'agent' && props.density === 'notebook',
)

// --- flag -----------------------------------------------------------------

const flagHtml = computed(() => {
  const flag = props.cell.flag
  if (!flag) return ''
  const suffix = flag.didYouMean ? ` — did you mean \`${flag.didYouMean}\`?` : ''
  return inlineCodeHtml(flag.message + suffix)
})

function applySuggestion(): void {
  const flag = props.cell.flag
  if (!flag?.didYouMean) return
  const broken = flag.message.match(/`([^`]+)`/)?.[1]
  const source = broken ? props.cell.source.split(broken).join(flag.didYouMean) : props.cell.source
  emit('edit', { source })
}

// --- tabs -----------------------------------------------------------------

const tabs = computed<CellTab[]>(() => {
  const list: CellTab[] = props.cell.outputs.map((output) => ({
    id: `out:${output.name}`,
    label: output.name,
    kind: output.kind,
  }))
  list.push({ id: 'code', label: 'code', icon: 'code' })
  if (props.cell.status === 'running')
    list.push({ id: 'console', label: 'console', icon: 'console', live: true })
  if (!props.cell.isNote) list.push({ id: 'logs', label: 'logs', icon: 'logs' })
  return list
})

function defaultTab(): string {
  if (props.cell.status === 'running') return 'console'
  const first = primary.value
  if (props.density === 'notebook' && first?.kind !== 'note') return 'code'
  return first ? `out:${first.name}` : 'code'
}

const selectedTab = ref(defaultTab())

// The live console takes focus the moment a run starts; a vanished tab
// (console after completion, a renamed output) falls back to the default.
watch(
  () => [props.cell.slug, props.cell.status, props.density] as const,
  ([, status], [, previousStatus]) => {
    if (status === 'running' && previousStatus !== 'running') selectedTab.value = 'console'
  },
)

const activeTab = computed(() =>
  tabs.value.some((tab) => tab.id === selectedTab.value) ? selectedTab.value : defaultTab(),
)

const selectedOutput = computed(() => {
  if (!activeTab.value.startsWith('out:')) return undefined
  const name = activeTab.value.slice(4)
  return props.cell.outputs.find((output) => output.name === name)
})
</script>
