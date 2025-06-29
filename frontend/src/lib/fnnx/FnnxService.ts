import { Model } from '@fnnx/web'
import {
  FNNX_PRODUCER_TAGS_MANIFEST_ENUM,
  FNNX_PRODUCER_TAGS_METADATA_ENUM,
  Tasks,
} from '../data-processing/interfaces'

class FnnxServiceClass {
  async createModelFromFile(file: File) {
    if (!file.name.endsWith('.dfs')) throw new Error('Incorrect file format')
    const buffer = await file.arrayBuffer()
    return Model.fromBuffer(buffer)
  }

  getModelMetrics(model: Model, availableTags: FNNX_PRODUCER_TAGS_METADATA_ENUM[]) {
    const metadata = model.getMetadata()
    for (const meta of metadata) {
      const tag = meta.producer_tags.find((tag: FNNX_PRODUCER_TAGS_METADATA_ENUM) =>
        availableTags.includes(tag),
      )
      if (tag) return meta.payload.metrics
    }
    return null
  }

  getModelTask(model: Model, availableTags: FNNX_PRODUCER_TAGS_MANIFEST_ENUM[]) {
    const manifest = model.getManifest()
    const tag = manifest.producer_tags.find((tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) =>
      availableTags.includes(tag),
    )
    if (tag) {
      switch (tag) {
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1:
          return Tasks.TABULAR_CLASSIFICATION
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1:
          return Tasks.TABULAR_REGRESSION
        default:
          return null
      }
    }
    return null
  }
}

export const FnnxService = new FnnxServiceClass()
