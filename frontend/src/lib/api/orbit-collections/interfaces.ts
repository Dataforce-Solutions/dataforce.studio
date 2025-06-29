export enum OrbitCollectionTypeEnum {
  model = 'model',
  dataset = 'dataset',
}

export interface OrbitCollection {
  id: number
  orbit_id: number
  description: string
  name: string
  collection_type: OrbitCollectionTypeEnum
  tags: string[]
  total_models: number
  created_at: Date
  updated_at: Date
}

export interface OrbitCollectionCreator {
  description: string
  name: string
  collection_type?: OrbitCollectionTypeEnum
  tags: string[]
}
