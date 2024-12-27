import axios from 'axios'
import type { AxiosInstance } from 'axios'

import type {
  IGetUserResponse,
  IPostChangePasswordRequest,
  IPostLogoutRequest,
  IPostRefreshTokenRequest,
  IPostRefreshTokenResponse,
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
  IPostSignupResponse,
  TDeleteAccountResponse,
  IPostChangePasswordResponse,
  TPostLogoutResponse,
  IUpdateUserRequest,
  IPostForgotPasswordRequest,
  IPostForgotPasswordResponse,
  IGetGoogleLoginRequest,
  IResetPasswordRequest,
} from './DataforceApi.interfaces'

import { installDataforceInterceptors } from './DataforceApi.interceptors'

export class DataforceApiClass {
  private api: AxiosInstance

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_DATAFORCE_API_URL,
      timeout: 10000,
    })

    installDataforceInterceptors(this.api)
  }

  public async signUp(data: IPostSignupRequest): Promise<IPostSignupResponse> {
    const { data: responseData } = await this.api.post('/auth/signup', data, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async signIn(data: IPostSignInRequest): Promise<IPostSignInResponse> {
    const { data: responseData } = await this.api.post('/auth/signin', data, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async googleLogin(params: IGetGoogleLoginRequest): Promise<IPostSignInResponse> {
    const { data } = await this.api.get('/auth/google/callback', {
      skipInterceptors: true,
      params,
    })

    return data
  }

  public async refreshToken(data: IPostRefreshTokenRequest): Promise<IPostRefreshTokenResponse> {
    const { data: responseData } = await this.api.post('/auth/refresh', data, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async forgotPassword(
    data: IPostForgotPasswordRequest,
  ): Promise<IPostForgotPasswordResponse> {
    const { data: responseData } = await this.api.post('/auth/forgot-password', data, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async getMe(): Promise<IGetUserResponse> {
    const { data: responseData } = await this.api.get('/auth/users/me')

    return responseData
  }

  public async updateUser(data: IUpdateUserRequest): Promise<IPostChangePasswordResponse> {
    const { data: responseData } = await this.api.patch('/auth/users/me', data)

    return responseData
  }

  public async deleteUser(): Promise<TDeleteAccountResponse> {
    const { data: responseData } = await this.api.delete('/auth/users/me')

    return responseData
  }

  public async logout(data: IPostLogoutRequest): Promise<TPostLogoutResponse> {
    const { data: responseData } = await this.api.post('/auth/logout', data)

    return responseData
  }
  
  public async resetPassword(data: IResetPasswordRequest) {
    await this.api.post('/auth/reset-password', data)
  }
}
