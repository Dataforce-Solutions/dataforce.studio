import {
  type ClassificationMetrics,
  type PredictRequestData,
  type TaskPayload,
  type TrainingData,
} from './../lib/data-processing/interfaces'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { predictErrorToast, trainingErrorToast } from '@/lib/primevue/data/toasts'
import { fixNumber, toPercent } from '@/helpers/helpers'

export const useModelTraining = () => {
  const toast = useToast()

  const isLoading = ref(false)
  const isTrainingSuccess = ref(false)
  const trainingData = ref<TrainingData<ClassificationMetrics> | null>(null)
  const modelsIdList = ref<string[]>([])
  const trainingModelId = ref<string | null>(null)
  const modelBlob = ref<Blob | null>(null)

  const getTotalScore = computed(() =>
    trainingData.value ? toPercent(trainingData.value.test_metrics.SC_SCORE) : 0,
  )
  const getTestMetrics = computed(() => ({
    ACC: trainingData.value ? fixNumber(trainingData.value.test_metrics.ACC, 2) : 0,
    PRECISION: trainingData.value ? fixNumber(trainingData.value.test_metrics.PRECISION, 2) : 0,
    RECALL: trainingData.value ? fixNumber(trainingData.value.test_metrics.RECALL, 2) : 0,
    F1: trainingData.value ? fixNumber(trainingData.value.test_metrics.F1, 2) : 0,
  }))
  const getTrainingMetrics = computed(() => ({
    ACC: trainingData.value ? fixNumber(trainingData.value?.train_metrics.ACC, 2) : 0,
    PRECISION: trainingData.value ? fixNumber(trainingData.value?.train_metrics.PRECISION, 2) : 0,
    RECALL: trainingData.value ? fixNumber(trainingData.value?.train_metrics.RECALL, 2) : 0,
    F1: trainingData.value ? fixNumber(trainingData.value?.train_metrics.F1, 2) : 0,
  }))
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

  function downloadModel(fileName: string) {
    if (!modelBlob.value) throw new Error('There is no model to download')

    const url = URL.createObjectURL(modelBlob.value)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
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
    startTraining,
    downloadModel,
    startPredict,
  }
}
