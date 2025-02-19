<template>
  <div>
    <d-dialog
      v-model:visible="isPredictVisible"
      modal
      header="Predict"
      :style="{ width: '31.25rem' }">
      <predict-content :manual-fields="predictionFields" :model-id="trainingModelId" />
    </d-dialog>
    <header class="header">
      <h1 class="title">Model evaluation dashboard</h1>
      <div class="buttons">
        <d-button severity="secondary" @click="isPredictVisible = true">
          <span>predict</span>
          <wand-sparkles width="14" height="14" />
        </d-button>
        <d-button severity="secondary" @click="downloadModelCallback()">
          <span>download</span>
          <cloud-download width="14" height="14" />
        </d-button>
        <d-button label="finish" @click="finishConfirm" />
      </div>
    </header>
    <div class="body">
      <div class="performance card">
        <header class="card-header">
          <h3 class="card-title">Model perfomance</h3>
          <info
            width="20"
            height="20"
            class="info-icon"
            v-tooltip.bottom="`Track your model's effectiveness through performance metrics. Higher scores indicate better predictions and generalization to new data`"/>
        </header>
        <div class="radialbar-wrapper">
          <apexchart
            type="radialBar"
            :series="[totalScore]"
            :options="totalScoreOptions"
            :style="{ pointerEvents: 'none', marginTop: '-30px', height: '135px' }"/>
        </div>
        <div class="metric-cards">
          <metric-card
            v-for="card in metricCardsData"
            :key="card.title"
            :title="card.title"
            :items="card.items"/>
        </div>
      </div>
      <div class="features card">
        <header class="card-header">
          <h3 class="card-title">Top {{ features.length }} features</h3>
          <info
            width="20"
            height="20"
            class="info-icon"
            v-tooltip.bottom="`Understand which features play the biggest role in your model's outcomes to guide further data analysis`"/>
        </header>
        <div :style="{ maxWidth: '725px' }">
          <apexchart
            type="bar"
            :options="featuresOptions"
            :series="featuresData"
            :height="barChartHeight"
            width="100%"
            :style="{ pointerEvents: 'none', margin: '-30px 0' }"/>
        </div>
      </div>
      <div class="detailed card">
        <detailed-table :values="detailedView" :is-train-mode="isTrainMode" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Tasks, TrainingImportance } from '@/lib/data-processing/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { WandSparkles, CloudDownload, Info } from 'lucide-vue-next'
import { getBarOptions, getRadialBarOptions } from '@/lib/apex-charts/apex-charts'
import { getMetricsCards } from '@/helpers/helpers'
import MetricCard from '../../../ui/MetricCard.vue'
import DetailedTable from './DetailedTable.vue'
import PredictContent from './PredictContent.vue'
import { table } from 'arquero'
import { useConfirm } from 'primevue/useconfirm'
import { dashboardFinishConfirmOptions } from '@/lib/primevue/data/confirm'
import { useRouter } from 'vue-router'

type Props = {
  predictionFields: string[]
  totalScore: number
  testMetrics: string[]
  trainingMetrics: string[]
  features: TrainingImportance[]
  predictedData: Record<string, []>
  isTrainMode: boolean
  downloadModelCallback: Function
  trainingModelId: string
  currentTask: Tasks | null
}

const props = defineProps<Props>()

const router = useRouter()
const confirm = useConfirm()

const finishConfirm = () => {
  const accept = async () => {
    router.push({ name: 'home' })
  }
  confirm.require(dashboardFinishConfirmOptions(accept))
}

const totalScoreOptions = ref(getRadialBarOptions())
const isPredictVisible = ref(false)
const detailedView = ref<any>([])

const metricCardsData = computed(() => props.currentTask ? getMetricsCards(props.testMetrics, props.trainingMetrics, props.currentTask) : [])
const featuresData = computed(() => {
  const data = props.features.map((feature) => (feature.scaled_importance * 100).toFixed())
  return [{ data }]
})
const featuresOptions = computed(() =>
  getBarOptions(
    props.features.map((feature) => {
      const name = feature.feature_name.length > 12 ? feature.feature_name.slice(0, 10) + '...' : feature.feature_name;
      return `${name} (${(feature.scaled_importance * 100).toFixed()}%)`
    }
    ),
  ),
)
const barChartHeight = computed(() => {
  const featuresCount = props.features.length
  return 45 * featuresCount + 60 + 'px'
})

onBeforeMount(() => {
  detailedView.value = table(props.predictedData).objects()
})
</script>

<style scoped>
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-top: 32px;
  margin-bottom: 20px;
}

.title {
  font-size: 24px;
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
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
}

.metric-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.radialbar-wrapper {
  max-width: 325px;
  margin: 0 auto;
  margin-bottom: 2rem;
}

.radialbar-wrapper .vue-apexcharts {
  min-height: 0 !important;
}

@media (max-width: 1200px) {
  .header {
    flex-direction: column;
  }

  .body {
    grid-template-columns: 1fr;
  }

  .metric-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
}

.info-icon {
  color: var(--p-icon-muted-color);
}

@media (max-width:768px){
  .header {
    padding-top: 8px;
  }
  .card {
    padding: 16px;
  }
  .metric-cards {
    grid-template-columns: 1fr;
  }
  .info-icon {
    display: none;
  }
}
</style>
