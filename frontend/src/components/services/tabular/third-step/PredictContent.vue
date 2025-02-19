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
              fluid/>
            <label class="label" :for="field">{{ cutStringOnMiddle(field, 24) }}</label>
          </d-float-label>
        </div>
      </div>
      <d-button
        label="Predict"
        type="submit"
        fluid
        :disabled="isManualPredictButtonDisabled"
        @click="onManualSubmit"/>
      <Textarea
        class="prediction"
        v-model="predictionText"
        id="prediction"
        fluid
        rows="4"
        :style="{ resize: 'none' }"
        disabled
        placeholder="Prediction"></Textarea>
    </div>
    <div v-else class="upload">
      <file-input
        id="predict"
        :file="fileData"
        :error="isUploadWithErrors || filePredictWithError"
        :loading="isLoading"
        loading-message="Loading prediction..."
        :success-message-only="predictReadyForDownload ? 'Success! You can download the file.' : ''"
        success-remove-text="Upload new dataset"
        :accept="['text/csv']"
        accept-text="Accepts .csv file type"
        upload-text="upload CSV"
        @select-file="onSelectFile"
        @remove-file="onRemoveFile"/>
      <template v-if="predictReadyForDownload">
        <d-button label="Download" type="submit" fluid @click="downloadPredict" />
      </template>
      <d-button
        v-else
        label="Predict"
        type="submit"
        fluid
        :disabled="isPredictButtonDisabled"
        @click="onFileSubmit"/>
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
const isManualPredictButtonDisabled = computed(() => {
  for (const input in manualValues.value) {
    if (!manualValues.value[input]) return true
  }
  return false
})

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
    if (!value) continue;
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

watch(fileData, () => {
    filePredictWithError.value = false
    downloadPredictBlob.value = null
  }, { deep: true },
)
</script>

<style scoped>
.text {
  margin-bottom: 28px;
  color: var(--p-text-muted-color);
}

.manual {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.upload {
  display: flex;
  flex-direction: column;
  gap: 28px;
  margin-top: 28px;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 306px;
  overflow-y: auto;
  padding-top: 14px;
  margin-top: 14px;
}

.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.prediction:disabled {
  background-color: var(--p-textarea-background) !important;
  color: var(--p-textarea-color);
}

.prediction.p-filled {
  border: 1px solid var(--p-textarea-focus-border-color);
  background-color: var(--p-textarea-filled-background) !important;
  font-weight: 500 !important;
}
</style>
