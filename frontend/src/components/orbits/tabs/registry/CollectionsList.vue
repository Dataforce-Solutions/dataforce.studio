<template>
  <div class="list">
    <CollectionCard
      v-for="collection in collectionsStore.collectionsList"
      :edit-available="editAvailable"
      :data="collection"
    ></CollectionCard>
  </div>
</template>

<script setup lang="ts">
import { useCollectionsStore } from '@/stores/collections'
import CollectionCard from './CollectionCard.vue'

type Props = {
  editAvailable: boolean
}

defineProps<Props>()

const collectionsStore = useCollectionsStore()
</script>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
