<template>
  <div
    v-if="skipped.length"
    class="px-3 py-1.5 rounded border border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-300 text-sm"
  >
    Reusing {{ skipped.length }} materialization{{ skipped.length === 1 ? '' : 's' }} from cache —
    <span class="font-mono text-xs">{{ preview }}</span>
    <span v-if="skipped.length > 3"> and {{ skipped.length - 3 }} more</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { cacheSkipSet, resolveSlice } from '../engine'
import type { BranchId, FlowSession } from '../types'

/**
 * Announced up front, the way ComfyUI broadcasts its skip set before a run.
 *
 * Cache sharing across branches is the headline architectural claim, and cached
 * work emits no events — so without this, switching to a mostly-cached branch
 * produces a silent, still screen that reads as broken.
 */
const props = defineProps<{ session: FlowSession; branchId: BranchId }>()

const skipped = computed(() => cacheSkipSet(props.session, props.branchId))

const preview = computed(() => {
  const slice = resolveSlice(props.session, props.branchId)
  return skipped.value
    .slice(0, 3)
    .map((assetId) => slice[assetId]?.definition.name ?? assetId)
    .join(', ')
})
</script>
