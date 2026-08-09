<template>
  <div class="text-sm">
    <div v-if="value.type === 'frame'" class="overflow-x-auto">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-surface-200 dark:border-surface-700">
            <th
              v-for="(column, index) in value.columns"
              :key="column"
              class="py-1 pr-4 font-medium whitespace-nowrap"
            >
              {{ column }}
              <span class="block text-xs text-muted-color font-normal">{{ value.dtypes[index] }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, rowIndex) in value.rows"
            :key="rowIndex"
            class="border-b border-surface-100 dark:border-surface-800"
          >
            <td v-for="(cell, cellIndex) in row" :key="cellIndex" class="py-1 pr-4 whitespace-nowrap">
              {{ cell ?? '—' }}
            </td>
          </tr>
        </tbody>
      </table>
      <p class="text-xs text-muted-color mt-2">
        {{ value.rows.length }} of {{ value.totalRows.toLocaleString() }} rows
      </p>
    </div>

    <div v-else-if="value.type === 'plot'">
      <p class="text-xs text-muted-color mb-1">{{ value.title }}</p>
      <svg :viewBox="`0 0 ${plotWidth} ${plotHeight}`" class="w-full h-32">
        <line
          :x1="padding"
          :y1="plotHeight - padding"
          :x2="plotWidth - padding"
          :y2="plotHeight - padding"
          class="stroke-surface-300 dark:stroke-surface-600"
          stroke-width="1"
        />
        <template v-for="(series, seriesIndex) in value.series" :key="series.label">
          <polyline
            v-if="value.kind === 'line'"
            :points="polyline(series.points)"
            fill="none"
            :stroke="series.color ?? seriesColor(seriesIndex)"
            stroke-width="1.5"
          />
          <template v-else>
            <rect
              v-for="(point, pointIndex) in series.points"
              :key="pointIndex"
              :x="scaleX(point[0]) - barWidth(series.points.length) / 2"
              :y="scaleY(point[1])"
              :width="barWidth(series.points.length)"
              :height="Math.max(0, plotHeight - padding - scaleY(point[1]))"
              :fill="series.color ?? seriesColor(seriesIndex)"
              opacity="0.85"
            />
          </template>
        </template>
      </svg>
      <p class="text-xs text-muted-color">{{ value.xLabel }} · {{ value.yLabel }}</p>
    </div>

    <div v-else-if="value.type === 'note'" class="leading-relaxed whitespace-pre-wrap">
      {{ value.markdown }}
    </div>

    <dl v-else-if="value.type === 'model'" class="grid grid-cols-2 gap-x-4 gap-y-1">
      <dt class="text-muted-color">flavor</dt>
      <dd>{{ value.flavor }}</dd>
      <dt class="text-muted-color">parameters</dt>
      <dd>{{ value.paramCount.toLocaleString() }}</dd>
      <dt class="text-muted-color">size</dt>
      <dd>{{ (value.sizeBytes / 1024).toFixed(0) }} KB</dd>
      <dt class="text-muted-color">signature</dt>
      <dd class="font-mono text-xs">{{ value.signature }}</dd>
    </dl>

    <div v-else-if="value.type === 'experiment'">
      <p class="font-medium mb-1">{{ value.runName }}</p>
      <div class="flex flex-wrap gap-2 mb-2">
        <span
          v-for="(metric, name) in value.finalMetrics"
          :key="name"
          class="px-2 py-0.5 rounded bg-surface-100 dark:bg-surface-800 text-xs"
        >
          {{ name }} <span class="font-medium">{{ metric.toFixed(3) }}</span>
        </span>
      </div>
      <svg viewBox="0 0 240 80" class="w-full h-24">
        <polyline
          v-for="(series, index) in value.curves"
          :key="series.name"
          :points="curvePolyline(series.points)"
          fill="none"
          :stroke="seriesColor(index)"
          stroke-width="1.5"
        />
      </svg>
      <p class="text-xs text-muted-color font-mono">{{ value.checkpointRef }}</p>
    </div>

    <div v-else-if="value.type === 'eval'">
      <div class="flex flex-wrap gap-2 mb-2">
        <span
          v-for="(score, name) in value.scores"
          :key="name"
          class="px-2 py-0.5 rounded bg-surface-100 dark:bg-surface-800 text-xs"
        >
          {{ name }} <span class="font-medium">{{ score.toFixed(3) }}</span>
        </span>
      </div>
      <p class="text-xs text-muted-color mb-2">
        {{ value.sampleCount }} samples · {{ value.datasetRef }}
      </p>
      <div v-if="value.traces.length" class="space-y-1">
        <div
          v-for="trace in value.traces.slice(0, 4)"
          :key="trace.sampleId"
          class="border-l-2 pl-2 border-surface-200 dark:border-surface-700"
        >
          <p class="text-xs text-muted-color">{{ trace.prompt }}</p>
          <p class="text-xs">{{ trace.output }}</p>
          <p class="text-xs text-muted-color">score {{ trace.score }} · {{ trace.latencyMs }}ms</p>
        </div>
      </div>
    </div>

    <p v-else-if="value.type === 'metric'">
      <span class="text-muted-color">{{ value.name }}</span>
      <span class="ml-2 font-medium">{{ value.value.toFixed(4) }}</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ArtifactValue } from '../types'

const props = defineProps<{ value: ArtifactValue }>()

const plotWidth = 240
const plotHeight = 90
const padding = 8

const points = computed(() =>
  props.value.type === 'plot' ? props.value.series.flatMap((series) => series.points) : [],
)

const bounds = computed(() => {
  if (!points.value.length) return { minX: 0, maxX: 1, minY: 0, maxY: 1 }
  const xs = points.value.map((point) => point[0])
  const ys = points.value.map((point) => point[1])
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs) || 1,
    minY: Math.min(0, ...ys),
    maxY: Math.max(...ys) || 1,
  }
})

const scaleX = (x: number): number => {
  const { minX, maxX } = bounds.value
  const span = maxX - minX || 1
  return padding + ((x - minX) / span) * (plotWidth - padding * 2)
}

const scaleY = (y: number): number => {
  const { minY, maxY } = bounds.value
  const span = maxY - minY || 1
  return plotHeight - padding - ((y - minY) / span) * (plotHeight - padding * 2)
}

const polyline = (series: [number, number][]): string =>
  series.map(([x, y]) => `${scaleX(x)},${scaleY(y)}`).join(' ')

const barWidth = (count: number): number => Math.max(4, (plotWidth - padding * 2) / (count * 1.6))

const curvePolyline = (series: [number, number][]): string => {
  const ys = series.map((point) => point[1])
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const span = maxY - minY || 1
  return series
    .map(([, y], index) => {
      const px = 4 + (index / Math.max(1, series.length - 1)) * 232
      const py = 76 - ((y - minY) / span) * 68
      return `${px},${py}`
    })
    .join(' ')
}

const palette = ['#2563eb', '#0d9488', '#d97706', '#dc2626', '#7c3aed']
const seriesColor = (index: number): string => palette[index % palette.length]
</script>
