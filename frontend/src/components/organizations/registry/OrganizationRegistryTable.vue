<template>
  <div class="simple-table">
    <div class="simple-table__header">
      <div class="simple-table__row">
        <div>Name</div>
        <div>Created</div>
        <div></div>
      </div>
    </div>
    <div class="simple-table__rows">
      <div v-if="!bucketsStore.buckets.length" class="simple-table__placeholder">
        No buckets created for this organization.
      </div>
      <div v-for="bucket in bucketsStore.buckets" class="simple-table__row">
        <div style="overflow: hidden; text-overflow: ellipsis;">{{ bucket.bucket_name }}</div>
        <div>{{ new Date(bucket.created_at).toLocaleDateString() }}</div>
        <div>
          <Button
            disabled
            severity="secondary"
            variant="text"
            v-tooltip.top="'Not available yet'"
            @click="deleteBucket(bucket.id)"
          >
            <template #icon>
              <Trash2 :size="14" />
            </template>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useBucketsStore } from '@/stores/buckets'
import { useOrganizationStore } from '@/stores/organization'
import { onMounted, ref } from 'vue'
import { Button } from 'primevue'
import { Trash2 } from 'lucide-vue-next'

const bucketsStore = useBucketsStore()
const organizationStore = useOrganizationStore()

const loading = ref()

async function deleteBucket(bucketId: number) {
  const organizationId = organizationStore.currentOrganization?.id
  if (!organizationId) return
  bucketsStore.deleteBucket(organizationId, bucketId)
}

onMounted(async () => {
  try {
    const organizationId = organizationStore.currentOrganization?.id
    if (!organizationId) return
    await bucketsStore.getBuckets(organizationId)
  } catch {
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
@import '@/assets/tables.css';

.simple-table__row {
  grid-template-columns: 1fr 120px 35px;
}
</style>
