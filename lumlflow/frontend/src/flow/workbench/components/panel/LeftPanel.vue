<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-0 dark:bg-surface-900 min-w-0">
    <div
      class="flex flex-col gap-2.5 border-b border-surface-200 dark:border-surface-700 px-2 py-3"
    >
      <BranchIdentifier
        v-if="branch"
        :branch="branch"
        :worktree-branch="session.worktreeBranch"
        @open="emit('open-graph')"
      />
      <AgentTaskLine :paired="session.paired" :viewed-branch="viewedBranch" />
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto px-2 py-3 flex flex-col gap-5">
      <InventoryRows label="cells" :rows="cellRows" @select="emit('select-cell', $event)" />
      <InventoryRows
        label="experiments"
        :rows="experimentRows"
        @select="emit('select-cell', $event)"
      />
      <InventoryRows label="models" :rows="modelRows" @select="emit('select-cell', $event)" />
      <InventoryRows
        label="inputs"
        :rows="inputRows"
        caption="external inputs read outside the store — it cannot know when their bytes change"
        @select="emit('select-cell', $event)"
      />

      <section class="flex flex-col gap-2 min-w-0">
        <InventoryRows label="docs" :rows="docRows" @select="emit('select-cell', $event)" />
        <div class="flex flex-col gap-1.5 px-1.5">
          <p class="text-[11px] uppercase tracking-wide text-muted-color">intent timeline</p>
          <JournalFeed v-if="branchJournal.length" :entries="branchJournal" compact />
          <p v-else class="text-xs text-muted-color">no transactions on this branch yet</p>
        </div>
        <div class="flex flex-col gap-1 px-1.5">
          <Button
            label="Summarize this branch"
            size="small"
            severity="secondary"
            outlined
            @click="emit('summarize-branch')"
          >
            <template #icon>
              <Sparkles :size="13" />
            </template>
          </Button>
          <p class="text-[11px] text-muted-color">
            hands the branch payload to the agent; the agent writes the note cell
          </p>
        </div>
      </section>

      <PackagesPanel :env="env" />
    </div>

    <div class="border-t border-surface-200 dark:border-surface-700 px-2 py-3">
      <PanelSettings :settings="settings" @update="emit('update-settings', $event)" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button } from 'primevue'
import { Sparkles } from 'lucide-vue-next'
import { formatMetric } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type {
  BranchInfo,
  EnvState,
  FlowCell,
  FlowSettings,
  JournalEntry,
  WorkbenchSession,
} from '../../model/types'
import JournalFeed from '../session/JournalFeed.vue'
import AgentTaskLine from './AgentTaskLine.vue'
import BranchIdentifier from './BranchIdentifier.vue'
import InventoryRows, { type InventoryRow } from './InventoryRows.vue'
import PackagesPanel from './PackagesPanel.vue'
import PanelSettings from './PanelSettings.vue'

/**
 * The left panel, scoped to ONE viewed branch: identifier, current agent task,
 * the inventory lenses (all over the same cells — never a second store), and
 * the two settings that are real. Switching the viewed branch re-scopes all of
 * it.
 */
const props = defineProps<{
  branches: BranchInfo[]
  cells: FlowCell[]
  viewedBranch: string
  session: WorkbenchSession
  env: EnvState
  settings: FlowSettings
  journal: JournalEntry[]
}>()

const emit = defineEmits<{
  'open-graph': []
  'select-cell': [slug: string]
  'summarize-branch': []
  'update-settings': [settings: FlowSettings]
}>()

const branch = computed(() => props.branches.find((b) => b.name === props.viewedBranch))

const branchJournal = computed(() =>
  props.journal.filter((entry) => entry.branch === props.viewedBranch),
)

const cellRows = computed<InventoryRow[]>(() =>
  props.cells.map((cell) => ({
    key: cell.slug,
    slug: cell.slug,
    kind: primaryOutput(cell)?.kind ?? 'unknown',
    title: cell.slug,
    mono: true,
    status: cell.status,
    stale: cell.stale,
  })),
)

const experimentRows = computed<InventoryRow[]>(() =>
  props.cells.flatMap((cell) =>
    cell.outputs.flatMap((output) => {
      if (output.preview.type !== 'experiment') return []
      const { runName, mainMetric } = output.preview
      return [
        {
          key: `${cell.slug}.${output.name}`,
          slug: cell.slug,
          kind: 'experiment' as const,
          title: runName,
          detail: `${mainMetric.name} ${formatMetric(mainMetric.value)}`,
        },
      ]
    }),
  ),
)

const modelRows = computed<InventoryRow[]>(() =>
  props.cells.flatMap((cell) =>
    cell.outputs.flatMap((output) => {
      if (output.preview.type !== 'model') return []
      const { headlineMetric } = output.preview
      return [
        {
          key: `${cell.slug}.${output.name}`,
          slug: cell.slug,
          kind: 'model' as const,
          title: `${cell.slug}.${output.name}`,
          mono: true,
          detail: headlineMetric
            ? `${headlineMetric.name} ${formatMetric(headlineMetric.value)}`
            : undefined,
        },
      ]
    }),
  ),
)

/** Dataset outputs plus external-volatility cells — what "input" honestly means at runtime. */
const inputRows = computed<InventoryRow[]>(() => {
  const rows: InventoryRow[] = []
  for (const cell of props.cells) {
    const datasets = cell.outputs.filter((output) => output.preview.type === 'dataset')
    for (const output of datasets) {
      rows.push({
        key: `${cell.slug}.${output.name}`,
        slug: cell.slug,
        kind: 'dataset',
        title: `${cell.slug}.${output.name}`,
        mono: true,
        external: cell.externalInput,
      })
    }
    if (cell.externalInput && datasets.length === 0) {
      rows.push({
        key: cell.slug,
        slug: cell.slug,
        kind: primaryOutput(cell)?.kind ?? 'unknown',
        title: cell.slug,
        mono: true,
        external: true,
      })
    }
  }
  return rows
})

const docRows = computed<InventoryRow[]>(() =>
  props.cells
    .filter((cell) => cell.isNote)
    .map((cell) => ({
      key: cell.slug,
      slug: cell.slug,
      kind: 'note' as const,
      title: noteTitle(cell),
    })),
)

/** First markdown heading of the note, falling back to the slug. */
function noteTitle(cell: FlowCell): string {
  for (const output of cell.outputs) {
    if (output.preview.type !== 'note') continue
    const heading = output.preview.markdown
      .split('\n')
      .find((line) => line.trimStart().startsWith('#'))
    if (heading) return heading.replace(/^\s*#+\s*/, '')
  }
  return cell.slug
}
</script>
