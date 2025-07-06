<template>
  <div>
    <UiPageLoader v-if="loading"></UiPageLoader>

    <Ui404 v-else-if="!orbitsStore.currentOrbitDetails"></Ui404>
    <div v-else class="orbit-page">
      <OrbitTabs></OrbitTabs>
      <div class="view">
        <RouterView></RouterView>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeMount, ref, watch } from 'vue'
import { useToast } from 'primevue'
import { useOrbitsStore } from '@/stores/orbits'
import { useRoute, useRouter } from 'vue-router'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import Ui404 from '@/components/ui/Ui404.vue'
import OrbitTabs from '@/components/orbits/tabs/OrbitTabs.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import { useOrganizationStore } from '@/stores/organization'

const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const loading = ref(false)

async function loadOrbitDetails() {
  try {
    loading.value = true
    orbitsStore.setCurrentOrbitDetails(null)
    const details = await orbitsStore.getOrbitDetails(
      +route.params.organizationId,
      +route.params.id,
    )
    orbitsStore.setCurrentOrbitDetails(details)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load orbit data'))
  } finally {
    loading.value = false
  }
}

watch(() => organizationStore.currentOrganization?.id, async (id) => {
  if (!id || +route.params.organizationId === id) return
  
  await router.push({ name: 'orbits', params: { organizationId: id }})
})

onBeforeMount(async () => {
  loadOrbitDetails()
})
</script>

<style scoped>
.orbit-page {
  padding: 32px 0;
}
.view {
  padding-top: 20px;
}
</style>
