<template>
  <section class="runtime" data-testid="runtime-tab">
    <div class="intro">
      <p class="section-title">Runtime</p>
      <p class="section-subtitle">
        Is the deployed endpoint technically healthy — regardless of what it predicts?
      </p>
    </div>

    <AlertBannerList
      v-if="runtime?.alerts?.length"
      :banners="runtime.alerts"
      inspectable
      @acknowledge="$emit('acknowledge', $event)"
    />

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="4"
      empty-title="No calls in this window"
      empty-detail="Nothing reached the deployment in the selected range. Widen the range, or send traffic."
    />

    <template v-else-if="runtime">
      <div class="cards grid">
        <MetricCard v-for="card in cards" :key="card.key" :card="card" />
      </div>

      <div class="charts grid">
        <ChartFrame
          v-for="chart in charts"
          :key="chart.series.key"
          class="card"
          :title="chart.title"
          :subtitle="chart.subtitle"
          eyebrow="Runtime"
        >
          <template #default="{ height }">
            <SeriesChart :series="chart.series" :color="chart.color" :height="height" />
          </template>
        </ChartFrame>
      </div>

      <!--
        The counters above say how many calls failed; this says how. A window that is all
        504 is a saturated model server, one that is all 422 is a caller sending bad
        payloads — the same error rate, different problem.
      -->
      <div class="card">
        <p class="section-title small">Outcome breakdown</p>
        <p class="section-subtitle">how the calls in this window ended</p>

        <p v-if="!runtime.status_breakdown.length" class="empty">No calls to break down.</p>

        <div v-else class="table-scroll">
          <table class="breakdown" data-testid="status-breakdown">
            <thead>
              <tr>
                <th>Outcome</th>
                <th>Code</th>
                <th class="num">Calls</th>
                <th class="num">Share</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in runtime.status_breakdown" :key="rowKey(row)" data-testid="status-row">
                <td class="outcome" :class="{ failed: row.status !== 'success' }">
                  {{ outcomeLabel(row.status) }}
                </td>
                <td class="mono">{{ row.status_code ?? '—' }}</td>
                <td class="mono num">{{ formatCount(row.count) }}</td>
                <td class="mono num">{{ formatRate(row.share) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AlertBanner, Card, RuntimeResponse, StatusBreakdownRow } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { runtimeCharts } from '@/lib/charts'
import { formatCount, formatRate } from '@/lib/format'
import StateBlock from '@/components/StateBlock.vue'
import SeriesChart from '@/components/SeriesChart.vue'
import ChartFrame from '@/components/ChartFrame.vue'
import MetricCard from '@/components/overview/MetricCard.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'

const props = defineProps<{
  runtime: RuntimeResponse | null
  status: LoadStatus
}>()

defineEmits<{ acknowledge: [AlertBanner] }>()

/**
 * A window nobody called reads as empty, not as a wall of zeros.
 *
 * The rollup is computed on demand and always answers `ok`, so with no traffic the section
 * would otherwise render eight zeroed cards and three flat charts — which looks like a
 * broken dashboard rather than a quiet deployment.
 */
const view = computed(() => {
  const state = sectionView(props.status, props.runtime?.state)
  return state === 'ready' && props.runtime?.request_count === 0 ? 'empty' : state
})

const charts = computed(() => runtimeCharts(props.runtime?.series))

/**
 * The rollup as cards, in the order the spec lists the runtime metrics.
 *
 * Overview shows three of these; the rest live only here, which is the point of the tab —
 * a timeout alert can fire with nothing on Overview to confirm it against.
 */
const cards = computed<Card[]>(() => {
  const data = props.runtime
  if (!data) return []
  return [
    { key: 'requests', label: 'Requests', value: data.request_count },
    { key: 'success_rate', label: 'Success rate', value: data.success_rate, unit: 'ratio' },
    { key: 'error_rate', label: 'Error rate', value: data.error_rate, unit: 'ratio' },
    { key: 'latency_p50', label: 'Latency p50', value: data.latency_p50_ms, unit: 'ms' },
    { key: 'latency_p95', label: 'Latency p95', value: data.latency_p95_ms, unit: 'ms' },
    { key: 'latency_max', label: 'Latency max', value: data.latency_max_ms, unit: 'ms' },
    { key: 'timeout_count', label: 'Timeouts', value: data.timeout_count },
    {
      key: 'failed_inference_count',
      label: 'Failed inferences',
      value: data.failed_inference_count,
    },
  ]
})

function rowKey(row: StatusBreakdownRow): string {
  return `${row.status}:${row.status_code ?? 'none'}`
}

function outcomeLabel(status: string): string {
  const words = status.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
</script>

<style scoped>
.runtime {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.cards {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.charts {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}
.section-title.small {
  font-size: var(--luml-text-base);
}
.empty {
  margin: var(--luml-space-3) 0 0;
  font-size: var(--luml-caption-size);
  color: var(--luml-fg-muted);
}
.table-scroll {
  overflow-x: auto;
  margin-top: var(--luml-space-3);
}
.breakdown {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.breakdown th {
  text-align: left;
  padding: 10px 12px;
  background: var(--luml-surface-50);
  color: var(--luml-fg-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--luml-border);
  white-space: nowrap;
}
.breakdown td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--luml-surface-100);
  color: var(--luml-fg);
}
.breakdown tbody tr:last-child td {
  border-bottom: none;
}
.breakdown .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.outcome {
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.outcome.failed {
  color: var(--luml-danger-tint-fg);
}
</style>
