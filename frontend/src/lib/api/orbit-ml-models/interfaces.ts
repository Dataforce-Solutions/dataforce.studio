export enum MlModelStatusEnum {
  pending_upload = 'pending_upload',
  uploaded = 'uploaded',
  pending_deletion = 'pending_deletion',
  upload_failed = 'upload_failed',
  deletion_failed = 'deletion_failed',
}

export interface MlModelCreator {
  metrics: Record<string, object>
  manifest: Record<string, object>
  file_index: Record<string, object>
  file_hash: string
  size: number
  file_name: string
  description: string
  tags: string[]
}

export interface MlModel {
  id: number
  collection_id: number
  file_name: string
  description: string
  metrics: Record<string, object>
  manifest: Record<string, object>
  file_hash: string
  file_index: Record<string, object>
  bucket_location: string
  size: number
  unique_identifier: string
  tags: string[]
  status: MlModelStatusEnum
  created_at: Date
  updated_at: Date
}

export interface UpdateMlModelPayload {
  id: number
  file_name: string
  description: string
  tags: string[]
  status: MlModelStatusEnum
}

export interface CreateModelResponse {
  model: MlModel
  url: string
}
