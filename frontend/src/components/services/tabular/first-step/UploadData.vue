<template>
  <div class="wrapper">
    <div class="headings">
      <h1 class="main-title">Upload your data for model training</h1>
      <p class="sub-title">
        Drag and drop your file here, or choose one of our sample datasets to get started.
      </p>
    </div>
    <div class="area">
      <file-input
        id="table"
        :file
        :error="hasError"
        @select-file="(e) => $emit('selectFile', e)"
        @remove-file="$emit('removeFile')"
      />
      <div class="info">
        <h3 class="info-title">File parameters</h3>
        <ul class="info-list">
          <li class="info-item">
            <div class="info-item-body">
              <span>File size: up to 50 MB</span>
              <template v-if="isTableExist">
                <x width="20" height="20" class="danger" v-if="errors.size" />
                <check width="20" height="20" class="success" v-if="!errors.size" />
              </template>
            </div>
          </li>
          <li class="info-item">
            <div class="info-item-body">
              <span>Columns: more than 3</span>
              <template v-if="isTableExist">
                <x width="20" height="20" class="danger" v-if="errors.columns" />
                <check width="20" height="20" class="success" v-if="!errors.columns" />
              </template>
            </div>
          </li>
          <li class="info-item">
            <div class="info-item-body">
              <span>Rows: more than 100</span>
              <template v-if="isTableExist">
                <x width="20" height="20" class="danger" v-if="errors.rows" />
                <check width="20" height="20" class="success" v-if="!errors.rows" />
              </template>
            </div>
          </li>
        </ul>
      </div>
      <span class="middle-divider">or</span>
      <span class="empty"></span>
      <div class="sample">
        <div class="sample-title">
          <img :src="CSVIcon" alt="CSV File" />
          <span>Sample dataset</span>
        </div>
        <div class="sample-text">
          Select our preloaded dataset to train your model and view the results in a detailed
          dashboard.
        </div>
        <d-button label="use sample" @click="selectSample" />
      </div>
      <div class="info">
        <h3 class="info-title">Resources</h3>
        <ul class="info-list">
          <li class="info-item">
            <a href="#" class="info-item-body link">
              <span>How to format your file</span>
              <external-link width="14" height="14" />
            </a>
          </li>
          <li class="info-item">
            <a href="#" class="info-item-body link">
              <span>Accepted field formats</span>
              <external-link width="14" height="14" />
            </a>
          </li>
          <li class="info-item">
            <a href="#" class="info-item-body link">
              <span>How to get your CSV</span>
              <external-link width="14" height="14" />
            </a>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { ExternalLink, X, Check } from 'lucide-vue-next'

import CSVIcon from '@/assets/img/icons/csv.svg'

import FileInput from '@/components/ui/FileInput.vue'

type Props = {
  isTableExist: boolean
  errors: {
    size: boolean
    columns: boolean
    rows: boolean
  }
  file: {
    name?: string
    size?: number
  }
}

type Emits = {
  selectFile: [File]
  removeFile: []
}

const emit = defineEmits<Emits>()

const props = defineProps<Props>()

const hasError = computed(() => {
  const errors = props.errors

  if (!errors) return false

  for (const key in errors) {
    if (errors[key as keyof typeof errors]) return true
  }

  return false
})

async function selectSample() {
  const fileUrl = new URL('@/assets/data/iris.csv', import.meta.url).href

  const response = await fetch(fileUrl)
  const text = await response.text()

  const file = new File([text], 'iris.csv', { type: 'text/csv' })

  if (file) emit('selectFile', file)
}
</script>

<style scoped>
.wrapper {
  padding-top: 3rem;
  padding-bottom: 3rem;
}

.headings {
  margin-bottom: 3rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.area {
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  padding: 3rem;
  gap: 16px;
  display: grid;
  grid-template-columns: 1fr 227px;
}

.middle-divider {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
  color: var(--p-text-muted-color);
  font-weight: 500;
  &::before,
  &::after {
    content: '';
    height: 1px;
    background-color: var(--p-divider-border-color);
  }
}

.info {
  font-weight: 500;
  padding: 16px;
}

.info-title {
  margin-bottom: 16px;
  font-size: 16px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  line-height: 1.7;
}

.info-item-body {
  display: flex;
  align-items: center;
  font-size: 14px;
  gap: 7px;
  justify-content: space-between;
  color: var(--p-text-muted-color);
  font-weight: 500;
  padding-right: 10px;
}

.sample {
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  padding: 24px;
}

.sample-title {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.sample-text {
  margin-bottom: 16px;
  color: var(--p-text-hover-muted-color);
  font-size: 14px;
  line-height: 1.7;
}

.danger {
  color: var(--p-badge-danger-background);
}

.success {
  color: var(--p-badge-success-background);
}

@media (max-width: 968px) {
  .area {
    grid-template-columns: 1fr;
  }

  .info {
    order: 3;
  }
}
</style>
