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
    <step-edit v-else-if="step === 2 && columnsCount && rowsCount && viewValues" @back="step = 1" @continue="goToMainStep">
      <table-view
        :columns-count="columnsCount"
        :rows-count="rowsCount"
        :all-columns="getAllColumnNames"
        :value="viewValues"
        :selected-columns="selectedColumns"
        :export-callback="downloadCSV"
        :columnTypes="columnTypes"
        :inputs-outputs-columns="inputsOutputsColumns"
        show-column-header-menu
        @edit="setSelectedColumns"
      />
    </step-edit>
    <step-main v-else-if="step === 3" :initial-nodes="initialNodes" @go-back="backFromMain"/>
  </div>
</template>

<script setup lang="ts">
import { onBeforeMount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StepMain from '@/components/prompt-fusion/step-main/index.vue'
import UploadData from '@/components/ui/UploadData.vue'
import { useDataTable } from '@/hooks/useDataTable'
import { promptFusionResources } from '@/constants/constants'
import FirstStepNavigation from '@/components/prompt-fusion/step-upload/Navigation.vue'
import { initialNodes as defaultInitialNodes, getInitialNodes } from '@/constants/prompt-fusion'
import TableView from '@/components/table-view/index.vue'
import StepEdit from '@/components/prompt-fusion/step-edit/StepEdit.vue'

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {
    size: !!(size && size > 50 * 1024 * 1024),
    columns: !!(columns && columns <= 2),
    rows: !!(rows && rows <= 100),
  }
}

const route = useRoute()
const router = useRouter()
const {
  isTableExist,
  fileData,
  uploadDataErrors,
  isUploadWithErrors,
  columnsCount,
  rowsCount,
  getAllColumnNames,
  viewValues,
  selectedColumns,
  columnTypes,
  inputsOutputsColumns,
  getInputsColumns,
  getOutputsColumns,
  onSelectFile,
  onRemoveFile,
  setSelectedColumns,
  downloadCSV,
} = useDataTable(tableValidator)

const step = ref<number>()

const initialNodes = ref(defaultInitialNodes)

function backFromMain() {
  if (route.params.mode === 'data-driven') step.value = 2
  else router.back()
}
function goToMainStep() {
  initialNodes.value = getInitialNodes(getInputsColumns.value, getOutputsColumns.value)
  step.value = 3
}

onBeforeMount(() => {
  step.value = route.params.mode === 'data-driven' ? 1 : 3
})
</script>

<style scoped></style>
