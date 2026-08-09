<template>
  <section class="border border-surface-300 dark:border-surface-600 rounded p-3">
    <header class="flex items-center gap-2 mb-2">
      <h3 class="font-medium text-sm">Agents</h3>
      <span v-if="unseen.length" class="text-xs text-amber-600 dark:text-amber-400">
        {{ unseen.length }} unseen
      </span>
      <button
        class="ml-auto text-xs px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600"
        @click="emit('mark-seen')"
      >
        mark caught up
      </button>
    </header>

    <ul class="space-y-1 mb-3">
      <li v-for="agent in agents" :key="agent.agentId" class="flex items-center gap-2 text-xs">
        <span
          class="w-4 h-4 rounded-full flex items-center justify-center text-[8px] text-white shrink-0"
          :style="{ background: agent.color }"
        >
          {{ agent.label.slice(0, 1) }}
        </span>
        <span>{{ agent.label }}</span>
        <span class="text-muted-color truncate">
          {{ agent.activeBranchId ? branchName(agent.activeBranchId) : 'idle' }}
          <template v-if="agent.activeAssetId"> · {{ assetName(agent.activeAssetId) }}</template>
        </span>
        <span
          v-if="agent.activeBranchId && !branchIds.includes(agent.activeBranchId)"
          class="ml-auto text-muted-color shrink-0"
          title="This agent is working outside the variants you are comparing."
        >
          off-screen
        </span>
      </li>
    </ul>

    <!--
      The burst is several transactions on one step. Rendering the whole step at
      once, grouped by intent, is the only way it stays readable — one row per
      tick would silently drop most of it.
    -->
    <p class="text-xs text-muted-color mb-1">landing at step {{ step }}</p>
    <ul v-if="grouped.length" class="space-y-1">
      <li
        v-for="entry in grouped"
        :key="entry.key"
        class="flex items-start gap-2 text-xs"
        :class="branchIds.includes(entry.branchId) ? '' : 'opacity-60'"
      >
        <span
          class="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
          :style="{ background: session.agents[entry.author]?.color ?? '#94a3b8' }"
        />
        <span
          class="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
          :style="{ background: session.branches[entry.branchId]?.color ?? '#94a3b8' }"
        />
        <span>
          <span class="font-medium">{{ entry.intent }}</span>
          <span class="text-muted-color">
            · {{ branchName(entry.branchId) }}
            <template v-if="entry.count > 1"> · {{ entry.count }} transactions</template>
          </span>
        </span>
      </li>
    </ul>
    <p v-else class="text-xs text-muted-color">nothing landed on this step</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentId, AssetId, BranchId, FlowSession, Transaction } from '../../types'

const props = defineProps<{
  session: FlowSession
  branchIds: BranchId[]
  step: number
  unseen: Transaction[]
}>()

const emit = defineEmits<{ 'mark-seen': [] }>()

const agents = computed(() => Object.values(props.session.agents))

const branchName = (branchId: BranchId): string =>
  props.session.branches[branchId]?.name ?? branchId

const assetName = (assetId: AssetId): string =>
  props.session.assets[assetId]?.at(-1)?.definition.name ?? assetId

/** Grouped by intent, because a burst is one act of work split across ops. */
const grouped = computed(() => {
  const byKey = new Map<string, { key: string; branchId: BranchId; author: AgentId; intent: string; count: number }>()
  for (const tx of props.session.transactions.filter((item) => item.step === props.step)) {
    const key = `${tx.branchId}::${tx.intent}`
    const existing = byKey.get(key)
    if (existing) {
      existing.count += 1
      continue
    }
    byKey.set(key, { key, branchId: tx.branchId, author: tx.author, intent: tx.intent, count: 1 })
  }
  return [...byKey.values()]
})
</script>
