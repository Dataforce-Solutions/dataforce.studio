import type { AxiosInstance } from 'axios'
import type { CreateModelResponse, MlModel, MlModelCreator, UpdateMlModelPayload } from './interfaces'

export class MlModelsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async createModel(organizationId: number, orbitId: number, collectionId: number, data: MlModelCreator) {
    const { data: responseData } = await this.api.post<CreateModelResponse>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/ml-models`, data)
    return responseData
  }

  async getModelsList(organizationId: number, orbitId: number, collectionId: number) {
    const { data: responseData } = await this.api.get<MlModel[]>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/ml-models`)
    return responseData
  }

  async updateModel(organizationId: number, orbitId: number, collectionId: number, modelId: number, data: UpdateMlModelPayload) {
    const { data: responseData } = await this.api.patch<MlModel>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/ml-models/${modelId}`, data)
    return responseData
  }

  async getModelDownloadUrl(organizationId: number, orbitId: number, collectionId: number, modelId: number) {
    const { data: responseData } = await this.api.get<{ url: string }>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/ml-models/${modelId}/download-url`)
    return responseData
  }

  async getModelDeleteUrl(organizationId: number, orbitId: number, collectionId: number, modelId: number) {
    const { data: responseData } = await this.api.get<{ url: string }>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/ml-models/${modelId}/delete-url`)
    return responseData
  }

  async confirmModelDelete(organizationId: number, orbitId: number, collectionId: number, modelId: number) {
    const { data: responseData } = await this.api.delete(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/ml-models/${modelId}`)
    return responseData
  }
}
