import { dataforceApi } from '@/utils/api'
import type {
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
  IPostSignupResponse,
} from '@/utils/api/DataforceApi.interfaces'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'

export const useAuthStore = defineStore('auth', () => {
  const usersStore = useUserStore()

  const isAuth = ref(false)

  const signUp = async (data: IPostSignupRequest) => {
    const { access_token, refresh_token }: IPostSignupResponse = await dataforceApi.signUp(data)

    saveTokens(access_token, refresh_token)

    isAuth.value = true

    await usersStore.loadUser()
  }

  const signIn = async (data: IPostSignInRequest) => {
    const { access_token, refresh_token }: IPostSignInResponse = await dataforceApi.signIn(data)

    saveTokens(access_token, refresh_token)

    isAuth.value = true

    await usersStore.loadUser()
  }

  const logout = async () => {
    const refresh_token = localStorage.getItem('refreshToken')

    if (!refresh_token) throw new Error('Refresh token is not exist')

    await dataforceApi.logout({ refresh_token })

    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')

    usersStore.resetUser()
  }

  const checkIsLoggedId = async () => {
    const refresh_token = localStorage.getItem('refreshToken')

    if (!refresh_token) return

    const { access_token, refresh_token: newRefreshToken } = await dataforceApi.refreshToken({
      refresh_token,
    })

    saveTokens(access_token, newRefreshToken)

    isAuth.value = true

    await usersStore.loadUser()
  }

  const saveTokens = (token: string, refreshToken?: string) => {
    localStorage.setItem('token', token)

    refreshToken && localStorage.setItem('refreshToken', refreshToken)
  }

  return { isAuth, signUp, signIn, logout, checkIsLoggedId }
})
