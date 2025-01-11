import {
  Tasks,
  type ClassificationMetrics,
  type PredictRequestData,
  type RegressionMetrics,
  type TaskPayload,
  type TrainingData,
} from './../lib/data-processing/interfaces'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { predictErrorToast, trainingErrorToast } from '@/lib/primevue/data/toasts'
import { getMetrics, toPercent } from '@/helpers/helpers'

export const useModelTraining = () => {
  const toast = useToast()

  const isLoading = ref(false)
  const isTrainingSuccess = ref(false)
  const trainingData = ref<TrainingData<ClassificationMetrics | RegressionMetrics> | null>(null)
  const modelsIdList = ref<string[]>([])
  const trainingModelId = ref<string | null>(null)
  const modelBlob = ref<Blob | null>(null)
  const currentTask = ref<Tasks | null>(null)

  const getTotalScore = computed(() =>
    trainingData.value ? toPercent(trainingData.value.test_metrics.SC_SCORE) : 0,
  )
  const getTestMetrics = computed(() => {
    if (!trainingData.value) return [];

    if (currentTask.value === Tasks.TABULAR_CLASSIFICATION) {
      return getMetrics(trainingData.value, Tasks.TABULAR_CLASSIFICATION, 'test_metrics')
    } else {
      return getMetrics(trainingData.value, Tasks.TABULAR_REGRESSION, 'test_metrics')
    }
  })
  const getTrainingMetrics = computed(() => {
    if (!trainingData.value) return [];

    if (currentTask.value === Tasks.TABULAR_CLASSIFICATION) {
      return getMetrics(trainingData.value, Tasks.TABULAR_CLASSIFICATION, 'train_metrics')
    } else {
      return getMetrics(trainingData.value, Tasks.TABULAR_REGRESSION, 'train_metrics')
    }
  })
  const getTop5Feature = computed(
    () => trainingData.value?.importances.filter((item, index) => index < 5) || [],
  )
  const isTrainMode = computed(() => trainingData.value?.predicted_data_type === 'train')
  const getPredictedData = computed(() =>
    trainingData.value ? trainingData.value.predicted_data : {},
  )

  async function startTraining(data: TaskPayload) {
    isLoading.value = true
    try {
      const result: TrainingData<ClassificationMetrics> = await DataProcessingWorker.startTraining(
        JSON.parse(JSON.stringify(data)),
      )

      if (result.status === 'success') {
        trainingData.value = result
        trainingModelId.value = result.model_id
        modelsIdList.value.push(result.model_id)
        saveModel(result.model)
        isTrainingSuccess.value = true
        currentTask.value = data.task
      } else {
        throw new Error(result?.error_message || 'Unknown error')
      }
    } catch (error: any) {
      isTrainingSuccess.value = false
      toast.add(trainingErrorToast(error))
    } finally {
      isLoading.value = false
    }
  }

  async function startPredict(request: PredictRequestData) {
    isLoading.value = true

    try {
      const result = await DataProcessingWorker.startPredict(JSON.parse(JSON.stringify(request)))

      if (result.status === 'success') {
        return result
      } else {
        throw new Error(result?.error_message || 'Unknown error')
      }
    } catch (error: any) {
      toast.add(predictErrorToast(error))
    } finally {
      isLoading.value = false
    }
  }

  function saveModel(model: object) {
    const modelBytes = new Uint8Array(Object.values(model))
    modelBlob.value = new Blob([modelBytes])
  }

  function downloadModel() {
    if (!modelBlob.value) throw new Error('There is no model to download')

    const timestamp = Date.now()
    const filename = `${currentTask.value}_${timestamp}.dfs`

    const url = URL.createObjectURL(modelBlob.value)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  async function deleteModels() {
    await DataProcessingWorker.deallocateModels(modelsIdList.value)
  }

  onBeforeUnmount(() => {
    deleteModels()
  })

  return {
    isLoading,
    isTrainingSuccess,
    getTotalScore,
    getTestMetrics,
    getTrainingMetrics,
    getTop5Feature,
    isTrainMode,
    getPredictedData,
    trainingModelId,
    currentTask,
    startTraining,
    downloadModel,
    startPredict,
  }
}
