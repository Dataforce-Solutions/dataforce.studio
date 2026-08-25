<template>
  <section class="alerts-tab" data-testid="alerts-tab">
    <div class="intro">
      <p class="section-title">Alerts</p>
      <p class="section-subtitle">
        What needs attention: every threshold still breached in the selected window.
      </p>
    </div>

    <div class="card">
      <StateBlock
        v-if="view !== 'ready'"
        :view="view"
        :skeleton-rows="4"
        empty-title="Nothing is firing"
        empty-detail="No metric is past its threshold in this window."
      />

      <template v-else>
        <div class="summary" data-testid="alerts-summary">
          <span class="count">{{ total }} open</span>
          <span v-if="criticals" class="count critical">{{ criticals }} critical</span>
        </div>

        <!-- Alerts that fired since the reader last looked; dismissing marks them seen. -->
        <button
          v-if="newCount > 0"
          type="button"
          class="new-alerts"
          data-testid="new-alerts"
          @click="$emit('seen')"
        >
          <BellRing :size="13" />
          {{ newCount }} new {{ newCount === 1 ? 'alert' : 'alerts' }} — mark seen
        </button>

        <!-- Same viewport as the Traces table: past that the list scrolls, not the page. -->
        <div class="table-scroll table-viewport">
          <table class="alerts-table" data-testid="alerts-table">
            <thead>
              <tr>
                <th>Alert</th>
                <th>Seen</th>
                <th class="num">Value</th>
                <th>Status</th>
                <th class="num">Duration</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="group in alerts?.groups ?? []" :key="group.group">
                <tr class="group-row">
                  <td colspan="5">
                    {{ groupLabel(group.group) }}
                    <span class="group-count">{{ group.alerts.length }}</span>
                  </td>
                </tr>
                <tr
                  v-for="alert in group.alerts"
                  :key="alert.metric"
                  class="row"
                  :class="{ selected: alert.metric === selected?.metric, fresh: freshKeys?.has(alert.metric) }"
                  data-testid="alert-row"
                  role="button"
                  tabindex="0"
                  :aria-label="`Inspect ${alert.metric}`"
                  @click="selected = alert"
                  @keydown.enter.prevent="selected = alert"
                  @keydown.space.prevent="selected = alert"
                >
                  <td>
                    <span class="subject-cell">
                      <span class="dot" :class="`sev-${alert.severity}`" />
                      <span class="subject mono">{{ subject(alert) }}</span>
                    </span>
                  </td>
                  <td class="seen-cell">
                    <span
                      v-if="alert.state === 'acknowledged'"
                      class="ack"
                      title="Someone has seen this alert; it stays until the metric recovers"
                      data-testid="alert-acknowledged-chip"
                    >
                      <Check :size="11" />
                      seen
                    </span>
                  </td>
                  <td class="reading mono num">{{ alert.value_label }}</td>
                  <td><SeverityTag :severity="alert.severity" /></td>
                  <td class="age num">{{ durationLabel(alert.duration_seconds) }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <DetailDrawer
      :open="selected !== null"
      :feature="selected ? subject(selected) : null"
      :kind="selected?.label ?? null"
      :caption="drawerCaption"
      eyebrow="Alert"
      testid="alert-drawer"
      @close="selected = null"
    >
      <template #status>
        <SeverityTag v-if="selected" :severity="selected.severity" />
      </template>
      <AlertDetailPanel
        v-if="selected"
        :alert="selected"
        @show-feature="showFeature"
        @acknowledge="$emit('acknowledge', $event)"
      />
    </DetailDrawer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AlertBanner, AlertsResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { alertSubject, durationLabel, groupLabel } from '@/lib/alerts'
import StateBlock from '@/components/StateBlock.vue'
import { BellRing, Check } from 'lucide-vue-next'
import SeverityTag from '@/components/SeverityTag.vue'
import DetailDrawer from '@/components/DetailDrawer.vue'
import AlertDetailPanel from './AlertDetailPanel.vue'

const props = withDefaults(
  defineProps<{
    alerts: AlertsResponse | null
    status: LoadStatus
    newCount?: number
    freshKeys?: Set<string>
  }>(),
  { newCount: 0, freshKeys: undefined },
)

const emit = defineEmits<{ 'show-feature': [AlertBanner]; acknowledge: [AlertBanner]; seen: [] }>()

const view = computed(() => {
  const state = sectionView(props.status, props.alerts?.state)
  // An "ok" section with no groups is the good case, not a missing one.
  return state === 'ready' && !props.alerts?.groups?.length ? 'empty' : state
})

const selected = ref<AlertBanner | null>(null)

const total = computed(() =>
  (props.alerts?.groups ?? []).reduce((sum, group) => sum + group.alerts.length, 0),
)
const criticals = computed(() =>
  (props.alerts?.groups ?? []).reduce(
    (sum, group) => sum + group.alerts.filter((a) => a.severity === 'critical').length,
    0,
  ),
)

function subject(alert: AlertBanner): string {
  return alertSubject(alert)
}

const drawerCaption = computed(() => {
  if (!selected.value) return null
  return `${groupLabel(selected.value.group)} · ${selected.value.state ?? 'open'}`
})

function showFeature(alert: AlertBanner): void {
  emit('show-feature', alert)
  selected.value = null
}

// An alert panel must not outlive the alert: a reload may have resolved it.
watch(
  () => props.alerts,
  (response) => {
    if (!selected.value) return
    const key = selected.value.metric
    const all = (response?.groups ?? []).flatMap((group) => group.alerts)
    selected.value = all.find((alert) => alert.metric === key) ?? null
  },
)
</script>

<style scoped>
.alerts-tab {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.summary {
  display: flex;
  gap: var(--luml-space-3);
  padding-bottom: 12px;
  border-bottom: 1px solid var(--luml-border);
}
.count {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.count.critical {
  color: var(--luml-danger-tint-fg);
}
.new-alerts {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 10px 0 2px;
  padding: 5px 12px;
  border: 1px solid var(--luml-brand-tint-strong);
  border-radius: var(--luml-radius-pill);
  background: var(--luml-brand-tint);
  color: var(--luml-brand);
  font: inherit;
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
}
.new-alerts:hover {
  background: var(--luml-brand-tint-strong);
}
.table-scroll {
  overflow-x: auto;
}
/* Same column-header treatment as the Data quality table. */
.alerts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.alerts-table th {
  text-align: left;
  padding: 8px 12px;
  color: var(--luml-fg-muted);
  font-weight: 500;
  border-bottom: 1px solid var(--luml-border);
  white-space: nowrap;
  /* the header stays put while the list scrolls under it */
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--luml-bg-card);
}
.alerts-table td {
  padding: 11px 18px;
  border-bottom: 1px solid var(--luml-surface-100);
  color: var(--luml-fg);
}
.alerts-table tbody tr:last-child td {
  border-bottom: none;
}
.alerts-table .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.group-row td {
  padding: 14px 18px 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
  border-bottom: none;
}
.group-count {
  margin-left: 4px;
  font-weight: 500;
}
.row {
  cursor: pointer;
}
.row:hover td,
.row.selected td {
  background: var(--luml-surface-50);
}
.row.fresh td {
  animation: fresh-alert 2.2s ease-out;
}
@keyframes fresh-alert {
  from {
    background: var(--luml-brand-tint);
  }
  to {
    background: transparent;
  }
}
.subject-cell {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.sev-critical {
  background: var(--luml-danger);
}
.dot.sev-warning {
  background: var(--luml-warn);
}
.dot.sev-ok {
  background: var(--luml-success);
}
.subject {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.reading {
  font-size: 13px;
  color: var(--luml-fg);
}
/* Quiet green: the mark means "handled", it must not compete with severity colors. */
.ack {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: var(--luml-radius-pill);
  background: var(--luml-success-tint-bg);
  color: var(--luml-success-tint-fg);
  font-size: 10.5px;
  font-weight: 500;
}
.age {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
</style>
