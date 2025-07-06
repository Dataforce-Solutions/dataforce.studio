import { Model } from '@fnnx/web'
import {
  Tasks,
} from '../data-processing/interfaces'


export enum FNNX_PRODUCER_TAGS_METADATA_ENUM {
  contains_classification_metrics_v1 = 'falcon.beastbyte.ai::tabular_classification_metrics:v1',
  contains_regression_metrics_v1 = 'falcon.beastbyte.ai::tabular_regression_metrics:v1',
  contains_registry_metricss_v1 = 'dataforce.studio::registry_metrics:v1',
}

export enum FNNX_PRODUCER_TAGS_MANIFEST_ENUM {
  tabular_classification_v1 = "dataforce.studio::tabular_classification:v1",
  tabular_regression_v1 = "dataforce.studio::tabular_regression:v1",
}

class FnnxServiceClass {
  async createModelFromFile(file: File) {
    const allowedExtensions = ['.fnnx', '.pyfnx', '.dfs']
    if (!allowedExtensions.some(ext => file.name.endsWith(ext))) {
      throw new Error('Incorrect file format');
    }
    const buffer = await file.arrayBuffer()
    return Model.fromBuffer(buffer)
  }

  getRegistryMetrics(model: Model) {
    // extract the metrics to be used in the registry
    const tag = this.getTypeTag(model)
    if (tag) {
      switch (tag) {
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1:
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1:
          const tabularMetrics = this.getTabularMetadata(model)
          const tabularEvalMetrics = tabularMetrics.performance.eval_holdout || tabularMetrics.performance.eval_cv || {}
          return Object.fromEntries(
            Object.entries(tabularEvalMetrics).filter(([key, value]) => key !== "N_SAMPLES")
          );
      }
    }
    const customMetrics = this.getMetadataByTag(model, [FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_registry_metricss_v1])
    if (customMetrics) {
      return customMetrics.metrics || {}
    }
    return {}
  }

  getMetadataByTag(model: Model, availableTags: FNNX_PRODUCER_TAGS_METADATA_ENUM[]) {
    // extracts the first available metadata entry that a metadata tag
    const metadata = model.getMetadata()
    for (const meta of metadata) {
      const tag = meta.producer_tags.find((tag) =>
        availableTags.includes(tag as FNNX_PRODUCER_TAGS_METADATA_ENUM),
      )
      if (tag) return meta.payload
    }
    return null
  }

  getTabularMetadata(model: Model) {
    const availableTags = [FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_classification_metrics_v1, FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_regression_metrics_v1]
    return this.getMetadataByTag(model, availableTags)?.metrics || null
  }

  getTypeTag(model: Model) {
    // extracts the extract tag that is used to determine the type of the model
    const availableTags = Object.values(FNNX_PRODUCER_TAGS_MANIFEST_ENUM)
    const manifest = model.getManifest()
    const tag = manifest.producer_tags.find((tag) =>
      availableTags.includes(tag as FNNX_PRODUCER_TAGS_MANIFEST_ENUM),
    )
    return tag || null
  }

  getStudioTask(model: Model) { // TODO: get rid of this completely, use type tag instead as it is more robust
    // determines the DFS task based on the type tag
    const tag = this.getTypeTag(model)
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
