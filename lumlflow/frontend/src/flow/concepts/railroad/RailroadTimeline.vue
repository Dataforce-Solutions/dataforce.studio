<template>
  <div class="h-full flex flex-col border-l border-surface-200 dark:border-surface-700">
    <div class="px-2 py-2 border-b border-surface-200 dark:border-surface-700 space-y-1.5">
      <div class="flex items-center gap-1.5">
        <span class="text-xs font-medium">railroad</span>
        <span class="text-[10px] text-muted-color">{{ entries.length }} events</span>
        <span class="ml-auto text-[10px] text-muted-color">collapses in place</span>
      </div>
      <div class="flex flex-wrap gap-1">
        <button
          v-for="option in lensOptions"
          :key="option.id"
          class="px-1.5 py-0.5 rounded border text-[11px] disabled:opacity-40"
          :class="
            option.id === lens
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-surface-300 dark:border-surface-600 text-muted-color'
          "
          :disabled="option.id === 'asset' && !selectedAssetId"
          :title="option.hint"
          @click="emit('update:lens', option.id)"
        >
          {{ option.label }}
        </button>
      </div>
      <select
        v-if="lens === 'author'"
        :value="agentFilter"
        class="w-full bg-transparent border border-surface-300 dark:border-surface-600 rounded px-1 py-0.5 text-[11px]"
        @change="emit('update:agentFilter', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="agent in agents" :key="agent.agentId" :value="agent.agentId">
          {{ agent.label }}
        </option>
      </select>
      <p v-if="lens === 'asset'" class="text-[10px] text-muted-color truncate">
        scoped to <span class="font-mono">{{ selectedAssetName }}</span> — {{ matchCount }} of
        {{ entries.length }} events touch it
      </p>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto px-2 py-1">
      <div v-for="row in rows" :key="row.key" class="relative pl-4">
        <span class="absolute left-1 top-0 bottom-0 w-px bg-surface-200 dark:bg-surface-700" />

        <button
          v-if="row.collapsed"
          class="relative w-full text-left my-0.5 py-1 pr-1 rounded hover:bg-surface-100 dark:hover:bg-surface-800"
          @click="toggleRun(row.key)"
        >
          <span
            class="absolute -left-4 top-1.5 w-2.5 h-2.5 rounded-full border border-surface-400 border-dashed"
          />
          <span class="flex flex-wrap items-center gap-1">
            <span class="text-[11px] text-muted-color">{{ row.entries.length }} collapsed</span>
            <span
              v-for="author in row.authors"
              :key="author"
              class="px-1 rounded text-[10px] text-white"
              :style="{ background: session.agents[author]?.color ?? '#64748b' }"
            >
              {{ session.agents[author]?.label ?? author }}
            </span>
            <span class="text-[10px] text-muted-color truncate">{{ row.assetSummary }}</span>
            <span
              v-if="row.metricDelta !== null"
              class="text-[10px]"
              :class="
                row.metricDelta >= 0
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-red-600 dark:text-red-400'
              "
            >
              {{ row.metricKey }} {{ row.metricDelta >= 0 ? '+' : ''
              }}{{ row.metricDelta.toFixed(3) }}
            </span>
          </span>
        </button>

        <template v-else>
          <div
            v-for="entry in row.entries"
            :key="entry.key"
            class="relative my-0.5 py-1 pr-1 rounded cursor-pointer hover:bg-surface-100 dark:hover:bg-surface-800"
            :class="entry.txId === selectedTxId ? 'bg-primary-50 dark:bg-primary-950/30' : ''"
            @mouseenter="hoveredKey = entry.key"
            @mouseleave="hoveredKey = null"
            @click="emit('select-checkpoint', entry.txId)"
          >
            <span
              class="absolute -left-4 top-1.5 w-2.5 h-2.5 rounded-full border"
              :class="
                entry.isCheckpoint
                  ? 'border-transparent'
                  : 'border-surface-400 bg-surface-0 dark:bg-surface-900'
              "
              :style="
                entry.isCheckpoint
                  ? { background: session.branches[entry.branchId]?.color ?? '#64748b' }
                  : undefined
              "
            />
            <div class="flex items-center gap-1">
              <span class="text-[10px] font-mono text-muted-color">{{ entry.step }}</span>
              <span
                class="px-1 rounded text-[10px] text-white"
                :style="{ background: session.agents[entry.author]?.color ?? '#64748b' }"
              >
                {{ session.agents[entry.author]?.label ?? entry.author }}
              </span>
              <span
                v-if="entry.isLiveHead"
                class="text-[10px] text-primary-600 dark:text-primary-400"
              >
                @ live head
              </span>
              <span v-else-if="entry.isBranchHead" class="text-[10px] text-muted-color">head</span>
            </div>
            <p class="text-[11px] leading-tight">{{ entry.intent }}</p>
            <div class="flex flex-wrap items-center gap-1 mt-0.5">
              <span
                v-if="entry.isFork"
                class="px-1 rounded text-[10px] border"
                :style="{ borderColor: session.branches[entry.branchId]?.color ?? '#64748b' }"
              >
                forked {{ session.branches[entry.branchId]?.name ?? entry.branchId }}
              </span>
              <span
                v-if="!entry.isCheckpoint"
                class="text-[10px] text-muted-color"
                title="Not settled — the branch was mid-flight here, so it is not a state worth returning to."
              >
                unsettled
              </span>
              <span v-if="entry.metricLabel" class="text-[10px] text-muted-color">
                {{ entry.metricLabel }}
              </span>
            </div>
            <CostChip
              v-if="hoveredKey === entry.key && entry.isCheckpoint"
              class="mt-1"
              :cost="jumpCost(entry)"
            />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import CostChip from '../../components/CostChip.vue'
import { branchLineage, preflightCost, versionsOf } from '../../engine'
import { sessionAtStep } from '../../composables/usePlayback'
import { lensOptions, type RailroadLens } from './lens'
import type { AgentId, AssetId, BranchId, FlowSession, PreflightCost, Transaction } from '../../types'

/**
 * History as a scoped query, not a second topology.
 *
 * Three rules hold this up: collapsed runs carry scent (authors, assets, metric
 * delta) instead of a bare count; the current checkpoint, every branch head and
 * the live head survive every lens; and a lens switch changes visibility only —
 * rows stay in step order, so the rail never reflows under the cursor.
 */
const props = defineProps<{
  /** Step-filtered session: the rail grows as playback advances. */
  session: FlowSession
  fullSession: FlowSession
  branchId: BranchId
  selectedAssetId: AssetId | null
  selectedTxId: string | null
  lens: RailroadLens
  agentFilter: AgentId
}>()

const emit = defineEmits<{
  'update:lens': [lens: RailroadLens]
  'update:agentFilter': [agentId: AgentId]
  'select-checkpoint': [txId: string]
}>()

const expandedRuns = ref<Set<string>>(new Set())
const hoveredKey = ref<string | null>(null)

const agents = computed(() => Object.values(props.session.agents))

const selectedAssetName = computed(() =>
  props.selectedAssetId ? nameOf(props.selectedAssetId) : '',
)

interface RailEntry {
  key: string
  txId: string
  step: number
  branchId: BranchId
  author: AgentId
  intent: string
  isCheckpoint: boolean
  isFork: boolean
  isBranchHead: boolean
  isLiveHead: boolean
  assetIds: AssetId[]
  assetNames: string[]
  metrics: Record<string, number> | null
  metricLabel: string
}

interface Row {
  key: string
  collapsed: boolean
  entries: RailEntry[]
  authors: AgentId[]
  assetSummary: string
  metricKey: string
  metricDelta: number | null
}

const lineage = computed(() => new Set(branchLineage(props.session, props.branchId)))

function nameOf(assetId: AssetId): string {
  const versions = versionsOf(props.fullSession, assetId)
  return versions[versions.length - 1]?.definition.name ?? assetId
}

function collectMetrics(tx: Transaction): Record<string, number> | null {
  const merged: Record<string, number> = {}
  for (const op of tx.ops) {
    if (op.op === 'materialize' && op.result.metrics) Object.assign(merged, op.result.metrics)
  }
  return Object.keys(merged).length ? merged : null
}

const entries = computed<RailEntry[]>(() => {
  // The rail covers this branch's lineage plus the forks cut off it — otherwise
  // "a second agent started elsewhere" is invisible from where you are standing.
  const relevant = props.session.transactions.filter(
    (tx) =>
      lineage.value.has(tx.branchId) ||
      tx.ops.some((op) => op.op === 'fork-branch' && lineage.value.has(op.fromBranchId)),
  )

  const lastIndexByBranch = new Map<BranchId, number>()
  relevant.forEach((tx, index) => lastIndexByBranch.set(tx.branchId, index))

  return relevant.map((tx, index) => {
    const assetIds = [
      ...new Set(tx.ops.flatMap((op) => ('assetId' in op ? [op.assetId] : []))),
    ]
    const metrics = collectMetrics(tx)
    const metricEntry = metrics ? Object.entries(metrics)[0] : null
    return {
      key: `${tx.txId}-${index}`,
      txId: tx.txId,
      step: tx.step,
      branchId: tx.branchId,
      author: tx.author,
      intent: tx.intent,
      isCheckpoint: tx.settled,
      isFork: tx.ops.some((op) => op.op === 'fork-branch'),
      isBranchHead: lastIndexByBranch.get(tx.branchId) === index,
      isLiveHead: index === relevant.length - 1,
      assetIds,
      assetNames: assetIds.map(nameOf),
      metrics,
      metricLabel: metricEntry ? `${metricEntry[0]} ${metricEntry[1].toFixed(3)}` : '',
    }
  })
})

function matchesLens(entry: RailEntry): boolean {
  switch (props.lens) {
    case 'asset':
      return props.selectedAssetId ? entry.assetIds.includes(props.selectedAssetId) : true
    case 'author':
      return entry.author === props.agentFilter
    case 'outcome':
      return entry.metrics !== null
    default:
      return true
  }
}

/** Rows kept visible in every lens — jj's `@`, plus every head so nobody is stranded. */
function isPinned(entry: RailEntry): boolean {
  return entry.txId === props.selectedTxId || entry.isBranchHead || entry.isLiveHead || entry.isFork
}

const matchCount = computed(() => entries.value.filter(matchesLens).length)

const rows = computed<Row[]>(() => {
  const out: Row[] = []
  let pending: RailEntry[] = []
  let previousMetrics: Record<string, number> | null = null

  const flush = (): void => {
    if (!pending.length) return
    const key = `run-${pending[0].key}`
    const names = [...new Set(pending.flatMap((entry) => entry.assetNames))]
    const runMetrics = pending.filter((entry) => entry.metrics).pop()?.metrics ?? null
    const metricKey = runMetrics ? Object.keys(runMetrics)[0] : ''
    out.push({
      key,
      collapsed: !expandedRuns.value.has(key),
      entries: pending,
      authors: [...new Set(pending.map((entry) => entry.author))],
      assetSummary: names.length
        ? `${names.slice(0, 2).join(', ')}${names.length > 2 ? ` +${names.length - 2}` : ''}`
        : 'no asset change',
      metricKey,
      metricDelta:
        runMetrics && previousMetrics && metricKey in previousMetrics
          ? runMetrics[metricKey] - previousMetrics[metricKey]
          : null,
    })
    pending = []
  }

  for (const entry of entries.value) {
    if (matchesLens(entry) || isPinned(entry)) {
      flush()
      out.push({
        key: entry.key,
        collapsed: false,
        entries: [entry],
        authors: [entry.author],
        assetSummary: '',
        metricKey: '',
        metricDelta: null,
      })
    } else {
      pending.push(entry)
    }
    if (entry.metrics) previousMetrics = entry.metrics
  }
  flush()
  return out
})

const toggleRun = (key: string): void => {
  const next = new Set(expandedRuns.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedRuns.value = next
}

/** What returning to this checkpoint would actually cost, before the click. */
const jumpCost = (entry: RailEntry): PreflightCost =>
  preflightCost(sessionAtStep(props.fullSession, entry.step), entry.branchId)
</script>
