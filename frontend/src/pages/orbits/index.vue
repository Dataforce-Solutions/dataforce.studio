<template>
  <div class="content">
    <UiPageLoader v-if="loading"></UiPageLoader>

    <div v-else-if="organizationStore.currentOrganization">
      <OrbitsListHeader class="header" @create-new="showCreator = true"></OrbitsListHeader>
      <OrbitsList
        :create-available="createAvailable"
        :orbits="orbitsStore.orbitsList"
        @create-new="showCreator = true"
      ></OrbitsList>
      <OrbitCreator v-model:visible="showCreator"></OrbitCreator>
    </div>

    <Ui404 v-else></Ui404>
  </div>
</template>

<script setup lang="ts">
import { useOrbitsStore } from '@/stores/orbits'
import { computed, ref, watch } from 'vue'
import { useOrganizationStore } from '@/stores/organization'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import Ui404 from '@/components/ui/Ui404.vue'
import OrbitsListHeader from '@/components/orbits/OrbitsListHeader.vue'
import OrbitsList from '@/components/orbits/OrbitsList.vue'
import OrbitCreator from '@/components/orbits/creator/OrbitCreator.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()

const loading = ref(false)
const showCreator = ref(false)

const createAvailable = computed(() => true)

async function loadOrbits(organizationId: number) {
  try {
    loading.value = true
    await orbitsStore.loadOrbitsList(organizationId)
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.message || 'Failed to load orbits'))
  } finally {
    loading.value = false
  }
}

watch(
  () => organizationStore.currentOrganization?.id,
  (id) => {
    if (!id) return
    loadOrbits(id)
  },
  {
    immediate: true,
  },
)
</script>

<style scoped>
.content {
  padding-top: 32px;
  box-sizing: border-box;
}
.header {
  margin-bottom: 44px;
}
</style>
