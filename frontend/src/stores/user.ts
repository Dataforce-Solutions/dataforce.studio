import { defineStore } from 'pinia'
import type { IUser } from './user.interfaces'
import { computed, ref } from 'vue'
import { dataforceApi } from '@/utils/api'
import type { IPostChangePasswordRequest } from '@/utils/api/DataforceApi.interfaces'
import { useAuthStore } from './auth'

export const useUserStore = defineStore('user', () => {
  const authStore = useAuthStore()

  const user = ref<IUser | null>(null)

  const getUserEmail = computed(() => user.value?.email)
  const getUserFullName = computed(() => user.value?.full_name)
  const isUserDisabled = computed(() => user.value?.disabled)

  const loadUser = async () => {
    const data = await dataforceApi.getMe()

    user.value = data
  }

  const changePassword = async (data: IPostChangePasswordRequest) => {
    await dataforceApi.changePassword(data)
  }

  const deleteAccount = async () => {
    await dataforceApi.deleteUser()

    authStore.logout()
  }

  const resetUser = () => {
    user.value = null
  }

  return {
    getUserEmail,
    getUserFullName,
    isUserDisabled,
    loadUser,
    changePassword,
    deleteAccount,
    resetUser,
  }
})
