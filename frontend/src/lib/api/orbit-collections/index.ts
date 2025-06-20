import type { AxiosInstance } from 'axios'
import type { BaseDetailResponse } from '../DataforceApi.interfaces'
import type { OrbitCollection, OrbitCollectionCreator } from './interfaces'

export class OrbitCollectionsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getCollectionsList(organizationId: number, orbitId: number) {
    const { data: responseData } = await this.api.get<OrbitCollection[]>(`/organizations/${organizationId}/orbits/${orbitId}/collections`)
    return responseData
  }

  async createCollection(organizationId: number, orbitId: number, data: OrbitCollectionCreator) {
    const { data: responseData } = await this.api.post<OrbitCollection>(`/organizations/${organizationId}/orbits/${orbitId}/collections`, data)
    return responseData
  }

  async updateCollection(organizationId: number, orbitId: number, collectionId: number, data: Omit<OrbitCollectionCreator, 'collection_type'>) {
    const { data: responseData } = await this.api.patch<OrbitCollection>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`, data)
    return responseData
  }

  async deleteCollection(organizationId: number, orbitId: number, collectionId: number) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(`/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`)
    return responseData
  }
}
