<template>
  <div
    v-if="organizationStore.loading"
    :style="{
      width: '100%',
      height: `calc(100vh - ${headerSizes.height}px)`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }"
  >
    <ProgressSpinner></ProgressSpinner>
  </div>

  <div v-else-if="organizationStore.currentOrganization">
    <OrganizationLocked v-if="!hasPermission"></OrganizationLocked>
    <div v-else class="organization-page">
      <OrganizationInfo class="info"></OrganizationInfo>
      <OrganizationLimits class="limits"></OrganizationLimits>
      <OrganizationTabs></OrganizationTabs>
    </div>
  </div>
  <div v-else class="title">Organization {{ route.params.id }} not found...</div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOrganizationStore } from '@/stores/organization'
import { useToast, ProgressSpinner } from 'primevue'
import OrganizationInfo from '@/components/organizations/OrganizationInfo.vue'
import OrganizationLimits from '@/components/organizations/OrganizationLimits.vue'
import OrganizationTabs from '@/components/organizations/OrganizationTabs.vue'
import OrganizationLocked from '@/components/organizations/OrganizationLocked.vue'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { useLayout } from '@/hooks/useLayout'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'

const route = useRoute()
const router = useRouter()
const organizationStore = useOrganizationStore()
const toast = useToast()
const { headerSizes } = useLayout()

const hasPermission = computed(() => {
  const userRole = organizationStore.availableOrganizations.find(
    (organization) => organization.id === organizationStore.currentOrganization?.id,
  )?.role
  if (!userRole || userRole === OrganizationRoleEnum.member) return false
  return true
})

onBeforeMount(async () => {
  if (typeof route.params.id !== 'string') {
    return
  }
  try {
    await organizationStore.setCurrentOrganizationId(+route.params.id)
  } catch (e: any) {
    toast.add(simpleErrorToast(e.details || 'Unable to retrieve organization data'))
  }
})

watch(
  () => organizationStore.currentOrganization?.id,
  (id) => {
    router.push({ name: 'organization', params: { id } })
  },
)
</script>

<style scoped>
.organization-page {
  padding-top: 30px;
}
.info {
  margin-bottom: 24px;
}
.limits {
  margin-bottom: 44px;
}
.title {
  padding-top: 30px;
}
</style>
