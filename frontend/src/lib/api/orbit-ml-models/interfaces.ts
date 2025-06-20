export enum MlModelStatusEnum {
  pending_upload = 'pending_upload',
  uploaded = 'uploaded',
  pending_deletion = 'pending_deletion',
}

export interface MlModelCreator {
  metrics: Record<string, object>
  manifest: Record<string, object>
  file_hash: string
  size: number
  file_name: string
  tags: string[]
}

export interface MlModel {
  id: number
  collection_id: number
  metrics: {
    additionalProp1: {}
  }
  manifest: {
    additionalProp1: {}
  }
  file_hash: string
  bucket_location: string
  size: number
  unique_identifier: string
  tags: string[]
  status: MlModelStatusEnum
  created_at: Date
  updated_at: Date
}

export interface UpdateMlModelPayload {
  id: number,
  tags: string[],
}
