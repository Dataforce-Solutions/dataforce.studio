<template>
  <SessionExpiredOverlay v-if="sessionExpired" />

  <main v-else class="dashboard">
    <DashboardHeader v-if="header && headerView === 'ready'" :header="header" />
    <StateBlock
      v-else
      :view="headerView"
      :skeleton-rows="2"
      error-title="Deployment context unavailable"
    />

    <GlobalControls
      :dimensions="dimensions"
      :auto-refresh="autoRefreshSeconds"
      @update:window="setWindow"
      @update:compare="setCompare"
      @update:severity="setSeverity"
      @update:auto="setAutoRefresh"
      @refresh="refresh"
    />

    <PlaceholderBanner v-if="isPlaceholderProfile" />

    <DashboardTabs :active="activeTab" @select="setActiveTab" />

    <!-- Refetches keep the previous content on screen, only dimmed: swapping a full
         tab for a skeleton on every reload made each click feel like a page load. -->
    <div class="tab-stage" :class="{ refreshing }">
    <OverviewTab
      v-if="activeTab === 'overview'"
      :overview="overview"
      :status="overviewStatus"
      :worker-health="workerHealth"
      :granularity="dimensions.granularity"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
      @update:granularity="setGranularity"
    />

    <RuntimeTab
      v-else-if="activeTab === 'runtime'"
      :runtime="runtime"
      :status="runtimeStatus"
      :granularity="dimensions.granularity"
      @acknowledge="acknowledgeAlert($event.metric)"
      @update:granularity="setGranularity"
    />

    <TracesTab
      v-else-if="activeTab === 'traces'"
      :traces="traces"
      :status="tracesStatus"
      :open-trace-id="openTraceId"
      :trace-detail="traceDetail"
      :trace-detail-status="traceDetailStatus"
      :new-count="tracesNewCount"
      @page="setTracesPage"
      @open="openTrace"
      @close-trace="closeTrace"
      @show-latest="showLatestTraces"
    />

    <DataQualityTab
      v-else-if="activeTab === 'data-quality'"
      :data-quality="dataQuality"
      :status="dataQualityStatus"
      :window="dimensions.window"
      :trends="qualityTrends"
      :trends-status="qualityTrendsStatus"
      :focus-feature="focusedFeature"
      @inspect="loadQualityTrends"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
    />

    <AlertsTab
      v-else-if="activeTab === 'alerts'"
      :alerts="alerts"
      :status="alertsStatus"
      :new-count="alertsNewCount"
      :fresh-keys="alertsFreshKeys"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
      @seen="markAlertsSeen"
    />

    <OutputDriftTab
      v-else-if="activeTab === 'output-drift'"
      :output-drift="outputDrift"
      :status="outputDriftStatus"
      :window="dimensions.window"
      @acknowledge="acknowledgeAlert($event.metric)"
    />

    <ReferenceProfileTab
      v-else-if="activeTab === 'reference-profile'"
      :profile="profileDocument"
      :status="profileDocumentStatus"
    />

    <FeatureDriftTab
      v-else
      :feature-drift="featureDrift"
      :status="featureDriftStatus"
      :window="dimensions.window"
      :selected-feature="dimensions.feature"
      :reference-profile="referenceProfile"
      :reference-profile-status="referenceProfileStatus"
      @select-feature="setFeature"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
    />
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useMonitoringDashboard } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import DashboardHeader from '@/components/DashboardHeader.vue'
import GlobalControls from '@/components/GlobalControls.vue'
import DashboardTabs from '@/components/DashboardTabs.vue'
import PlaceholderBanner from '@/components/PlaceholderBanner.vue'
import SessionExpiredOverlay from '@/components/SessionExpiredOverlay.vue'
import StateBlock from '@/components/StateBlock.vue'
import OverviewTab from '@/components/overview/OverviewTab.vue'
import RuntimeTab from '@/components/runtime/RuntimeTab.vue'
import TracesTab from '@/components/traces/TracesTab.vue'
import DataQualityTab from '@/components/data-quality/DataQualityTab.vue'
import FeatureDriftTab from '@/components/feature-drift/FeatureDriftTab.vue'
import OutputDriftTab from '@/components/output-drift/OutputDriftTab.vue'
import ReferenceProfileTab from '@/components/reference-profile/ReferenceProfileTab.vue'
import AlertsTab from '@/components/alerts/AlertsTab.vue'

const {
  dimensions,
  activeTab,
  sessionExpired,
  header,
  headerStatus,
  overview,
  overviewStatus,
  runtime,
  runtimeStatus,
  dataQuality,
  dataQualityStatus,
  qualityTrends,
  qualityTrendsStatus,
  loadQualityTrends,
  profileDocument,
  profileDocumentStatus,
  alerts,
  alertsStatus,
  alertsNewCount,
  alertsFreshKeys,
  markAlertsSeen,
  acknowledgeAlert,
  workerHealth,
  focusAlert,
  focusedFeature,
  traces,
  tracesStatus,
  tracesNewCount,
  showLatestTraces,
  openTraceId,
  traceDetail,
  traceDetailStatus,
  openTrace,
  closeTrace,
  featureDrift,
  featureDriftStatus,
  outputDrift,
  outputDriftStatus,
  referenceProfile,
  referenceProfileStatus,
  isPlaceholderProfile,
  autoRefreshSeconds,
  setAutoRefresh,
  load,
  refresh,
  setWindow,
  setGranularity,
  setCompare,
  setSeverity,
  setFeature,
  setTracesPage,
  setActiveTab,
} = useMonitoringDashboard()

const headerView = computed(() => sectionView(headerStatus.value, header.value?.state))

/** The active tab is fetching; its stale content stays up, dimmed a touch. */
const refreshing = computed(() => {
  const status = {
    overview: overviewStatus,
    runtime: runtimeStatus,
    traces: tracesStatus,
    'data-quality': dataQualityStatus,
    'feature-drift': featureDriftStatus,
    'output-drift': outputDriftStatus,
    'reference-profile': profileDocumentStatus,
    alerts: alertsStatus,
  }[activeTab.value]
  return status?.value === 'loading'
})

onMounted(() => {
  void load()
})
</script>

<style scoped>
.tab-stage {
  transition: opacity 0.15s ease;
}
/* The delay keeps fast refetches invisible; only a slow one dims at all. */
.tab-stage.refreshing {
  opacity: 0.55;
  transition-delay: 0.2s;
  pointer-events: none;
}
</style>
