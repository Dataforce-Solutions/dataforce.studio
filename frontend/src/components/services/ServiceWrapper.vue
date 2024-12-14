<template>
  <Stepper :value="1" class="stepper">
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
        <div class="flex flex-col h-48">
          <div
            class="border-2 border-dashed border-surface-200 dark:border-surface-700 rounded bg-surface-50 dark:bg-surface-950 flex-auto flex justify-center items-center font-medium"
          >
            Content II
          </div>
        </div>
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="activateCallback(1)" />
          <d-button :disabled="!isStepAvailable(3)" @click="activateCallback(3)">
            <span style="font-weight: 500">Continue</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel v-slot="{ activateCallback }" :value="3">
        <div class="flex flex-col h-48">
          <div
            class="border-2 border-dashed border-surface-200 dark:border-surface-700 rounded bg-surface-50 dark:bg-surface-950 flex-auto flex justify-center items-center font-medium"
          >
            Content III
          </div>
        </div>
        <div class="pt-6">
          <d-button
            label="Back"
            severity="secondary"
            icon="pi pi-arrow-left"
            @click="activateCallback(2)"
          />
        </div>
      </StepPanel>
    </StepPanels>
  </Stepper>
</template>

<script setup lang="ts">
import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import StepPanels from 'primevue/steppanels'
import StepItem from 'primevue/stepitem'
import Step from 'primevue/step'
import StepPanel from 'primevue/steppanel'
import { ArrowRight } from 'lucide-vue-next'
import UploadData from './UploadData.vue'
import { computed } from 'vue'

import { useDataTable } from '@/hooks/useDataTable'

type TProps = {
  steps: {
    id: number
    text: string
  }[]
}

defineProps<TProps>()

const { isTableExist, fileData, uploadDataErrors, isUploadWithErrors, onSelectFile, onRemoveFile } =
  useDataTable()

const isStepAvailable = computed(() => (id: number) => {
  if (id === 1) return true
  if (id === 2) return isTableExist.value && !isUploadWithErrors.value
})
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
