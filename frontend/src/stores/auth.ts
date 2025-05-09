import { dataforceApi } from '@/lib/api'
import type {
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
} from '@/lib/api/DataforceApi.interfaces'

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { AnalyticsService } from '@/lib/analytics/AnalyticsService'

export const useAuthStore = defineStore('auth', () => {
  const usersStore = useUserStore()

  const isAuth = ref(false)

  const signUp = async (data: IPostSignupRequest) => {
    await dataforceApi.signUp(data)
    AnalyticsService.identify(data.email)
  }

  const signIn = async (data: IPostSignInRequest) => {
    const { access_token, refresh_token }: IPostSignInResponse = await dataforceApi.signIn(data)
    saveTokens(access_token, refresh_token)
    isAuth.value = true
    AnalyticsService.identify(data.email)
    await usersStore.loadUser()
  }

  const logout = async () => {
    const refresh_token = localStorage.getItem('refreshToken')
    if (!refresh_token) throw new Error('Refresh token is not exist')
    try {
      await dataforceApi.logout({ refresh_token })
    } catch (e) {
      throw e
    } finally {
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      usersStore.resetUser()
      isAuth.value = false
    }
  }

  const checkIsLoggedId = async () => {
    const token = localStorage.getItem('token');
    const refreshToken = localStorage.getItem('refreshToken');
    if (!token && !refreshToken) {
      isAuth.value = false;
      return
    }
    await usersStore.loadUser()
    isAuth.value = true
  }

  const saveTokens = (token: string, refreshToken?: string) => {
    localStorage.setItem('token', token)
    refreshToken && localStorage.setItem('refreshToken', refreshToken)
  }

  const forgotPassword = async (email: string) => {
    await dataforceApi.forgotPassword({ email })
  }

  const loginWithGoogle = async (code: string) => {
    const { access_token, refresh_token } = await dataforceApi.googleLogin({ code })
    if (!access_token) return
    saveTokens(access_token, refresh_token)
    isAuth.value = true
    await usersStore.loadUser()
  }

  return { isAuth, signUp, signIn, logout, checkIsLoggedId, forgotPassword, loginWithGoogle }
})
