<template>
  <div class="h-full overflow-auto">
    <div class="mx-auto max-w-4xl flex flex-col gap-8 px-6 py-8">
      <AssetCard
        v-for="assetId in order"
        :key="assetId"
        :session="session"
        :version="slice[assetId]"
        :cause="causes[assetId] ?? null"
        :selected="assetId === selectedAssetId"
        :artifact-height="420"
        @click="emit('select', assetId)"
        @expand="emit('expand', assetId)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AssetCard from './AssetCard.vue'
import { readingOrder, type FlowLayout } from './flowLayout'
import { resolveSlice, unsyncedCause } from '../../engine'
import type { AssetId, BranchId, FlowSession, UnsyncedCause } from '../../types'

/**
 * The same cards in dependency order, one column, no edges.
 *
 * A DAG has no reading order, but a finding does — this is the view where a
 * slice is read rather than navigated, and it is what an exported artifact
 * looks like to whoever receives it.
 */
const props = defineProps<{
  session: FlowSession
  branchId: BranchId
  layout: FlowLayout
  selectedAssetId: AssetId | null
}>()

const emit = defineEmits<{ select: [AssetId]; expand: [AssetId] }>()

const slice = computed(() => resolveSlice(props.session, props.branchId))
const order = computed(() => readingOrder(props.session, props.branchId, props.layout))

const causes = computed(() => {
  const result: Record<AssetId, UnsyncedCause | null> = {}
  for (const assetId of order.value) {
    result[assetId] = unsyncedCause(props.session, props.branchId, assetId)
  }
  return result
})
</script>
