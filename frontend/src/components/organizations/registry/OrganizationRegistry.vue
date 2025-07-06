<template>
  <div>
    <div class="header">
      <h3 class="label">List of Buckets for current organization (3)</h3>
      <OrganizationBucketCreator></OrganizationBucketCreator>
    </div>
    <OrganizationRegistryTable></OrganizationRegistryTable>
  </div>
</template>

<script setup lang="ts">
import OrganizationRegistryTable from './OrganizationRegistryTable.vue'
import OrganizationBucketCreator from './OrganizationBucketCreator.vue'
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.label {
  font-weight: 500;
  font-size: 20px;
}
</style>
