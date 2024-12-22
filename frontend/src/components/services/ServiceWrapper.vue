<template>
  <Stepper :value="currentStep" class="stepper" @update:value="(step) => (currentStep = step)">
    <StepList>
      <Step
        v-for="step in steps"
        :key="step.id"
        :value="step.id"
        :disabled="!isStepAvailable(step.id)"
        >{{ step.text }}</Step
      >
    </StepList>
    <StepPanels>
      <StepPanel v-slot="{ activateCallback }" :value="1">
        <upload-data
          v-if="currentStep === 1"
          :errors="uploadDataErrors"
          :is-table-exist="isTableExist"
          :file="fileData"
          @selectFile="onSelectFile"
          @removeFile="onRemoveFile"
        />
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="$router.push({ name: 'home' })" />
          <d-button :disabled="!isStepAvailable(2)" @click="activateCallback(2)">
            <span style="font-weight: 500">Continue</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel v-slot="{ activateCallback }" :value="2">
        <table-view
          v-if="currentStep === 2 && columnsCount && rowsCount && viewValues"
          :columns-count="columnsCount"
          :rows-count="rowsCount"
          :all-columns="getAllColumnNames"
          :value="viewValues"
          :target="getTarget"
          :group="getGroup"
          :selected-columns="selectedColumns"
          :export-callback="downloadCSV"
          :filters="getFilters"
          :columnTypes="columnTypes"
          @set-target="setTarget"
          @change-group="changeGroup"
          @edit="setSelectedColumns"
          @change-filters="setFilters"
        />
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="activateCallback(1)" />
          <d-button :disabled="!isStepAvailable(3)" @click="onStep2ContinueClick">
            <span style="font-weight: 500">Continue</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel :value="3">
        <service-evaluate
          v-if="currentStep === 3"
          :selected-columns="selectedColumns.length ? selectedColumns : getAllColumnNames"
        />
      </StepPanel>
    </StepPanels>
  </Stepper>
  <d-dialog v-model:visible="training" modal :closable="false" :closeOnEscape="false">
    <template #container>
      <training-progress :time="8" />
    </template>
  </d-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import StepPanels from 'primevue/steppanels'
import Step from 'primevue/step'
import StepPanel from 'primevue/steppanel'
import { ArrowRight } from 'lucide-vue-next'

import UploadData from './UploadData.vue'
import ServiceEvaluate from './ServiceEvaluate.vue'
import TableView from './TableView.vue'
import TrainingProgress from './TrainingProgress.vue'

import { useDataTable } from '@/hooks/useDataTable'

type TProps = {
  steps: {
    id: number
    text: string
  }[]
}

defineProps<TProps>()

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {
    size: !!(size && size > 1024 * 1024),
    columns: !!(columns && columns <= 3),
    rows: !!(rows && rows <= 100),
  }
}

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
} = useDataTable(tableValidator)

const currentStep = ref(1)
const training = ref(false)
const trainingResult = ref(null)

const isStepAvailable = computed(() => (id: number) => {
  if (id === 1) return true
  if (id === 2) return isTableExist.value && !isUploadWithErrors.value
  if (id === 3) return isTableExist.value && !isUploadWithErrors.value // trainingResult.value
})

function startTraining() {
  training.value = true
}
function onStep2ContinueClick() {
  startTraining()
}
</script>

<style scoped>
.stepper {
  padding-top: 17px;
}

.navigation {
  display: flex;
  gap: 24px;
  justify-content: flex-end;
}

@media (max-width: 968px) {
  .navigation {
    position: fixed;
    bottom: 0;
    right: 0;
    background-color: var(--p-content-background);
    padding-top: 4px;
    padding-bottom: 44px;
    padding-right: 100px;
    width: 100%;
    z-index: 5;
  }
}
</style>
