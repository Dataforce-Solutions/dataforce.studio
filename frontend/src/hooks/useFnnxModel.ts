import { Model } from '@fnnx/web'
import { computed, ref } from 'vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, Tasks } from '@/lib/data-processing/interfaces'

const availableTags = [FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1, FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1];

export const useFnnxModel = () => {
  const model = ref<Model | null>(null)
  const currentTask = ref<Tasks | null>(null)

  const getModel = computed(() => model.value)

  async function createModelFromFile(file: File) {
    if (!file.name.endsWith('.dfs')) throw new Error('Incorrect file format')
    const buffer = await file.arrayBuffer()
    model.value = await Model.fromBuffer(buffer)
    const manifest = model.value.getManifest()
    const tag = manifest.producer_tags.find((tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) => availableTags.includes(tag))
    if (tag) {
      switch (tag) {
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1:
          currentTask.value = Tasks.TABULAR_CLASSIFICATION
          break
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1:
          currentTask.value = Tasks.TABULAR_REGRESSION
          break
      }
      model.value.warmup()
    }
  }
  function removeModel() {
    model.value = null
  }

  return { currentTask, getModel, createModelFromFile, removeModel }
}
