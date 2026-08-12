<template>
  <div class="flex flex-col gap-3 min-w-0">
    <div v-if="preview.headlineMetric" class="flex flex-col gap-1">
      <span
        class="font-medium tabular-nums leading-none"
        :class="density === 'drawer' ? 'text-4xl' : 'text-3xl'"
      >
        {{ formatMetric(preview.headlineMetric.value) }}
      </span>
      <span class="inline-flex items-center gap-1 text-xs text-muted-color">
        <component
          :is="preview.headlineMetric.higherIsBetter ? ArrowUp : ArrowDown"
          v-tooltip.top="
            preview.headlineMetric.higherIsBetter ? 'higher is better' : 'lower is better'
          "
          :size="12"
        />
        <span>{{ preview.headlineMetric.name }}</span>
      </span>
    </div>

    <ConfigGrid :config="preview.config" />

    <p class="inline-flex items-center gap-1.5 text-xs text-muted-color">
      <Box :size="12" class="shrink-0" />
      <span>{{ preview.flavor }} · {{ formatBytes(preview.sizeBytes) }}</span>
    </p>

    <p v-if="preview.experimentRef" class="text-xs text-muted-color">
      see the full experiment — output
      <code class="font-mono">{{ preview.experimentRef }}</code>
    </p>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown, ArrowUp, Box } from 'lucide-vue-next'
import { formatBytes, formatMetric } from '../model/format'
import type { ModelPreview } from '../model/types'
import ConfigGrid from './ConfigGrid.vue'
import type { RenderDensity } from './shared'

defineProps<{
  preview: ModelPreview
  density?: RenderDensity
}>()
</script>
