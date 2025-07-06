import type {
  MlModel,
  MlModelCreator,
  UpdateMlModelPayload,
} from '@/lib/api/orbit-ml-models/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { dataforceApi } from '@/lib/api'
import axios from 'axios'
import { useRoute } from 'vue-router'
import { downloadFileFromBlob } from '@/helpers/helpers'

export const useModelsStore = defineStore('models', () => {
  const route = useRoute()

  const modelsList = ref<MlModel[]>([])

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string') throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Current orbit not found')
    if (typeof route.params.collectionId !== 'string') throw new Error('Current collection not found')

    return {
      organizationId: +route.params.organizationId,
      orbitId: +route.params.id,
      collectionId: +route.params.collectionId,
    }
  })

  async function loadModelsList() {
    modelsList.value = await dataforceApi.mlModels.getModelsList(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
    )
  }

  function initiateCreateModel(data: MlModelCreator) {
    return dataforceApi.mlModels.createModel(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      data,
    )
  }

  async function confirmModelUpload(payload: UpdateMlModelPayload) {
    const model = await dataforceApi.mlModels.updateModel(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      payload.id,
      payload,
    )
    modelsList.value.push(model)
  }

  async function cancelModelUpload(payload: UpdateMlModelPayload) {
    await dataforceApi.mlModels.updateModel(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      payload.id,
      payload,
    )
  }

  function resetList() {
    modelsList.value = []
  }

  async function deleteModels(modelsIds: number[]) {
    const deleted: number[] = []
    const failed: number[] = []
    for (let i = modelsIds.length - 1; i >= 0; i--) {
      const id = modelsIds[i]
      try {
        await deleteModel(id)

        deleted.push(id)
      } catch (error) {
        failed.push(id)
      }
    }
    modelsList.value = modelsList.value.filter((model) => !deleted.includes(model.id))
    return { deleted, failed }
  }

  async function deleteModel(modelId: number) {
    const { url } = await dataforceApi.mlModels.getModelDeleteUrl(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      modelId,
    )
    await axios.delete(url)
    await dataforceApi.mlModels.confirmModelDelete(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      modelId,
    )
  }

  async function downloadModel(modelId: number, name: string) {
    const { url } = await dataforceApi.mlModels.getModelDownloadUrl(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      modelId,
    )
    const response = await fetch(url)
    const blob = await response.blob()
    downloadFileFromBlob(blob, name)
  }

  return {
    modelsList,
    initiateCreateModel,
    confirmModelUpload,
    loadModelsList,
    cancelModelUpload,
    resetList,
    deleteModels,
    downloadModel,
  }
})
