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

export enum FNNX_PRODUCER_TAGS_METADATA_ENUM {
  contains_classification_metrics_v1 = 'falcon.beastbyte.ai::tabular_classification_metrics:v1',
  contains_regression_metrics_v1 = 'falcon.beastbyte.ai::tabular_regression_metrics:v1',
}

export enum FNNX_PRODUCER_TAGS_MANIFEST_ENUM {
  tabular_classification_v1 = "dataforce.studio::tabular_classification:v1",
  tabular_regression_v1 = "dataforce.studio::tabular_regression:v1",
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

export interface RuntimeMetrics {
  performance: {
    eval_cv?: ClassificationMetrics | RegressionMetrics
    eval_holdout?: ClassificationMetrics | RegressionMetrics
    train: ClassificationMetrics | RegressionMetrics
  }
  permutation_feature_importance_train: {
    importances: TrainingImportance[]
  }
}
