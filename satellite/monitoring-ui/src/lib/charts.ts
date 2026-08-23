import type { Series } from '@/api/types'

export interface ChartCard {
  series: Series
  title: string
  subtitle: string
  color: string
}

const FALLBACK_COLOR = '#2673fd'

// The runtime rollup drives both Overview and Runtime, so the same series is titled and
// coloured the same on both — a reader moving between the tabs sees one chart, not two.
const RUNTIME_CHART_META: Record<string, { title: string; subtitle: string; color: string }> = {
  requests: {
    title: 'Requests over time',
    subtitle: 'prediction calls per interval',
    color: FALLBACK_COLOR,
  },
  error_rate: {
    title: 'Error rate over time',
    subtitle: '4xx / 5xx share of calls',
    color: '#f97316',
  },
  latency_p95: {
    title: 'Latency p95 over time',
    subtitle: '95th percentile response time',
    color: '#a855f7',
  },
}

export function runtimeCharts(series: Series[] | undefined): ChartCard[] {
  return (series ?? []).map((entry) => ({
    series: entry,
    ...(RUNTIME_CHART_META[entry.key] ?? {
      title: entry.label,
      subtitle: '',
      color: FALLBACK_COLOR,
    }),
  }))
}
