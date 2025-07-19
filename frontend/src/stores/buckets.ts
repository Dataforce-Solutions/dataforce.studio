import type { BucketSecret, BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
import { dataforceApi } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBucketsStore = defineStore('buckets', () => {
  const buckets = ref<BucketSecret[]>([])

  async function getBuckets(organizationId: number) {
    buckets.value = await dataforceApi.bucketSecrets.getBucketSecretsList(organizationId)
  }

  async function createBucket(organizationId: number, data: BucketSecretCreator) {
    const bucket = await dataforceApi.bucketSecrets.createBucketSecret(organizationId, data)
    buckets.value.push(bucket)
  }

  async function updateBucket(organizationId: number, bucketId: number, data: BucketSecretCreator & { id: number }) {
    const updatedBucket = await dataforceApi.bucketSecrets.updateBucketSecret(organizationId, bucketId, data)
    const index = buckets.value.findIndex(bucket => bucket.id === bucketId)
    if (index !== -1) {
      buckets.value[index] = updatedBucket
    }
    return updatedBucket
  }

  async function deleteBucket(organizationId: number, bucketId: number) {
    await dataforceApi.bucketSecrets.deleteBucketSecret(organizationId, bucketId)
    buckets.value = buckets.value.filter((bucket) => bucket.id !== bucketId)
  }

  return {
    buckets,
    getBuckets,
    createBucket,
    updateBucket,
    deleteBucket,
  }
})
