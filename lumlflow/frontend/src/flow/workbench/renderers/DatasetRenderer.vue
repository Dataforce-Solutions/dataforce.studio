<template>
  <div class="flex flex-col gap-2.5 min-w-0 text-sm">
    <div class="flex flex-wrap gap-1.5">
      <span
        v-for="column in preview.schema"
        :key="column.name"
        class="font-mono text-[11px] px-1.5 py-0.5 rounded border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800"
      >
        {{ column.name }}<span class="text-muted-color">: {{ column.dtype }}</span>
      </span>
    </div>

    <div class="overflow-auto" :class="bodyMaxClass(density)">
      <DataTable :value="rows" size="small">
        <Column
          v-for="(column, index) in preview.schema"
          :key="column.name"
          :field="String(index)"
          :header="column.name"
        >
          <template #body="{ data }">
            <span class="whitespace-nowrap tabular-nums">{{ data[index] ?? '—' }}</span>
          </template>
        </Column>
      </DataTable>
    </div>

    <p class="text-xs text-muted-color">
      {{ preview.totalRows.toLocaleString() }} rows · {{ formatBytes(preview.sizeBytes) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Column, DataTable } from 'primevue'
import { formatBytes } from '../model/format'
import type { DatasetPreview } from '../model/types'
import { bodyMaxClass, type RenderDensity } from './shared'

const props = defineProps<{
  preview: DatasetPreview
  density?: RenderDensity
}>()

const rows = computed(() => props.preview.head.map((row) => ({ ...row })))
</script>
