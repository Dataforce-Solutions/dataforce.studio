import { ProviderModelsEnum, ProvidersEnum, ProviderStatus, type BaseProviderInfo, type ProviderModel, type ProviderWithModels } from './prompt-fusion.interfaces'
import OpenAi from '@/assets/img/providers/open-ai.svg'
import Ollama from '@/assets/img/providers/ollama.svg'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import GptModel from '@/assets/img/providers/gpt-model.svg'
import OllamaModel from '@/assets/img/providers/ollama-model.svg'

export const getProviders = (): BaseProviderInfo[] => {
  const settings = LocalStorageService.getProviderSettings()
  const savedOpenAiSettings = settings[ProvidersEnum.openAi]
  const savedOllamaSettings = settings[ProvidersEnum.ollama]
  return [
    {
      id: ProvidersEnum.openAi,
      image: OpenAi,
      name: 'OpenAI',
      status: ProviderStatus.connected,
      settings: [
        {
          id: 'apiKey',
          label: 'API Key',
          required: true,
          placeholder: 'Enter your API Key',
          value: savedOpenAiSettings?.apiKey || '',
        },
        {
          id: 'organization',
          label: 'Organization',
          required: false,
          placeholder: 'Enter your Organization ID',
          value: savedOpenAiSettings?.organization || '',
        },
        {
          id: 'apiBase',
          label: 'API Base',
          required: false,
          placeholder: 'Enter your API Base',
          value: savedOpenAiSettings?.apiBase || '',
        },
      ],
    },
    {
      id: ProvidersEnum.ollama,
      image: Ollama,
      name: 'Ollama',
      status: ProviderStatus.connected,
      settings: [
        {
          id: 'apiKey',
          label: 'API Key',
          required: true,
          placeholder: 'Enter your API Key',
          value: savedOllamaSettings?.apiKey || '',
        },
      ],
    },
  ]
}

export const openAiModels: ProviderModel[] = [
  {
    id: ProviderModelsEnum.gpt,
    label: 'gpt-3.5-turbo-0125',
    icon: GptModel,
  },
]

export const ollamaModels: ProviderModel[] = [
  {
    id: ProviderModelsEnum.llama,
    label: 'Llama 3.1',
    icon: OllamaModel,
  },
]

export const getAllModels = (): ProviderWithModels[] => {
  const openAi = { label: 'OpenAi', providerId: ProvidersEnum.openAi, items: openAiModels }
  const ollama = { label: 'Ollama', providerId: ProvidersEnum.ollama, items: ollamaModels }
  return [openAi, ollama]
}

export const allModels = getAllModels()
