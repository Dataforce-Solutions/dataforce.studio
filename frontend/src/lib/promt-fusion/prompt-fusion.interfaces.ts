import type { FieldVariant, NodeTypeEnum, PromptFieldTypeEnum } from "@/components/services/prompt-fusion/interfaces"

export interface BaseProviderInfo {
  id: ProvidersEnum
  image: string
  name: string
  status: ProviderStatus
  settings: ProviderSetting[]
}

export enum ProvidersEnum {
  openAi = 'openAi',
  ollama = 'ollama',
}

export enum ProviderModelsEnum {
  gpt = 'gpt',
  llama = 'llama',
}

export enum ModelTypeEnum {
  teacher = 'teacher',
  student = 'student',
}

export enum ProviderStatus {
  connected = 'connected',
  disconnected = 'disconnected',
}

export enum EvaluationModesEnum {
  exactMatch = 'Exact match',
  llmBased = 'LLM-based',
}

export interface ProviderSetting {
  id: string
  label: string
  required: boolean
  placeholder: string
  value: string
}

export interface ProviderModel {
  id: ProviderModelsEnum
  label: string
  icon: string
}

export interface ProviderWithModels {
  label: string;
  providerId: ProvidersEnum;
  items: ProviderModel[];
}

export interface PromptFusionPayload {
  data: PayloadData
  settings: PayloadSettings
  trainingData: object | null
}

export interface PayloadData {
  edges: PayloadEdge[]
  nodes: PayloadNode[]
}

export interface PayloadEdge {
  id: string
  sourceNode: string
  sourceField: string
  targetNode: string
  targetField: string
}

export interface PayloadNode {
  id: string
  data: PayloadNodeData
}

export interface PayloadNodeData {
  fields: PayloadNodeField[]
  type: NodeTypeEnum
  hint?: string
}

export interface PayloadNodeField {
  id: string
  value: string
  variant: FieldVariant
  type: PromptFieldTypeEnum
  variadic?: boolean
}

export interface PayloadSettings {
  taskDescription: string
  teacher: PayloadProviderData
  student: PayloadProviderData
  evaluationMode: EvaluationModesEnum
  criteriaList: string[]
}

export interface PayloadProviderData {
  providerId: ProvidersEnum
  modelId: ProviderModelsEnum
  providerSettings: Record<string, string>
}
