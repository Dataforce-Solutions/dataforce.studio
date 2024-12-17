<template>
  <div>
    <d-dialog
      v-model:visible="isPredictVisible"
      modal
      header="Predict"
      :style="{ width: '31.25rem' }"
    >
      <predict-content
        :manual-fields="[
          'AppointmentId',
          'AppointmentDate',
          'AppointmentTime',
          'Status',
          'Notes',
          'AppointmentId',
        ]"
      />
    </d-dialog>
    <header class="header">
      <h1 class="title">Model evaluation dashboard</h1>
      <div class="buttons">
        <d-button severity="secondary" @click="isPredictVisible = true">
          <span>predict</span>
          <wand-sparkles width="14" height="14" />
        </d-button>
        <d-button severity="secondary">
          <span>download</span>
          <cloud-download width="14" height="14" />
        </d-button>
        <d-button label="finish" />
      </div>
    </header>
    <div class="body">
      <div class="performance card">
        <header class="card-header">
          <h3 class="card-title">Model perfomance</h3>
          <info
            width="20"
            height="20"
            v-tooltip.bottom="
              `Track your model's effectiveness through performance metrics. Higher scores indicate better predictions and generalization to new data`
            "
          />
        </header>
        <div>
          <apexchart
            type="radialBar"
            :series="totalScoreData"
            :options="totalScoreOptions"
            :style="{pointerEvents: 'none', marginTop: '-30px'}"
          />
        </div>
        <div class="metric-cards">
          <metric-card
            v-for="card in metricCardsData"
            :key="card.title"
            :title="card.title"
            :items="card.items"
          />
        </div>
      </div>
      <div class="features card">
        <header class="card-header">
          <h3 class="card-title">Top 5 features</h3>
          <info
            width="20"
            height="20"
            v-tooltip.bottom="
              `Understand which features play the biggest role in your model's outcomes to guide further data analysis`
            "
          />
        </header>
        <div :style="{ maxWidth: '725px' }">
          <apexchart
            type="bar"
            :options="featuresOptions"
            :series="featuresData"
            :height="224 + 60 + 'px'"
            width="100%"
            :style="{pointerEvents: 'none', margin: '-30px 0'}"
          />
        </div>
      </div>
      <div class="detailed card">
        <detailed-table />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { WandSparkles, CloudDownload, Info } from 'lucide-vue-next'

import MetricCard from './MetricCard.vue'
import DetailedTable from './DetailedTable.vue'
import PredictContent from './PredictContent.vue'

import { getBarOptions, getRadialBarOptions } from '@/lib/apex-charts/apex-charts'

import { metricCardsData } from '@/assets/data/mock/mockData'

const totalScoreData = ref([85])
const totalScoreOptions = ref(getRadialBarOptions())

const featuresData = ref([{ data: [40, 30, 15, 10, 5] }])
const featuresOptions = ref(
  getBarOptions(['AppointmentId', 'AppointmentDate', 'AppointmentTime', 'Status', 'Notes']),
)
const isPredictVisible = ref(false)
</script>

<style scoped>
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-top: 24px;
  margin-bottom: 24px;
}

.title {
  font-size: 2rem;
}

.buttons {
  display: flex;
  gap: 8px;
}

.body {
  display: grid;
  grid-template-columns: 374px 1fr;
  gap: 24px;
}

.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.performance {
  grid-row: span 2;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.card-title {
  font-size: 1.5rem;
}

.metric-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
