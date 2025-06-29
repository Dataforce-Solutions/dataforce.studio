import { TarHandler } from '@/lib/tar-handler/TarHandler'
import { useModelsStore } from '@/stores/models'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { FNNX_PRODUCER_TAGS_METADATA_ENUM } from '@/lib/data-processing/interfaces'
import {
  MlModelStatusEnum,
  type CreateModelResponse,
  type MlModelCreator,
  type UpdateMlModelPayload,
} from '@/lib/api/orbit-ml-models/interfaces'
import { getSha256 } from '@/helpers/helpers'
import axios, { type AxiosProgressEvent } from 'axios'
import { ref } from 'vue'

const AVAILABLE_TAGS = [
  FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_classification_metrics_v1,
  FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_regression_metrics_v1,
]

export const useModelUpload = () => {
  const modelsStore = useModelsStore()

  const progress = ref<number | null>(null)

  async function upload(file: File, name: string, description: string, tags: string[]) {
    const model = await FnnxService.createModelFromFile(file)
    const manifest = model.getManifest()
    const modelBuffer = await file.arrayBuffer()
    const fileIndex = new TarHandler(modelBuffer).scan()
    const metrics = FnnxService.getModelMetrics(model, AVAILABLE_TAGS)
    const fileHash = await getSha256(modelBuffer)

    const payload: MlModelCreator = {
      metrics: {},
      manifest,
      file_index: Object.fromEntries(fileIndex.entries()),
      file_hash: fileHash,
      size: file.size,
      file_name: name,
      description,
      tags,
    }
    const response = await modelsStore.initiateCreateModel(payload)

    await uploadToBucket(response, modelBuffer, name, description, tags)

    const confirmPayload: UpdateMlModelPayload = {
      id: response.model.id,
      file_name: name,
      description,
      tags,
      status: MlModelStatusEnum.uploaded,
    }
    return modelsStore.confirmModelUpload(confirmPayload)
  }

  async function uploadToBucket(
    data: CreateModelResponse,
    buffer: ArrayBuffer,
    fileName: string,
    description: string,
    tags: string[],
  ) {
    try {
      progress.value = 0
      await axios.put(data.url, buffer, {
        headers: { 'Content-Type': 'application/octet-stream' },
        onUploadProgress,
      })
    } catch (e) {
      await modelsStore.cancelModelUpload({
        id: data.model.id,
        file_name: fileName,
        description,
        tags,
        status: MlModelStatusEnum.upload_failed,
      })
      throw e
    } finally {
      progress.value = null
    }
  }

  function onUploadProgress(event: AxiosProgressEvent) {
    if (event.total) {
      const percentCompleted = Math.round((event.loaded * 100) / event.total)
      progress.value = percentCompleted
    }
  }

  return { progress, upload }
}
