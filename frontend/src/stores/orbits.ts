import type { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { dataforceApi } from '@/lib/api'
import type { AddMemberToOrbitPayload, CreateOrbitPayload } from '@/lib/api/DataforceApi.interfaces'
import { defineStore } from 'pinia'

export const useOrbitsStore = defineStore('orbit', () => {
  async function createOrbit(payload: CreateOrbitPayload) {
    await dataforceApi.createOrbit(payload)
  }

  async function addMemberToOrbit(organizationId: number, payload: AddMemberToOrbitPayload) {
    return dataforceApi.addMemberToOrbit(organizationId, payload)
  }

  async function getOrbitDetails(organizationId: number, orbitId: number) {
    return dataforceApi.getOrbitDetails(organizationId, orbitId)
  }

  async function deleteMember(organizationId: number, orbitId: number, memberId: number) {
    return dataforceApi.deleteOrbitMember(organizationId, orbitId, memberId)
  }

  async function updateMember(organizationId: number, orbitId: number, data: { id: number, role: OrbitRoleEnum }) {
    return dataforceApi.updateOrbitMember(organizationId, orbitId, data)
  }

  return { createOrbit, addMemberToOrbit, getOrbitDetails, deleteMember, updateMember }
})
