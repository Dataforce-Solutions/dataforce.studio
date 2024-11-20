import { DataforceApiClass } from './DataforceApi'

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipInterceptors?: boolean
  }
}

export const dataforceApi = new DataforceApiClass()
