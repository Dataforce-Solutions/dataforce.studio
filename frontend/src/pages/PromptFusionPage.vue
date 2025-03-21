<template>
  <div class="prompt-fusion-page">
    <div v-if="step === 1">
      <upload-data
        :errors="uploadDataErrors"
        :is-table-exist="isTableExist"
        :file="fileData"
        :min-columns-count="2"
        :resources="promptFusionResources"
        sample-file-name="iris.csv"
        @selectFile="onSelectFile"
        @removeFile="onRemoveFile"
      />
      <first-step-navigation :is-next-step-available="!!fileData.name && !isUploadWithErrors" @continue="step = 2"/>
    </div>
    <div v-else-if="step === 2">There will be a table with data here</div>
    <step-main v-else-if="step === 3" :initial-nodes="initialNodes"/>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from 'vue'
import { useRoute } from 'vue-router'
import StepMain from '@/components/prompt-fusion/step-main/index.vue'
import UploadData from '@/components/ui/UploadData.vue'
import { useDataTable } from '@/hooks/useDataTable'
import { promptFusionResources } from '@/constants/constants'
import FirstStepNavigation from '@/components/prompt-fusion/step-upload/Navigation.vue'
import { initialNodes as defaultInitialNodes } from '@/constants/prompt-fusion'

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {
    size: !!(size && size > 1024 * 1024),
    columns: !!(columns && columns <= 2),
    rows: !!(rows && rows <= 100),
  }
}

const route = useRoute()
const {
  isTableExist,
  fileData,
  uploadDataErrors,
  isUploadWithErrors,
  columnsCount,
  rowsCount,
  getAllColumnNames,
  viewValues,
  getTarget,
  getGroup,
  selectedColumns,
  getFilters,
  columnTypes,
  onSelectFile,
  onRemoveFile,
  setTarget,
  changeGroup,
  setSelectedColumns,
  downloadCSV,
  setFilters,
  getDataForTraining,
} = useDataTable(tableValidator)

const step = ref<number>()

const initialNodes = computed(() => defaultInitialNodes)

onBeforeMount(() => {
  if (route.params.mode === 'data-driven') {
    step.value = 1
  } else {
    step.value = 3
  }
})
</script>

<style scoped></style>
