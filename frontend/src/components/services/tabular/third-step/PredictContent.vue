<template>
  <div class="content" :class="{ disabled: isLoading }">
    <p class="text">Get predictions by entering data manually or uploading a dataset</p>
    <SelectButton v-model="selectValue" :options="selectOptions" />
    <div v-if="selectValue === 'Manual'" class="manual">
      <div class="inputs">
        <div v-for="field in Object.keys(manualValues)" class="input-wrapper">
          <d-float-label variant="on">
            <d-input-text
              v-model="manualValues[field as keyof typeof manualValues]"
              :id="field"
              fluid
            />
            <label class="label" :for="field">{{ cutStringOnMiddle(field, 24) }}</label>
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
        :error="isUploadWithErrors || filePredictWithError"
        :loading="isLoading"
        loading-message="Loading prediction..."
        :successMessageOnly="predictReadyForDownload ? 'Success! You can download the file.' : ''"
        @selectFile="onSelectFile"
      />
      <template v-if="predictReadyForDownload">
        <!--<d-button label="Reset" type="reset" fluid @click="onRemoveFile" />-->
        <d-button label="Download" type="submit" fluid @click="downloadPredict" />
      </template>
      <d-button
        v-else
        label="Predict"
        type="submit"
        fluid
        :disabled="isPredictButtonDisabled"
        @click="onFileSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import SelectButton from 'primevue/selectbutton'
import { Textarea } from 'primevue'

import FileInput from '@/components/ui/FileInput.vue'

import { useDataTable } from '@/hooks/useDataTable'
import { useModelTraining } from '@/hooks/useModelTraining'
import { convertObjectToCsvBlob } from '@/helpers/helpers'

import { cutStringOnMiddle } from '@/helpers/helpers'

const { startPredict, isLoading } = useModelTraining()

type Props = {
  manualFields: string[]
  modelId: string
}

const props = defineProps<Props>()

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {}
}
const { isUploadWithErrors, fileData, onSelectFile, getDataForTraining, onRemoveFile } =
  useDataTable(tableValidator)

const selectValue = ref<'Manual' | 'Upload file'>('Manual')
const selectOptions = ref(['Manual', 'Upload file'])
const manualValues = ref(
  props.manualFields.reduce(
    (acc, field) => {
      acc[field] = ''

      return acc
    },
    {} as Record<string, string>,
  ),
)
const predictionText = ref('')
const filePredictWithError = ref(false)
const downloadPredictBlob = ref<Blob | null>(null)

const predictReadyForDownload = computed(() => !!downloadPredictBlob.value)
const isPredictButtonDisabled = computed(() => !fileData.value.name || isUploadWithErrors.value)

async function onManualSubmit() {
  predictionText.value = ''

  const data = prepareManualData()

  const predictRequest = { data, model_id: props.modelId }
  const result = await startPredict(predictRequest)

  if (result) predictionText.value = result.predictions?.join(', ')
}
async function onFileSubmit() {
  const data: any = getDataForTraining()

  const predictRequest = { data, model_id: props.modelId }
  const result = await startPredict(predictRequest)

  if (result) {
    data.prediction = result.predictions

    downloadPredictBlob.value = convertObjectToCsvBlob(data)
  } else {
    filePredictWithError.value = true
  }
}
function prepareManualData() {
  const data: any = {}

  for (const key in manualValues.value) {
    const value = manualValues.value[key].trim()

    if (!value) continue

    const formattedValue = isNaN(Number(value)) ? value : Number(value)

    data[key] = [formattedValue]
  }

  return data
}
function downloadPredict() {
  if (!downloadPredictBlob.value) return

  const url = URL.createObjectURL(downloadPredictBlob.value)
  const a = document.createElement('a')
  a.href = url
  a.download = 'dfs-predictions'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

watch(
  fileData,
  () => {
    filePredictWithError.value = false
    downloadPredictBlob.value = null
  },
  { deep: true },
)
</script>

<style scoped>
.text {
  margin-bottom: 32px;
  color: var(--p-text-muted-color);
}

.manual {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.upload {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  margin-top: 2rem;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-height: 316px;
  overflow-y: auto;
  padding-top: 1rem;
  margin-top: 1rem;
}

.disabled {
  opacity: 0.6;
  pointer-events: none;
}
</style>
