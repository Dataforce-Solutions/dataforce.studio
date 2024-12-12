import { dataforceApi } from '@/utils/api'
import type {
  IGetGoogleLoginRequest,
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
  IPostSignupResponse,
} from '@/utils/api/DataforceApi.interfaces'

import { googleSdkLoaded } from 'vue3-google-login'
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

  const forgotPassword = async (email: string) => {
    await dataforceApi.forgotPassword({ email })
  }

  const getTokensWithGoogleCode = async (code: string) => {
    const response = await dataforceApi.googleLogin({ code })

    console.log(response)
  }

  const loginWithGoogle = async () => {
    // const loginResponse = await dataforceApi.googleLogin()

    googleSdkLoaded((google) => {
      google.accounts.oauth2
        .initCodeClient({
          client_id: '1005997792037-17lj55mpmh2c43b7db51jr159bneqhqr.apps.googleusercontent.com',
          scope: 'email profile openid',
          redirect_uri: 'https://dev-api.dataforce.studio/auth/google/callback',
          callback: (response) => {
            console.log(response)
            if (response.code) {
              getTokensWithGoogleCode(response.code)
            }
          },
        })
        .requestCode()
    })
  }

  return { isAuth, signUp, signIn, logout, checkIsLoggedId, forgotPassword, loginWithGoogle }
})
