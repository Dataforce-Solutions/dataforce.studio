import { Model } from '@fnnx/web'
import { computed, ref } from 'vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, Tasks } from '@/lib/data-processing/interfaces'
import { FnnxService } from '@/lib/fnnx/FnnxService';

const availableTags = [FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1, FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1];

export const useFnnxModel = () => {
  const model = ref<Model | null>(null)
  const currentTask = ref<Tasks | null>(null)

  const getModel = computed(() => model.value)

  async function createModelFromFile(file: File) {
    if (!file.name.endsWith('.dfs')) throw new Error('Incorrect file format')
    const buffer = await file.arrayBuffer()
    model.value = await Model.fromBuffer(buffer)
    currentTask.value = FnnxService.getModelTask(model.value as Model, availableTags)
    await model.value.warmup()
  }
  function removeModel() {
    model.value = null
  }

  return { currentTask, getModel, createModelFromFile, removeModel }
}
