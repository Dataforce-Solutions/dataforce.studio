import { defineStore } from 'pinia'
import type { IUser } from './user.interfaces'
import { computed, ref } from 'vue'
import { dataforceApi } from '@/lib/api'
import type {
  IPostChangePasswordRequest,
  IUpdateUserRequest,
} from '@/lib/api/DataforceApi.interfaces'
import { useAuthStore } from './auth'
import { useOrganizationStore } from './organization'
import { useInvitationsStore } from './invitations'

export const useUserStore = defineStore('user', () => {
  const authStore = useAuthStore()
  const invitationsStore = useInvitationsStore()
  const organizationStore = useOrganizationStore()

  const user = ref<IUser | null>(null)
  const isPasswordHasBeenChanged = ref(false)

  const getUserEmail = computed(() => user.value?.email)
  const getUserFullName = computed(() => user.value?.full_name)
  const isUserDisabled = computed(() => user.value?.disabled)
  const getUserAvatar = computed(() => user.value?.photo)
  const isUserLoggedWithSSO = computed(() => user.value?.auth_method !== 'email')
  const getUserId = computed(() => user.value?.id)

  const loadUser = async () => {
    const data = await dataforceApi.getMe()
    user.value = data
    await invitationsStore.getInvitations()
    await organizationStore.getAvailableOrganizations()
  }

  const changePassword = async (data: IPostChangePasswordRequest) => {
    await dataforceApi.updateUser(data)
  }

  const deleteAccount = async () => {
    await dataforceApi.deleteUser()

    authStore.logout()
  }

  const resetUser = () => {
    user.value = null
  }

  const resetPassword = async (reset_token: string, new_password: string) => {
    return dataforceApi.resetPassword({ reset_token, new_password })
  }

  const updateUser = async (data: IUpdateUserRequest) => {
    const response = await dataforceApi.updateUser(data)

    await loadUser()

    return response
  }

  return {
    getUserEmail,
    getUserFullName,
    getUserAvatar,
    isUserDisabled,
    isPasswordHasBeenChanged,
    isUserLoggedWithSSO,
    getUserId,
    loadUser,
    changePassword,
    deleteAccount,
    resetUser,
    resetPassword,
    updateUser,
  }
})
