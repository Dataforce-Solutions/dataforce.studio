<template>
  <div class="flex flex-col gap-4">
    <IntegrityWarningBar
      v-for="warning in fixture.warnings"
      :key="warning.kind + warning.message"
      :warning="warning"
    />

    <div class="overflow-x-auto">
      <div
        class="grid items-baseline gap-x-6"
        :style="{ gridTemplateColumns: `max-content repeat(${columns.length}, minmax(9rem, 1fr))` }"
      >
        <span />
        <div v-for="column in columns" :key="column.branch" class="flex flex-col gap-1.5 pb-3">
          <div class="flex flex-wrap items-center gap-2">
            <BranchTag :name="column.branch" />
            <MetaBadge v-if="column.settled" variant="settled" />
          </div>
          <div class="flex items-baseline gap-1.5">
            <span class="text-2xl font-semibold tabular-nums">
              {{ formatMetric(column.headlineMetric.value) }}
            </span>
            <span class="text-xs text-muted-color">{{ column.headlineMetric.name }}</span>
          </div>
        </div>

        <template v-for="score in scoreNames" :key="score">
          <span
            class="border-t border-surface-200 py-1.5 pr-2 text-xs text-muted-color dark:border-surface-700"
          >
            {{ score }}
          </span>
          <span
            v-for="column in columns"
            :key="column.branch"
            class="border-t border-surface-200 py-1.5 text-sm tabular-nums dark:border-surface-700"
            :class="
              isBest(score, column) ? 'font-medium text-emerald-600 dark:text-emerald-400' : ''
            "
          >
            <template v-if="column.scores[score] !== undefined">
              {{ formatMetric(column.scores[score]) }}
              <span v-if="isBest(score, column)" class="text-[10px] align-middle">●</span>
            </template>
            <span v-else class="text-muted-color">—</span>
          </span>
        </template>
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <p class="text-xs text-muted-color">
        <span class="font-mono">{{ fixture.sharedMetric }}</span> over training — one line per
        branch
      </p>
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        class="w-full max-w-2xl"
        role="img"
        :aria-label="`${fixture.sharedMetric} curves for ${columns.length} branches`"
      >
        <line
          v-for="tick in yTicks"
          :key="tick.y"
          :x1="PAD.left"
          :x2="W - PAD.right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="currentColor"
          stroke-width="1"
          class="text-surface-200 dark:text-surface-700"
        />
        <text
          v-for="tick in yTicks"
          :key="'label' + tick.y"
          :x="PAD.left - 6"
          :y="tick.y + 3"
          text-anchor="end"
          font-size="9"
          class="fill-current text-muted-color"
        >
          {{ tick.label }}
        </text>
        <text :x="PAD.left" :y="H - 6" font-size="9" class="fill-current text-muted-color">
          {{ formatMetric(xMin) }}
        </text>
        <text
          :x="W - PAD.right"
          :y="H - 6"
          text-anchor="end"
          font-size="9"
          class="fill-current text-muted-color"
        >
          {{ formatMetric(xMax) }} epochs
        </text>
        <polyline
          v-for="(column, index) in columns"
          :key="column.branch"
          :points="linePoints(column)"
          fill="none"
          :stroke="branchColor(column.branch)"
          stroke-width="2"
          stroke-linejoin="round"
          stroke-linecap="round"
          :stroke-dasharray="dashFor(index)"
        >
          <title>{{ column.branch }}</title>
        </polyline>
      </svg>
      <div class="flex flex-wrap gap-x-5 gap-y-1.5">
        <span
          v-for="(column, index) in columns"
          :key="column.branch"
          class="inline-flex items-center gap-1.5 text-xs"
        >
          <svg width="18" height="6" aria-hidden="true">
            <line
              x1="0"
              y1="3"
              x2="18"
              y2="3"
              :stroke="branchColor(column.branch)"
              stroke-width="2"
              :stroke-dasharray="dashFor(index) ? '4 3' : undefined"
            />
          </svg>
          <span class="font-mono">{{ column.branch }}</span>
          <span class="text-muted-color tabular-nums">
            {{ formatMetric(column.headlineMetric.value) }}
          </span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CompareBranchColumn, CompareFixture } from '../../fixtures/compare'
import { formatMetric } from '../../model/format'
import BranchTag from '../../ui/BranchTag.vue'
import { branchColor } from '../../ui/kinds'
import MetaBadge from '../../ui/MetaBadge.vue'
import IntegrityWarningBar from './IntegrityWarningBar.vue'

const props = defineProps<{ fixture: CompareFixture }>()

const columns = computed(() => props.fixture.branches)

const scoreNames = computed(() => {
  const names: string[] = []
  for (const column of columns.value)
    for (const name of Object.keys(column.scores)) if (!names.includes(name)) names.push(name)
  return names
})

// Fixture scores are all higher-is-better metrics; direction per score is not
// declared, so "best" means max.
const bestByScore = computed<Record<string, number>>(() => {
  const best: Record<string, number> = {}
  for (const name of scoreNames.value) {
    const values = columns.value
      .map((column) => column.scores[name])
      .filter((value): value is number => value !== undefined)
    best[name] = Math.max(...values)
  }
  return best
})

function isBest(score: string, column: CompareBranchColumn): boolean {
  return column.scores[score] !== undefined && column.scores[score] === bestByScore.value[score]
}

const W = 520
const H = 180
const PAD = { left: 38, right: 12, top: 10, bottom: 22 }

const allPoints = computed(() => columns.value.flatMap((column) => column.curve.points))
const xMin = computed(() => Math.min(...allPoints.value.map((p) => p[0])))
const xMax = computed(() => Math.max(...allPoints.value.map((p) => p[0])))
const yDomain = computed(() => {
  const ys = allPoints.value.map((p) => p[1])
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  const pad = (max - min) * 0.08 || 0.05
  return { min: min - pad, max: max + pad }
})

function sx(x: number): number {
  return PAD.left + ((x - xMin.value) / (xMax.value - xMin.value || 1)) * (W - PAD.left - PAD.right)
}

function sy(y: number): number {
  const { min, max } = yDomain.value
  return H - PAD.bottom - ((y - min) / (max - min || 1)) * (H - PAD.top - PAD.bottom)
}

function linePoints(column: CompareBranchColumn): string {
  return column.curve.points.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(' ')
}

const yTicks = computed(() => {
  const { min, max } = yDomain.value
  return [min, (min + max) / 2, max].map((value) => ({
    y: sy(value),
    label: formatMetric(value),
  }))
})

// Branches with identical curves would hide each other exactly; dashing the
// later duplicate keeps both visible as "two coincident lines".
function dashFor(index: number): string | undefined {
  const key = JSON.stringify(columns.value[index].curve.points)
  for (let j = 0; j < index; j += 1)
    if (JSON.stringify(columns.value[j].curve.points) === key) return '6 5'
  return undefined
}
</script>
