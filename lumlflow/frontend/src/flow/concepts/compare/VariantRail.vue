<template>
  <section class="border border-surface-300 dark:border-surface-600 rounded p-3">
    <div class="flex items-baseline gap-3 mb-2">
      <h3 class="font-medium text-sm">Variants under comparison</h3>
      <span class="text-xs text-muted-color">
        {{ modelValue.length }} of {{ MAX_VARIANTS }} · picking from
        {{ branchIds.length }} branches
      </span>
      <p class="ml-auto text-xs text-muted-color max-w-[34rem] text-right">
        Capped at {{ MAX_VARIANTS }}. Supervising more than about six parallel things is past what
        anyone actually does — selecting from twenty is a workflow, comparing twenty at once is a
        leaderboard.
      </p>
    </div>

    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="branchId in branchIds"
        :key="branchId"
        class="flex items-center gap-2 px-2 py-1 rounded border text-left text-sm transition-opacity"
        :class="chipClass(branchId)"
        :disabled="!isSelected(branchId) && atCap"
        :title="titleFor(branchId)"
        @click="toggle(branchId)"
      >
        <span
          class="w-2.5 h-2.5 rounded-full shrink-0"
          :style="{ background: session.branches[branchId]?.color }"
        />
        <span class="whitespace-nowrap">{{ session.branches[branchId]?.name ?? branchId }}</span>
        <span
          v-for="agent in agentsOn(branchId)"
          :key="agent.agentId"
          class="w-4 h-4 rounded-full flex items-center justify-center text-[8px] text-white shrink-0"
          :style="{ background: agent.color }"
          :title="`${agent.label} is working on ${nameOfAsset(agent.activeAssetId)}`"
        >
          {{ agent.label.slice(0, 1) }}
        </span>
        <span v-if="session.branches[branchId]?.sweepGroup" class="text-xs text-muted-color">
          sweep
        </span>
      </button>
    </div>

    <!-- Pre-flight before the click that changes state: adding a variant to the
         comparison materializes its slice, and the honest answer is almost always
         "instant, all from cache" — which is the claim worth making visible. -->
    <div class="flex flex-wrap items-center gap-2 mt-3 text-xs">
      <span class="text-muted-color">pre-flight</span>
      <span v-for="branchId in modelValue" :key="branchId" class="flex items-center gap-1">
        <span
          class="w-2 h-2 rounded-full"
          :style="{ background: session.branches[branchId]?.color }"
        />
        <CostChip :cost="costOf(branchId)" />
      </span>
    </div>

    <!--
      What is out of sync *inside* each variant, before any comparison happens.
      Kept separate from the fan graph deliberately: the graph answers "how do
      these differ from each other", this answers "how does each differ from
      where it forked" — and the sweep branches read `RawChurn changed` here
      without anyone touching them, which is the divergent pin, stated early.
    -->
    <ul v-if="staleness.length" class="mt-2 space-y-1 text-xs">
      <li v-for="row in staleness" :key="row.branchId" class="flex flex-wrap items-center gap-1.5">
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :style="{ background: session.branches[row.branchId]?.color }"
        />
        <span class="text-muted-color">{{ session.branches[row.branchId]?.name }}</span>
        <span v-for="item in row.items" :key="item.assetId" class="flex items-center gap-1">
          <span>{{ item.name }}</span>
          <StatusBadges :cause="item.cause" />
        </span>
        <span v-if="row.hidden" class="text-muted-color">+{{ row.hidden }} more</span>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CostChip from '../../components/CostChip.vue'
import StatusBadges from '../../components/StatusBadges.vue'
import { preflightCost, resolveSlice, unsyncedCause } from '../../engine'
import { MAX_VARIANTS, MIN_VARIANTS } from './useComparison'
import type { Agent, AssetId, BranchId, FlowSession, PreflightCost, UnsyncedCause } from '../../types'

const props = defineProps<{ session: FlowSession; modelValue: BranchId[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: BranchId[]] }>()

const branchIds = computed(() => Object.keys(props.session.branches))
const atCap = computed(() => props.modelValue.length >= MAX_VARIANTS)

const isSelected = (branchId: BranchId): boolean => props.modelValue.includes(branchId)

const toggle = (branchId: BranchId): void => {
  if (isSelected(branchId)) {
    if (props.modelValue.length <= MIN_VARIANTS) return
    emit(
      'update:modelValue',
      props.modelValue.filter((id) => id !== branchId),
    )
    return
  }
  if (atCap.value) return
  emit('update:modelValue', [...props.modelValue, branchId])
}

const chipClass = (branchId: BranchId): string => {
  if (isSelected(branchId)) return 'border-primary-500 bg-primary-50 dark:bg-primary-950/30'
  if (atCap.value) return 'border-surface-200 dark:border-surface-700 opacity-40 cursor-not-allowed'
  return 'border-surface-300 dark:border-surface-600 hover:border-surface-400'
}

const titleFor = (branchId: BranchId): string => {
  if (isSelected(branchId)) {
    return props.modelValue.length <= MIN_VARIANTS
      ? `A comparison needs at least ${MIN_VARIANTS} variants.`
      : 'Remove from the comparison'
  }
  return atCap.value ? `Comparison is capped at ${MAX_VARIANTS} variants.` : 'Add to the comparison'
}

const agentsOn = (branchId: BranchId): Agent[] =>
  Object.values(props.session.agents).filter((agent) => agent.activeBranchId === branchId)

const nameOfAsset = (assetId: AssetId | null): string => {
  if (!assetId) return 'nothing in particular'
  return props.session.assets[assetId]?.at(-1)?.definition.name ?? assetId
}

/** Only the selected variants are costed — `preflightCost` walks a whole slice. */
const costOf = (branchId: BranchId): PreflightCost => preflightCost(props.session, branchId)

const MAX_STALE_SHOWN = 4

interface StaleRow {
  branchId: BranchId
  items: { assetId: AssetId; name: string; cause: UnsyncedCause }[]
  hidden: number
}

/** Edited assets lead; the rematerialized cascade below them is the long tail. */
const staleness = computed<StaleRow[]>(() =>
  props.modelValue
    .map((branchId) => {
      const slice = resolveSlice(props.session, branchId)
      const all = Object.values(slice)
        .map((version) => ({
          assetId: version.assetId,
          name: version.definition.name,
          cause: unsyncedCause(props.session, branchId, version.assetId),
        }))
        .filter((item): item is StaleRow['items'][number] => item.cause !== null)
        .sort((a, b) =>
          a.cause === b.cause ? 0 : a.cause === 'parent-rematerialized' ? 1 : -1,
        )
      return {
        branchId,
        items: all.slice(0, MAX_STALE_SHOWN),
        hidden: Math.max(0, all.length - MAX_STALE_SHOWN),
      }
    })
    .filter((row) => row.items.length),
)
</script>
