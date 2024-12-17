<template>
  <div class="content">
    <p class="text">Get predictions by entering data manually or uploading a dataset</p>
    <SelectButton class="select" v-model="selectValue" :options="selectOptions" />
    <div v-if="selectValue === 'Manual'" class="manual">
      <div class="inputs">
        <div v-for="field in Object.keys(manualValues)" class="input-wrapper">
          <d-float-label variant="on">
            <d-input-text
              v-model="manualValues[field as keyof typeof manualValues]"
              :id="field"
              fluid
            />
            <label class="label" :for="field">{{ field }}</label>
          </d-float-label>
        </div>
      </div>
      <d-button label="Predict" type="submit" fluid @click="onManualSubmit" />
      <div class="input-wrapper">
        <d-float-label variant="on">
          <Textarea v-model="predictionText" id="prediction" fluid rows="4" />
          <label class="label" for="prediction">Prediction</label>
        </d-float-label>
      </div>
    </div>
    <div v-else class="upload">
      <file-input
        id="predict"
        :file="fileData"
        :error="isUploadWithErrors"
        @selectFile="onSelectFile"
      />
      <d-button label="Predict" type="submit" fluid @click="onManualSubmit" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import SelectButton from 'primevue/selectbutton'
import { Textarea } from 'primevue'
import FileInput from '../ui/FileInput.vue'
import { useDataTable } from '@/hooks/useDataTable'

type Props = {
  manualFields: string[]
}

const props = defineProps<Props>()

const { isUploadWithErrors, fileData, onSelectFile } = useDataTable()

const selectValue = ref<'Manual' | 'Upload file'>('Manual')
const selectOptions = ref(['Manual', 'Upload file'])
const manualValues = ref(
  props.manualFields.reduce((acc, field) => {
    // @ts-ignore
    acc[field] = ''

    return acc
  }, {}),
)
const predictionText = ref('')

function onManualSubmit() {
  console.log(manualValues.value)
  console.log(predictionText.value)
}
</script>

<style scoped>
.text {
  margin-bottom: 32px;
  color: var(--p-text-muted-color);
}

.select {
  margin-bottom: 32px;
}

.manual {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.upload {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-height: 316px;
  overflow-y: auto;
}
</style>
