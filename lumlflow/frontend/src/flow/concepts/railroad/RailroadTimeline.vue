<template>
  <div class="h-full flex flex-col gap-4">
    <Select
      v-model="lens"
      :options="lensOptions"
      option-label="label"
      option-value="value"
      size="small"
      fluid
    />

    <div class="flex-1 overflow-auto flex flex-col gap-1">
      <template v-for="entry in entries" :key="entry.key">
        <button
          v-if="entry.kind === 'collapsed'"
          class="text-left text-sm text-muted-color px-3 py-2 rounded hover:bg-surface-100 dark:hover:bg-surface-800"
          @click="expanded.add(entry.key)"
        >
          {{ entry.count }} more · {{ entry.authors.join(', ') }}
          <span v-if="entry.assets">· {{ entry.assets }}</span>
        </button>

        <button
          v-else
          class="text-left px-3 py-2 rounded flex gap-3 items-start"
          :class="
            entry.tx.txId === selectedTxId
              ? 'bg-primary-50 dark:bg-primary-950/40'
              : 'hover:bg-surface-100 dark:hover:bg-surface-800'
          "
          @click="emit('select', entry.tx.txId)"
        >
          <span
            class="mt-1.5 w-2 h-2 rounded-full shrink-0"
            :style="{ background: session.agents[entry.tx.author]?.color }"
          />
          <span class="min-w-0 flex-1">
            <span class="block text-sm truncate">{{ entry.tx.intent }}</span>
            <span class="block text-xs text-muted-color">
              step {{ entry.tx.step }} · {{ session.branches[entry.tx.branchId]?.name }}
            </span>
          </span>
          <Tag v-if="entry.isHead" value="head" severity="contrast" />
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { Select, Tag } from 'primevue'
import type { AssetId, BranchId, FlowSession, Transaction } from '../../types'

/**
 * History as a scoped query, not a second topology.
 *
 * Every attempt to draw the full asset-version lattice ends in a hairball, so
 * the second dimension is a filtered list beside a stable picture. The lens
 * only changes what is visible — entries never reorder, because a timeline that
 * reshuffles on selection is the same disease the stable canvas exists to cure.
 */
const props = defineProps<{
  session: FlowSession
  branchId: BranchId
  selectedAssetId: AssetId | null
  selectedTxId: string | null
}>()

const emit = defineEmits<{ select: [string] }>()

const lens = defineModel<'branch' | 'asset' | 'all'>('lens', { default: 'branch' })
const expanded = reactive(new Set<string>())

const lensOptions = computed(() => [
  { label: 'This branch', value: 'branch' },
  {
    label: props.selectedAssetId
      ? `Changes to ${assetName(props.selectedAssetId)}`
      : 'Changes to selected asset',
    value: 'asset',
  },
  { label: 'Everything', value: 'all' },
])

function assetName(assetId: AssetId): string {
  return props.session.assets[assetId]?.at(-1)?.definition.name ?? assetId
}

function lineage(branchId: BranchId): Set<BranchId> {
  const chain = new Set<BranchId>()
  let current: BranchId | null = branchId
  while (current) {
    chain.add(current)
    current = props.session.branches[current]?.parentBranchId ?? null
  }
  return chain
}

const kept = computed<Transaction[]>(() => {
  const all = props.session.transactions
  if (lens.value === 'all') return all
  if (lens.value === 'asset') {
    if (!props.selectedAssetId) return all
    return all.filter((tx) =>
      tx.ops.some((op) => 'assetId' in op && op.assetId === props.selectedAssetId),
    )
  }
  const chain = lineage(props.branchId)
  return all.filter((tx) => chain.has(tx.branchId))
})

/** Runs of routine transactions fold into one row carrying who and what — a
 *  bare hidden count is not scent, and nobody expands a number. */
const entries = computed(() => {
  const headTxId = kept.value.at(-1)?.txId
  const rows: (
    | { kind: 'tx'; key: string; tx: Transaction; isHead: boolean }
    | { kind: 'collapsed'; key: string; count: number; authors: string[]; assets: string }
  )[] = []

  let run: Transaction[] = []
  const flush = (): void => {
    if (!run.length) return
    const key = `collapsed-${run[0].txId}`
    if (run.length < 3 || expanded.has(key)) {
      rows.push(
        ...run.map((tx) => ({ kind: 'tx' as const, key: tx.txId, tx, isHead: tx.txId === headTxId })),
      )
    } else {
      const authors = [
        ...new Set(run.map((tx) => props.session.agents[tx.author]?.label ?? tx.author)),
      ]
      const assets = [
        ...new Set(
          run.flatMap((tx) => tx.ops.flatMap((op) => ('assetId' in op ? [assetName(op.assetId)] : []))),
        ),
      ]
      rows.push({
        kind: 'collapsed',
        key,
        count: run.length,
        authors,
        assets: assets.slice(0, 2).join(', '),
      })
    }
    run = []
  }

  for (const tx of kept.value) {
    // Settled states, forks and the head are the only places worth returning to.
    const isLandmark =
      tx.settled ||
      tx.txId === headTxId ||
      tx.ops.some((op) => op.op === 'fork-branch' || op.op === 'rename-asset')
    if (isLandmark) {
      flush()
      rows.push({ kind: 'tx', key: tx.txId, tx, isHead: tx.txId === headTxId })
    } else {
      run.push(tx)
    }
  }
  flush()
  return rows
})
</script>
