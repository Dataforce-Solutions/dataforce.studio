<template>
  <div class="flex flex-col gap-1.5 py-1">
    <div class="flex items-baseline gap-2.5">
      <span
        class="font-medium tabular-nums leading-none"
        :class="density === 'drawer' ? 'text-4xl' : 'text-3xl'"
      >
        {{ formatMetric(preview.value) }}
      </span>
      <span
        v-if="preview.delta !== undefined"
        class="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded border"
        :class="deltaClasses"
      >
        {{ deltaLabel }}
      </span>
    </div>
    <span class="inline-flex items-center gap-1 text-xs text-muted-color">
      <component
        :is="preview.higherIsBetter ? ArrowUp : ArrowDown"
        v-tooltip.top="preview.higherIsBetter ? 'higher is better' : 'lower is better'"
        :size="12"
      />
      <span>{{ preview.name }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown, ArrowUp } from 'lucide-vue-next'
import { formatMetric } from '../model/format'
import type { MetricPreview } from '../model/types'
import type { RenderDensity } from './shared'

const props = defineProps<{
  preview: MetricPreview
  density?: RenderDensity
}>()

const deltaLabel = computed(() => {
  const delta = props.preview.delta ?? 0
  return `${delta > 0 ? '+' : ''}${formatMetric(delta)}`
})

// Colored by whether the delta is an improvement, not by its sign.
const deltaClasses = computed(() => {
  const delta = props.preview.delta ?? 0
  if (delta === 0) {
    return 'border-surface-300 text-surface-600 bg-surface-50 dark:border-surface-600 dark:text-surface-300 dark:bg-surface-800'
  }
  const improved = props.preview.higherIsBetter ? delta > 0 : delta < 0
  return improved
    ? 'border-emerald-200 text-emerald-700 bg-emerald-50 dark:border-emerald-500/30 dark:text-emerald-300 dark:bg-emerald-500/10'
    : 'border-red-200 text-red-700 bg-red-50 dark:border-red-500/30 dark:text-red-300 dark:bg-red-500/10'
})
</script>
