import type { FlowExportObject } from '@vue-flow/core'
import type { NodeData } from '@/components/express-tasks/prompt-fusion/interfaces'
import type {
  PayloadData,
  PayloadNode,
  PromptFusionPayload,
  ProviderModelsEnum,
  ProvidersEnum,
  ProviderSetting,
  ProviderWithModels,
  TrainingData,
} from './prompt-fusion.interfaces'
import { Observable } from '@/utils/observable/Observable'
import { EvaluationModesEnum, ProviderStatus } from './prompt-fusion.interfaces'
import { allModels, getProviders } from './prompt-fusion.data'
import { parseProviderSettingsToObject } from '@/helpers/helpers'
import { DataProcessingWorker } from '../data-processing/DataProcessingWorker'
import { WEBWORKER_ROUTES_ENUM } from '../data-processing/interfaces'

type Events = {
  CHANGE_SETTINGS_STATUS: boolean
  CHANGE_OPTIMIZATION_STATE: boolean
  OPEN_PROVIDER_SETTINGS: ProvidersEnum
  CLOSE_PROVIDER_SETTINGS: void
  CHANGE_TEACHER_MODEL: ProviderModelsEnum | null
  CHANGE_STUDENT_MODEL: ProviderModelsEnum | null
  CHANGE_TRAINING_STATE: boolean
  CHANGE_PREDICT_VISIBLE: boolean
  CHANGE_MODEL_ID: string
  CHANGE_PREDICTION_FIELDS: string[] | null
  CHANGE_AVAILABLE_MODELS: ProviderWithModels[]
}

const initialState = {
  availableModels: [],
  isSettingsOpened: false,
  openedProviderSettings: null,
  isOptimizationOpened: false,
  teacherModel: null,
  studentModel: null,
  evaluationMode: EvaluationModesEnum.none,
  evaluationCriteriaList: [],
  nodesData: null,
  payload: null,
  isTrainingActive: false,
  isPredictVisible: false,
  modelId: null,
  taskDescription: '',
  trainingData: null,
  predictionFields: null,
}

class PromptFusionServiceClass extends Observable<Events> {
  providers = getProviders()
  availableModels: ProviderWithModels[] = initialState.availableModels
  isSettingsOpened = initialState.isSettingsOpened
  openedProviderSettings: ProvidersEnum | null = initialState.openedProviderSettings
  isOptimizationOpened = initialState.isOptimizationOpened
  teacherModel: ProviderModelsEnum | null = initialState.teacherModel
  studentModel: ProviderModelsEnum | null = initialState.studentModel
  evaluationMode: EvaluationModesEnum = initialState.evaluationMode
  evaluationCriteriaList: string[] = initialState.evaluationCriteriaList
  nodesData: PayloadData | null = initialState.nodesData
  payload: PromptFusionPayload | null = initialState.payload
  isTrainingActive = initialState.isTrainingActive
  isPredictVisible = initialState.isPredictVisible
  modelId: string | null = initialState.modelId
  taskDescription = initialState.taskDescription
  trainingData: TrainingData | null = initialState.trainingData
  predictionFields: string[] | null = initialState.predictionFields

  constructor() {
    super()
  }

  openSettings() {
    this.isSettingsOpened = true
    this.emit('CHANGE_SETTINGS_STATUS', true)
  }

  closeSettings() {
    this.isSettingsOpened = false
    this.emit('CHANGE_SETTINGS_STATUS', false)
  }

  openProviderSettings(provider: ProvidersEnum) {
    this.openedProviderSettings = provider
    this.emit('OPEN_PROVIDER_SETTINGS', this.openedProviderSettings)
  }

  updateProviderSettings(provider: ProvidersEnum, settings: ProviderSetting[]) {
    const currentProvider = this.providers.find((prov) => prov.id === provider)
    if (!currentProvider) return
    currentProvider.settings = settings
    currentProvider.status = settings.filter((setting) => setting.required && !setting.value).length
      ? ProviderStatus.disconnected
      : ProviderStatus.connected
    this.changeAvailableModels()
  }

  closeProviderSettings() {
    this.openedProviderSettings = null
    this.emit('CLOSE_PROVIDER_SETTINGS')
  }

  changeOptimizationState(isOpen: boolean) {
    this.isOptimizationOpened = isOpen
    this.emit('CHANGE_OPTIMIZATION_STATE', isOpen)
  }

  changeAvailableModels() {
    this.availableModels = allModels.filter((model) =>
      this.getConnectedProviders().find((provider) => provider.id === model.providerId),
    )
    this.emit('CHANGE_AVAILABLE_MODELS', this.availableModels)
  }

  updateTeacherModel(model: ProviderModelsEnum | null) {
    this.teacherModel = model
    this.emit('CHANGE_TEACHER_MODEL')
  }

  updateStudentModel(model: ProviderModelsEnum | null) {
    this.studentModel = model
    this.emit('CHANGE_STUDENT_MODEL')
  }

  checkIsOptimizationAvailable() {
    if (!this.teacherModel) throw new Error('Teacher model is required!')
    if (!this.studentModel) throw new Error('Student model is required!')
    if (!this.taskDescription) throw new Error('Task description is required!')
    if (this.haveDuplicatedFields())
      throw new Error(
        'Optimization cannot proceed with identical field names in cards. Please review and rename duplicate fields.',
      )
  }

  getProviderSettings(providerId: ProvidersEnum) {
    return this.providers.find((provider) => provider.id === providerId)?.settings || []
  }

  async runOptimization() {
    this.isTrainingActive = true
    this.changeOptimizationState(false)
    this.emit('CHANGE_TRAINING_STATE', this.isTrainingActive)
    const result = await DataProcessingWorker.startTraining(
      { task_spec: this.payload! },
      WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_TRAIN,
    )
    if (result.status === 'success' && result.model_id) {
      this.setModelId(result.model_id)
      this.savePredictionFields()
      this.endTraining()
    } else {
      this.endTraining()
      throw new Error('Training failed')
    }
  }

  prepareData(object: FlowExportObject) {
    this.prepareNodesData(object)
    if (!this.nodesData) throw new Error('Failed to retrieve data')
    const optimizationSettings = {
      taskDescription: this.taskDescription,
      teacher: this.getTeacherProviderData(),
      student: this.getStudentProviderData(),
      evaluationMode: this.evaluationMode,
      criteriaList: this.evaluationCriteriaList,
    }
    const payload = {
      data: this.nodesData as PayloadData,
      settings: optimizationSettings,
      trainingData: this.trainingData,
    }
    this.payload = payload
  }

  endTraining() {
    this.isTrainingActive = false
    this.emit('CHANGE_TRAINING_STATE', this.isTrainingActive)
  }

  togglePredict() {
    this.isPredictVisible = !this.isPredictVisible
    this.emit('CHANGE_PREDICT_VISIBLE', this.isPredictVisible)
  }

  saveTrainingData(data: object, inputFields: string[], outputFields: string[]) {
    this.trainingData = { data, inputFields, outputFields }
  }

  resetState() {
    this.providers = getProviders()
    this.availableModels = initialState.availableModels
    this.isSettingsOpened = initialState.isSettingsOpened
    this.openedProviderSettings = initialState.openedProviderSettings
    this.isOptimizationOpened = initialState.isOptimizationOpened
    this.teacherModel = initialState.teacherModel
    this.studentModel = initialState.studentModel
    this.evaluationMode = initialState.evaluationMode
    this.evaluationCriteriaList = initialState.evaluationCriteriaList
    this.nodesData = initialState.nodesData
    this.payload = initialState.payload
    this.isTrainingActive = initialState.isTrainingActive
    this.isPredictVisible = initialState.isPredictVisible
    this.modelId = initialState.modelId
    this.taskDescription = initialState.taskDescription
    this.trainingData = initialState.trainingData
    this.predictionFields = initialState.predictionFields
  }

  getConnectedProviders() {
    return this.providers.filter((provider) => {
      if (provider.disabled) return false
      return provider.status === ProviderStatus.connected
    })
  }

  private haveDuplicatedFields() {
    return this.nodesData?.nodes.find((node) => {
      const values = node.data.fields.map((field) => field.value)
      return values.length !== new Set(values).size
    })
  }

  private prepareNodesData(object: FlowExportObject) {
    const edges = this.getEdgesFromObject(object)
    const nodes: PayloadNode[] = object.nodes.map((node) => {
      const nodeData = node.data as NodeData
      const data = {
        fields: this.getFieldsDataFromNodeData(nodeData),
        hint: nodeData.hint,
        type: nodeData.type,
        label: nodeData.label,
      }
      return { id: node.id, data }
    })
    this.nodesData = { edges, nodes }
  }

  private getEdgesFromObject(object: FlowExportObject) {
    return object.edges.map((edge) => ({
      id: edge.id,
      sourceNode: edge.source,
      sourceField: edge.sourceHandle!,
      targetNode: edge.target,
      targetField: edge.targetHandle!,
    }))
  }

  private getFieldsDataFromNodeData(nodeData: NodeData) {
    return nodeData.fields.map((field) => ({
      id: field.id,
      value: field.value,
      variant: field.variant,
      type: field.type!,
      variadic: !!field.variadic,
    }))
  }

  private getTeacherProviderData() {
    if (!this.teacherModel) throw new Error('Select teacher model before')
    const teacherProviderId = allModels.find((item) =>
      item.items.find((model) => model.id === this.teacherModel),
    )?.providerId
    const teacherProviderSettings = teacherProviderId
      ? this.getProviderSettings(teacherProviderId)
      : null
    const settingsObject = parseProviderSettingsToObject(teacherProviderSettings)
    return {
      providerId: teacherProviderId!,
      modelId: this.teacherModel,
      providerSettings: settingsObject,
    }
  }

  private getStudentProviderData() {
    if (!this.studentModel) throw new Error('Select student model before')
    const studentProviderId = allModels.find((item) =>
      item.items.find((model) => model.id === this.studentModel),
    )?.providerId
    const studentProviderSettings = studentProviderId
      ? this.getProviderSettings(studentProviderId)
      : null
    const settingsObject = parseProviderSettingsToObject(studentProviderSettings)
    return {
      providerId: studentProviderId!,
      modelId: this.studentModel,
      providerSettings: settingsObject,
    }
  }

  private setModelId(modelId: string) {
    this.modelId = modelId
    this.emit('CHANGE_MODEL_ID', this.modelId)
  }

  private savePredictionFields() {
    if (!this.nodesData) throw new Error('Create nodes data first')
    const fields = this.nodesData.nodes.reduce((acc: string[], node) => {
      node.data.fields.forEach((field) => {
        if (field.variant === 'input') acc.push(field.value)
      })
      return acc
    }, [])
    if (fields.length) {
      this.predictionFields = fields
      this.emit('CHANGE_PREDICTION_FIELDS', this.predictionFields)
    }
  }
}

export const promptFusionService = new PromptFusionServiceClass()
