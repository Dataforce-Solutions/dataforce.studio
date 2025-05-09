import type { AxiosInstance } from 'axios'
import type { IPostRefreshTokenRequest, IPostRefreshTokenResponse } from './DataforceApi.interfaces'

export const installDataforceInterceptors = (api: AxiosInstance) => {
  api.interceptors.request.use(
    (config) => {
      if (config.skipInterceptors) {
        return config
      }
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    },
    (error) => {
      return Promise.reject(error)
    },
  )

  api.interceptors.response.use(
    (response) => {
      return response
    },
    async (error) => {
      if (error.response && error.response.status === 401) {
        try {
          const refresh_token = localStorage.getItem('refreshToken')

          if (!refresh_token) throw new Error('Refresh token is not exist')

          const data: IPostRefreshTokenRequest = { refresh_token }

          const { data: responseData } = await api.post<IPostRefreshTokenResponse>(
            '/auth/refresh',
            data,
          )

          const newToken = responseData.access_token

          localStorage.setItem('token', newToken)
          localStorage.setItem('refreshToken', responseData.refresh_token)

          error.config.headers.Authorization = `Bearer ${newToken}`
          return api.request(error.config)
        } catch (refreshError) {
          localStorage.removeItem('token')
          localStorage.removeItem('refreshToken')
          console.error('Failed to refresh token:', refreshError)
        }
      }

      return Promise.reject(error)
    },
  )
}
