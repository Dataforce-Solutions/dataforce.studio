<template>
  <div class="space-y-1.5">
    <div class="flex items-center gap-2 overflow-x-auto pb-1">
      <span class="text-xs text-muted-color shrink-0">variant</span>
      <div
        v-for="branch in branches"
        :key="branch.branchId"
        class="shrink-0 flex items-center gap-1.5 px-2 py-1 rounded border text-xs cursor-pointer"
        :class="
          branch.branchId === branchId
            ? 'border-primary-500'
            : 'border-surface-300 dark:border-surface-600'
        "
        :title="branch.costTitle"
        @click="emit('select', branch.branchId)"
      >
        <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: branch.color }" />
        <span :class="branch.archived ? 'text-muted-color line-through' : ''">{{ branch.name }}</span>
        <span
          v-for="agent in branch.agents"
          :key="agent.agentId"
          class="w-3.5 h-3.5 rounded-full"
          :style="{ background: agent.color }"
          :title="`${agent.label} is working on this branch`"
        />
        <span
          v-if="branch.updateCount"
          class="px-1 rounded text-[10px] border border-amber-400 text-amber-700 dark:text-amber-400"
          title="Upstream versions this branch pinned away from that would actually change what it reads."
        >
          {{ branch.updateCount }} upstream
        </span>
        <label class="flex items-center gap-1 text-[10px] text-muted-color" @click.stop>
          <input
            type="checkbox"
            :checked="compareIds.includes(branch.branchId)"
            @change="emit('toggle-compare', branch.branchId)"
          />
          cmp
        </label>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <CostChip :cost="selectedCost" />
      <span class="text-[11px] text-muted-color">
        switching to {{ selectedName }} — cost shown before the click
      </span>
    </div>

    <div
      v-for="update in updates"
      :key="update.assetId"
      class="flex flex-wrap items-center gap-2 px-2 py-1.5 rounded border border-amber-400 bg-amber-50 dark:bg-amber-950/30 text-[11px]"
    >
      <span>
        <span class="font-mono">{{ update.name }}</span>
        moved to
        <span class="font-mono">{{ update.tag }}</span>
        upstream — this variant pinned <span class="font-mono">{{ update.pinnedTag }}</span> at fork
      </span>
      <CostChip :cost="update.cost" />
      <button class="px-1.5 py-0.5 rounded border border-surface-400 dark:border-surface-500">
        accept
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CostChip from '../../components/CostChip.vue'
import { downstreamOf, formatCost, preflightCost, resolveSlice, upstreamUpdates, versionsOf } from '../../engine'
import type { Agent, BranchId, FlowSession, PreflightCost } from '../../types'

/**
 * Variant selection, with the two things a branch list normally hides: what
 * switching costs, and what the branch has pinned away from.
 *
 * `upstreamUpdates` has already run early cutoff, so a row here means a content
 * hash this branch reads would genuinely move — and the row prices the accept
 * rather than showing a count nobody can act on.
 */
const props = defineProps<{
  session: FlowSession
  branchId: BranchId
  compareIds: BranchId[]
}>()

const emit = defineEmits<{ select: [branchId: BranchId]; 'toggle-compare': [branchId: BranchId] }>()

const agentsByBranch = computed(() => {
  const result: Record<BranchId, Agent[]> = {}
  for (const agent of Object.values(props.session.agents)) {
    if (!agent.activeBranchId) continue
    result[agent.activeBranchId] = result[agent.activeBranchId] ?? []
    result[agent.activeBranchId].push(agent)
  }
  return result
})

const branches = computed(() =>
  Object.values(props.session.branches).map((branch) => {
    const cost = preflightCost(props.session, branch.branchId)
    return {
      branchId: branch.branchId,
      name: branch.name,
      color: branch.color,
      archived: branch.archived,
      agents: agentsByBranch.value[branch.branchId] ?? [],
      updateCount: upstreamUpdates(props.session, branch.branchId).length,
      costTitle: cost.recomputeAssetIds.length
        ? `recomputes ${cost.recomputeAssetIds.length} · ~${formatCost(cost.totalSeconds)}`
        : 'instant from cache',
    }
  }),
)

const selectedCost = computed(() => preflightCost(props.session, props.branchId))
const selectedName = computed(
  () => props.session.branches[props.branchId]?.name ?? props.branchId,
)

const updates = computed(() => {
  const branch = props.session.branches[props.branchId]
  const slice = resolveSlice(props.session, props.branchId)
  return upstreamUpdates(props.session, props.branchId).map((update) => {
    const affected = [update.assetId, ...downstreamOf(props.session, props.branchId, update.assetId)]
    const affectedSet = new Set(affected)
    const cost: PreflightCost = {
      cachedAssetIds: Object.keys(slice).filter((assetId) => !affectedSet.has(assetId)),
      recomputeAssetIds: affected,
      totalSeconds: affected.reduce(
        (sum, assetId) =>
          sum + (props.session.materializations[slice[assetId]?.versionId]?.costSeconds ?? 0),
        0,
      ),
    }
    const versions = versionsOf(props.session, update.assetId)
    return {
      assetId: update.assetId,
      name: versions[versions.length - 1]?.definition.name ?? update.assetId,
      tag: tagOf(update.latestVersionId),
      pinnedTag: tagOf(branch?.pins[update.assetId] ?? ''),
      cost,
    }
  })
})

function tagOf(versionId: string): string {
  return versionId.split('@')[1] ?? versionId
}
</script>
