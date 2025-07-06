<template>
  <div>
    <UiPageLoader v-if="loading"></UiPageLoader>

    <div
      v-else-if="collectionsStore.currentCollection"
      class="page-content"
      :style="{
        height: `calc(100vh - ${headerSizes.height + footerSizes.height + 40}px )`,
      }"
    >
      <CollectionHeader
        :title="collectionsStore.currentCollection.name"
        :add-available="!!orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.create)"
        @add="modelCreatorVisible = true"
      ></CollectionHeader>
      <CollectionModelsTable class="table"></CollectionModelsTable>
      <d-button as-child v-slot="slotProps" severity="secondary">
        <RouterLink :to="{ name: 'orbit-registry' }" class="navigate-button" :class="slotProps.class" style="flex: 0 0 auto;">
          <ArrowLeft :size="14" />
          <span>Back to Registry</span>
        </RouterLink>
      </d-button>
      <CollectionModelCreator v-model:visible="modelCreatorVisible"></CollectionModelCreator>
    </div>

    <Ui404 v-else></Ui404>
  </div>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCollectionsStore } from '@/stores/collections'
import { useOrbitsStore } from '@/stores/orbits'
import { useToast } from 'primevue'
import { useLayout } from '@/hooks/useLayout'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { ArrowLeft } from 'lucide-vue-next'
import CollectionHeader from '@/components/orbits/tabs/registry/collection/CollectionHeader.vue'
import CollectionModelsTable from '@/components/orbits/tabs/registry/collection/CollectionModelsTable.vue'
import CollectionModelCreator from '@/components/orbits/tabs/registry/collection/model/CollectionModelCreator.vue'
import Ui404 from '@/components/ui/Ui404.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import { useOrganizationStore } from '@/stores/organization'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'

const route = useRoute()
const router = useRouter()
const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()
const { headerSizes, footerSizes } = useLayout()

const loading = ref(true)
const modelCreatorVisible = ref(false)

async function init(organizationId: number) {
  try {
    loading.value = true
    if (typeof route.params.id !== 'string' || typeof route.params.collectionId !== 'string')
      throw new Error('Incorrect route data')

    if (orbitsStore.currentOrbitDetails?.id !== +route.params.id) {
      const details = await orbitsStore.getOrbitDetails(organizationId, +route.params.id)
      orbitsStore.setCurrentOrbitDetails(details)
    }

    await collectionsStore.loadCollections()

    collectionsStore.setCurrentCollection(+route.params.collectionId)
  } catch {
    toast.add(simpleErrorToast('Failed to load collection data'))
  } finally {
    loading.value = false
  }
}

watch(() => organizationStore.currentOrganization?.id, async (id) => {
  if (!id || +route.params.organizationId === id) return

  await router.push({ name: 'orbits', params: { organizationId: id } })
})

onBeforeMount(() => {
  init(+route.params.organizationId)
})

onUnmounted(() => {
  collectionsStore.resetCurrentCollection()
})
</script>

<style scoped>
.loader-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
.page-content {
  display: flex;
  flex-direction: column;
}

.table {
  flex: 1 1 auto;
  margin-bottom: 16px;
}

.navigate-button {
  align-self: flex-start;
  margin-left: -88px;
}
</style>
