<template>
  <Button severity="secondary" variant="text" @click="visible = true">
    <template #icon>
      <Bolt :size="14" />
    </template>
  </Button>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="popup-title">
        <Database :size="20" class="popup-title-icon" />
        <span>bucket settings</span>
      </h2>
    </template>
    <div class="dialog-content">
      <div class="bucket-info">
        <div>
          <div class="bucket-name">{{ bucket.bucket_name }}</div>
          <div class="bucket-endpoint">{{ bucket.endpoint }}</div>
        </div>
      </div>
      <div class="bucket-form-wrapper">
        <BucketForm :initial-data="initialData" :loading="loading" @submit="onFormSubmit" />
      </div>
    </div>
    <template #footer>
      <Button severity="warn" variant="outlined" :disabled="loading" @click="onDelete">
        delete bucket
      </Button>
      <Button type="submit" :disabled="loading" form="bucketForm">save changes</Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { BucketSecret, BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
import { computed, ref } from 'vue'
import { Button, Dialog, useConfirm, useToast } from 'primevue'
import { useBucketsStore } from '@/stores/buckets'
import { Bolt, Database } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteBucketConfirmOptions } from '@/lib/primevue/data/confirm'
import BucketForm from './BucketForm.vue'

const dialogPT = {
  footer: {
    class: 'organization-edit-footer',
  },
}

type Props = {
  bucket: BucketSecret
}

const props = defineProps<Props>()

const bucketsStore = useBucketsStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

const initialData = computed<BucketSecretCreator>(() => ({
  bucket_name: props.bucket.bucket_name,
  endpoint: props.bucket.endpoint,
  region: props.bucket.region,
  secure: props.bucket.secure,
  access_key: '',
  secret_key: '',
}))

async function onFormSubmit(values: BucketSecretCreator) {
  try {
    visible.value = false
    loading.value = true

    const updatedBucket: any = {
      id: props.bucket.id,
      bucket_name: values.bucket_name,
      endpoint: values.endpoint,
      region: values.region,
      secure: values.secure,
      access_key: values.access_key,
      secret_key: values.secret_key,
    }

    await bucketsStore.updateBucket(props.bucket.organization_id, props.bucket.id, updatedBucket)
    toast.add(simpleSuccessToast('Bucket have been updated.'))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to update bucket'))
  } finally {
    loading.value = false
  }
}

function onDelete() {
  confirm.require(deleteBucketConfirmOptions(deleteBucket))
}

async function deleteBucket() {
  try {
    visible.value = false
    loading.value = true
    await bucketsStore.deleteBucket(props.bucket.organization_id, props.bucket.id)
    toast.add(simpleSuccessToast('The bucket has been successfully deleted.'))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to delete bucket'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.popup-title {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 16px;
  text-transform: uppercase;
  font-weight: 500;
}

.popup-title-icon {
  color: var(--p-primary-500);
}

.bucket-info {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
}

.bucket-name {
  margin-bottom: 4px;
}

.bucket-endpoint {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.bucket-form-wrapper :deep(button[type="submit"]) {
  display: none;
}
</style>
