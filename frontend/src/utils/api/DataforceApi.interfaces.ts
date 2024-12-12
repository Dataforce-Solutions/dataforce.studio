export interface IPostSignupRequest {
  email: string
  password: string
  full_name?: string
}

export interface IPostSignupResponse {
  access_token: string
  token_type: string
  refresh_token: string
}

export interface IPostSignInRequest {
  email: string
  password: string
  grant_type?: string
  scope?: string
  client_id?: string
  client_secret?: string
}

export interface IPostSignInResponse {
  access_token: string
  token_type: string
  refresh_token: string
}

export interface IPostRefreshTokenRequest {
  refresh_token: string
}

export interface IPostRefreshTokenResponse {
  access_token: string
  token_type: string
  refresh_token: string
}

export interface IPostChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface IPostChangePasswordResponse {
  detail: string
}

export type TDeleteAccountResponse = string

export interface IGetUserResponse {
  email: string
  full_name: string
  disabled: boolean
  auth_method: string
  photo: string
}

export interface IPostLogoutRequest {
  refresh_token: string
}

export type TPostLogoutResponse = string

export interface IUpdateUserRequest {
  full_name?: string
  current_password?: string
  new_password?: string
  photo?: File
  email?: string
}

export interface IPostForgotPasswordRequest {
  email: string
}

export interface IPostForgotPasswordResponse {
  detail: string
}

export interface IGetGoogleLoginRequest {
  code: string
}