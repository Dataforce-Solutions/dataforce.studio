export enum WebworkerMessage {
  LOAD_PYODIDE = 'LOAD_PYODIDE',
  TABULAR_PREDICT = 'tabular_predict',
  TABULAR_TRAIN = 'tabular_train',
  TABULAR_DEALLOCATE = 'tabular_deallocate',
}

export enum Tasks {
  TABULAR_CLASSIFICATION = 'tabular_classification',
  TABULAR_REGRESSION = 'tabular_regression',
}

export interface TaskPayload {
  data: object
  target: string
  groups?: string[]
  task: Tasks.TABULAR_CLASSIFICATION | Tasks.TABULAR_REGRESSION
}

export interface TrainingData<T extends ClassificationMetrics | RegressionMetrics> {
  importances: TrainingImportance[]
  model: object
  model_id: string
  predicted_data: Record<string, []>
  predicted_data_type: PredictedDataType
  test_metrics: T
  train_metrics: T
  status: TrainingStatus
  error_message?: string
}

type PredictedDataType = 'train' | 'test'

type TrainingStatus = 'success' | 'error'

export interface TrainingImportance {
  feature_name: string
  scaled_importance: number
}

export interface ClassificationMetrics {
  ACC: number
  PRECISION: number
  RECALL: number
  F1: number
  SC_SCORE: number
}

export interface RegressionMetrics {
  MSE: number
  RMSE: number
  MAE: number
  R2: number
  SC_SCORE: number
}

export interface PredictRequestData {
  data: object,
  model_id: string
}