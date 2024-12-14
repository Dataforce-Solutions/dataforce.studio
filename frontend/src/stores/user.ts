import { defineStore } from 'pinia'
import type { IUser } from './user.interfaces'
import { computed, ref } from 'vue'
import { dataforceApi } from '@/utils/api'
import type {
  IPostChangePasswordRequest,
  IUpdateUserRequest,
} from '@/utils/api/DataforceApi.interfaces'
import { useAuthStore } from './auth'
import { useRouter } from 'vue-router'

export const useUserStore = defineStore('user', () => {
  const authStore = useAuthStore()
  const router = useRouter()

  const user = ref<IUser | null>(null)
  const isPasswordHasBeenChanged = ref(false)

  const getUserEmail = computed(() => user.value?.email)
  const getUserFullName = computed(() => user.value?.full_name)
  const isUserDisabled = computed(() => user.value?.disabled)
  const getUserAvatar = computed(() => user.value?.photo)
  const isUserLoggedWithSSO = computed(() => user.value?.auth_method !== 'email')

  const loadUser = async () => {
    const data = await dataforceApi.getMe()

    user.value = data
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

  const resetPassword = async () => {
    isPasswordHasBeenChanged.value = true

    router.push({ name: 'home' })

    setTimeout(() => {
      isPasswordHasBeenChanged.value = false
    }, 3000)
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
    loadUser,
    changePassword,
    deleteAccount,
    resetUser,
    resetPassword,
    updateUser,
  }
})
