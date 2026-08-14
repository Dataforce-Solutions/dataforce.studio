<template>
  <div v-if="page" class="overflow-x-auto text-sm">
    <table class="w-full text-left border-collapse">
      <thead>
        <tr class="border-b border-surface-200 dark:border-surface-700">
          <th v-for="column in page.columns" :key="column" class="py-1 pr-4">
            {{ column }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, rowIndex) in page.rows" :key="rowIndex">
          <td v-for="column in page.columns" :key="column" class="py-1 pr-4">
            {{ row[column] ?? '—' }}
          </td>
        </tr>
      </tbody>
    </table>
    <p class="text-xs text-muted-color mt-2">
      Rows {{ page.offset + 1 }}–{{ page.offset + page.rows.length }} of {{ page.total_rows }}
    </p>
  </div>
  <div v-else-if="preview" class="text-sm flex flex-col gap-3">
    <template v-for="(block, index) in preview.blocks" :key="index">
      <div v-if="block.type === 'table'" class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b border-surface-200 dark:border-surface-700">
              <th v-for="column in stringList(block.columns)" :key="column" class="py-1 pr-4">
                {{ column }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in rows(block.rows)" :key="rowIndex">
              <td v-for="(value, valueIndex) in row" :key="valueIndex" class="py-1 pr-4">
                {{ value ?? '—' }}
              </td>
            </tr>
          </tbody>
        </table>
        <p class="text-xs text-muted-color mt-2">{{ block.total_rows ?? 0 }} rows</p>
      </div>
      <dl v-else-if="block.type === 'kv'" class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <template v-for="item in keyValues(block.items)" :key="item.key">
          <dt class="text-muted-color">{{ item.key }}</dt>
          <dd>{{ item.value }}</dd>
        </template>
      </dl>
      <img
        v-else-if="block.type === 'image' && typeof block.data_b64 === 'string'"
        :src="`data:${String(block.mime)};base64,${block.data_b64}`"
        alt="Output preview"
        class="max-w-full"
      />
      <p v-else-if="block.type === 'file'">{{ block.name }} · {{ block.size }} bytes</p>
      <pre v-else class="text-xs whitespace-pre-wrap font-mono">{{ block.text ?? block }}</pre>
    </template>
  </div>
  <p v-else class="text-sm text-muted-color">Not materialized in this branch.</p>
</template>

<script setup lang="ts">
import type { AssetPage, JsonValue, PreviewPayload } from '../api/types'

defineProps<{ preview: PreviewPayload | null; page?: AssetPage | null }>()

const stringList = (value: JsonValue | undefined): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

const rows = (value: JsonValue | undefined): JsonValue[][] =>
  Array.isArray(value) ? value.filter((item): item is JsonValue[] => Array.isArray(item)) : []

const keyValues = (value: JsonValue | undefined): { key: string; value: JsonValue }[] => {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || Array.isArray(item) || typeof item !== 'object') return []
    return typeof item.key === 'string' ? [{ key: item.key, value: item.value ?? null }] : []
  })
}
</script>
