import { Tasks, type ClassificationMetrics, type RegressionMetrics, type TrainingData } from '@/lib/data-processing/interfaces'
import type { ProviderSetting } from '@/lib/promt-fusion/prompt-fusion.interfaces'

export const getMetrics = (
  data: TrainingData<ClassificationMetrics | RegressionMetrics>,
  task: Tasks,
  metricsType: 'test_metrics' | 'train_metrics',
) => {
  if (task === Tasks.TABULAR_CLASSIFICATION) {
    const metrics = data?.[metricsType] as ClassificationMetrics
    return [
      metrics?.ACC ? fixNumber(metrics.ACC, 2).toFixed(2) : '0',
      metrics?.PRECISION ? fixNumber(metrics.PRECISION, 2).toFixed(2) : '0',
      metrics?.RECALL ? fixNumber(metrics.RECALL, 2).toFixed(2) : '0',
      metrics?.F1 ? fixNumber(metrics.F1, 2).toFixed(2) : '0',
    ]
  } else {
    const metrics = data?.[metricsType] as RegressionMetrics
    return [
      metrics?.MSE ? getFormattedMetric(metrics.MSE) : '0',
      metrics?.RMSE ? getFormattedMetric(metrics.RMSE) : '0',
      metrics?.MAE ? getFormattedMetric(metrics.MAE) : '0',
      metrics?.R2 ? getFormattedMetric(metrics.R2) : '0',
    ]
  }
}

export const getFormattedMetric = (num: number) => {
  if (Math.log10(Math.abs(num)) > 5) return formatNumberScientific(num)
  else if (Math.log10(Math.abs(num)) > 2) return num.toFixed()
  return num.toFixed(2)
}

export const getMetricsCards = (testValues: string[], trainingValues: string[], task: Tasks) => {
  let titles: string[] = []
  if (task === Tasks.TABULAR_CLASSIFICATION) {
    titles = ['Balanced accuracy', 'Precision', 'Recall', 'F1 score']
  } else {
    titles = ['Mean Squared Error', 'Root Mean Squared Error', 'Mean Absolute Error', 'R² Score']
  }
  return titles.map((title, index) => ({
    title,
    items: [{ value: testValues[index] }, { value: trainingValues[index] }],
  }))
}

export const toPercent = (float: number) => Number((float * 100).toFixed())

export const fixNumber = (float: number, decimals: number) => Number(float.toFixed(decimals))

export const convertObjectToCsvBlob = (data: object) => {
  const headers = Object.keys(data)
  const rows = []
  const maxLength = Math.max(...headers.map((key) => (data[key as keyof typeof data] as []).length))
  for (let i = 0; i < maxLength; i++) {
    const row = headers.map((header) => data[header as keyof typeof data][i] ?? '')
    rows.push(row)
  }
  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n')
  return new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
}

export const formatNumberScientific = (num: number, significantDigits = 3) => {
  return new Intl.NumberFormat('en', {
    notation: 'scientific',
    maximumSignificantDigits: significantDigits,
  }).format(num)
}

export const cutStringOnMiddle = (string: string, length = 20) => {
  if (string.length < length) return string
  const startSubstring = string.slice(0, Math.floor(length / 2))
  const endSubstring = string.slice(Math.floor(-length / 2))
  return `${startSubstring}...${endSubstring}`
}

export const prepareRuntimeMetrics = (metrics: ClassificationMetrics | RegressionMetrics, task: Tasks) => {
  if (task === Tasks.TABULAR_CLASSIFICATION) {
    const currentMetrics = metrics as ClassificationMetrics
    return [
      currentMetrics.ACC ? fixNumber(currentMetrics.ACC, 2).toFixed(2) : '0',
      currentMetrics.PRECISION ? fixNumber(currentMetrics.PRECISION, 2).toFixed(2) : '0',
      currentMetrics.RECALL ? fixNumber(currentMetrics.RECALL, 2).toFixed(2) : '0',
      currentMetrics.F1 ? fixNumber(currentMetrics.F1, 2).toFixed(2) : '0',
    ]
  } else if (task === Tasks.TABULAR_REGRESSION) {
    const currentMetrics = metrics as RegressionMetrics
    return [
      currentMetrics.MSE ? getFormattedMetric(currentMetrics.MSE) : '0',
      currentMetrics.RMSE ? getFormattedMetric(currentMetrics.RMSE) : '0',
      currentMetrics.MAE ? getFormattedMetric(currentMetrics.MAE) : '0',
      currentMetrics.R2 ? getFormattedMetric(currentMetrics.R2) : '0',
    ]
  } else {
    return []
  }
}

export const parseProviderSettingsToObject = (settings: ProviderSetting[] | null) => {
  if (!settings) return {}
  return settings.reduce((acc: Record<string, string>, setting) => {
    acc[setting.id] = setting.value
    return acc
  }, {}) || {}
}
