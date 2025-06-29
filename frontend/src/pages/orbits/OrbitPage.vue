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
import { ref, watch } from 'vue'
import { useToast } from 'primevue'
import { useOrganizationStore } from '@/stores/organization'
import { useOrbitsStore } from '@/stores/orbits'
import { useRoute } from 'vue-router'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import Ui404 from '@/components/ui/Ui404.vue'
import OrbitTabs from '@/components/orbits/tabs/OrbitTabs.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const route = useRoute()
const toast = useToast()

const loading = ref(false)

watch(
  () => organizationStore.currentOrganization?.id,
  async (organizationId) => {
    if (!organizationId || typeof route.params.id !== 'string') return
    try {
      loading.value = true
      orbitsStore.setCurrentOrbitDetails(null)
      const details = await orbitsStore.getOrbitDetails(organizationId, +route.params.id)
      orbitsStore.setCurrentOrbitDetails(details)
    } catch (e) {
      toast.add(simpleErrorToast('Failed to load orbit data'))
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.orbit-page {
  padding: 32px 0;
}
.view {
  padding-top: 20px;
}
</style>
