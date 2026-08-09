<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border"
    :class="instant ? 'border-emerald-400 text-emerald-700 dark:text-emerald-400' : 'border-orange-400 text-orange-700 dark:text-orange-400'"
    :title="detail"
  >
    <span class="w-1.5 h-1.5 rounded-full" :class="instant ? 'bg-emerald-500' : 'bg-orange-500'" />
    {{ headline }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatCost } from '../engine'
import type { PreflightCost } from '../types'

/**
 * What a state change costs, shown *before* the click.
 *
 * "Materializes from cache, instant" versus "recomputes TrainGBM, ~2h" is the
 * difference between the warm-process promise being honest and being marketing.
 */
const props = defineProps<{ cost: PreflightCost }>()

const instant = computed(() => props.cost.recomputeAssetIds.length === 0)

const headline = computed(() =>
  instant.value
    ? `${props.cost.cachedAssetIds.length} from cache · instant`
    : `recomputes ${props.cost.recomputeAssetIds.length} · ~${formatCost(props.cost.totalSeconds)}`,
)

const detail = computed(() =>
  instant.value
    ? 'Every asset in this slice is already materialized.'
    : `${props.cost.cachedAssetIds.length} assets come from cache; ${props.cost.recomputeAssetIds.length} would recompute.`,
)
</script>
