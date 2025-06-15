import type {
  CreateOrganizationPayload,
  Invitation,
  Organization,
  OrganizationDetails,
  UpdateMemberPayload,
} from '@/lib/api/DataforceApi.interfaces'
import { defineStore } from 'pinia'
import { dataforceApi } from '@/lib/api'
import { ref } from 'vue'
import type { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'

export const useOrganizationStore = defineStore('organization', () => {
  const availableOrganizations = ref<Organization[]>([])
  const currentOrganization = ref<OrganizationDetails | null>(null)
  const loading = ref(false)

  function setLoading(value: boolean) {
    loading.value = value
  }

  async function getAvailableOrganizations() {
    const response = await dataforceApi.getOrganizations()
    availableOrganizations.value = response
    await setInitialOrganization()
  }

  async function createOrganization(payload: CreateOrganizationPayload) {
    await dataforceApi.createOrganization(payload)
    await getAvailableOrganizations()
  }

  async function updateOrganization(organizationId: number, payload: CreateOrganizationPayload) {
    const response = await dataforceApi.updateOrganization(organizationId, payload)
    return response
  }

  async function deleteOrganization(organizationId: number) {
    await dataforceApi.deleteOrganization(organizationId)
    const organizationInLocalStorage = LocalStorageService.get('dataforce:currentOrganizationId')
    if (organizationInLocalStorage && +organizationInLocalStorage === organizationId) {
      LocalStorageService.remove('dataforce:currentOrganizationId')
    }
    availableOrganizations.value = availableOrganizations.value.filter(
      (organization) => organization.id !== organizationId,
    )
    setInitialOrganization()
  }

  async function setCurrentOrganizationId(id: number) {
    if (currentOrganization.value?.id === id) return
    try {
      setLoading(true)
      const organizationDetails = await getOrganization(id)
      LocalStorageService.set('dataforce:currentOrganizationId', organizationDetails.id.toString())
      setCurrentOrganization(organizationDetails)
    } catch (e) {
      throw e
    } finally {
      setLoading(false)
    }
  }

  function setCurrentOrganization(organization: OrganizationDetails) {
    currentOrganization.value = organization
    availableOrganizations.value = availableOrganizations.value.map((item) => {
      if (item.id === organization.id) {
        return {
          id: organization.id,
          name: organization.name,
          logo: organization.logo,
          created_at: organization.created_at,
          updated_at: organization.updated_at,
          role: item.role,
        }
      } else {
        return item
      }
    })
  }

  async function getOrganization(id: number) {
    return dataforceApi.getOrganization(id)
  }

  async function setInitialOrganization() {
    const organizationInStorage = LocalStorageService.get('dataforce:currentOrganizationId')
    const organizationInStorageAvailable =
      organizationInStorage &&
      availableOrganizations.value?.find((org) => org.id === +organizationInStorage)
    const organizationForSelect = organizationInStorageAvailable
      ? organizationInStorageAvailable.id
      : availableOrganizations.value?.[0]?.id
    if (!organizationForSelect) return
    await setCurrentOrganizationId(organizationForSelect)
  }

  function resetCurrentOrganization() {
    currentOrganization.value = null
  }

  async function updateMember(
    organizationId: number,
    memberId: number,
    payload: UpdateMemberPayload,
  ) {
    return dataforceApi.updateOrganizationMember(organizationId, memberId, payload)
  }

  async function deleteMember(organizationId: number, memberId: number) {
    await dataforceApi.deleteMemberFormOrganization(organizationId, memberId)
    if (!currentOrganization.value) return
    const members = currentOrganization.value.members.filter((member) => member.id !== memberId)
    currentOrganization.value = { ...currentOrganization.value, members: members }
  }

  function removeInviteFromCurrentOrganization(inviteId: number) {
    if (!currentOrganization.value) return
    currentOrganization.value = {
      ...currentOrganization.value,
      invites: currentOrganization.value.invites.filter((invite) => invite.id !== inviteId),
    }
  }

  function addInviteToCurrentOrganization(invite: Invitation) {
    currentOrganization.value?.invites.push(invite)
  }

  async function leaveOrganization(organizationId: number) {
    await dataforceApi.leaveOrganization(organizationId)
    availableOrganizations.value = availableOrganizations.value.filter(
      (organization) => organization.id !== organizationId,
    )
  }

  return {
    availableOrganizations,
    currentOrganization,
    loading,
    getAvailableOrganizations,
    createOrganization,
    updateOrganization,
    deleteOrganization,
    resetCurrentOrganization,
    deleteMember,
    updateMember,
    removeInviteFromCurrentOrganization,
    addInviteToCurrentOrganization,
    leaveOrganization,
    setCurrentOrganizationId,
    setLoading,
    setCurrentOrganization,
  }
})
