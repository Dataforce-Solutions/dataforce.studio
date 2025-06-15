import type { CreateInvitePayload, Invitation } from '@/lib/api/DataforceApi.interfaces'
import { dataforceApi } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useInvitationsStore = defineStore('invitations', () => {
  const invitations = ref<Invitation[]>([])

  async function getInvitations() {
    const response = await dataforceApi.getInvitations()
    invitations.value = response
  }

  async function acceptInvitation(inviteId: number) {
    await dataforceApi.acceptInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
  }

  async function rejectInvitation(inviteId: number) {
    await dataforceApi.acceptInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
  }

  async function createInvite(payload: CreateInvitePayload) {
    const invite = await dataforceApi.createInvite(payload.organization_id, payload)
    return invite
  }

  async function cancelInvite(organizationId: number, inviteId: number) {
    return dataforceApi.cancelInvitation(organizationId, inviteId)
  }

  return { invitations, getInvitations, acceptInvitation, rejectInvitation, createInvite, cancelInvite }
})
