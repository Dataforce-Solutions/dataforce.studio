<template>
  <div class="text-sm min-w-0">
    <div class="overflow-auto" :class="bodyMaxClass(density)">
      <DataTable :value="rows" size="small">
        <Column v-for="(column, index) in preview.columns" :key="column" :field="String(index)">
          <template #header>
            <span class="leading-tight">
              <span class="font-medium whitespace-nowrap">{{ column }}</span>
              <span class="block text-xs text-muted-color font-normal">
                {{ preview.dtypes[index] }}
              </span>
            </span>
          </template>
          <template #body="{ data }">
            <span class="whitespace-nowrap tabular-nums">{{ data[index] ?? '—' }}</span>
          </template>
        </Column>
      </DataTable>
    </div>
    <p class="text-xs text-muted-color mt-2">
      {{ preview.rows.length }} of {{ preview.totalRows.toLocaleString() }} rows · preview
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Column, DataTable } from 'primevue'
import type { FramePreview } from '../model/types'
import { bodyMaxClass, type RenderDensity } from './shared'

const props = defineProps<{
  preview: FramePreview
  density?: RenderDensity
}>()

const rows = computed(() => props.preview.rows.map((row) => ({ ...row })))
</script>
