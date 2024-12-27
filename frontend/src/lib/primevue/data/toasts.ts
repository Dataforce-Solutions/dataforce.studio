import type { ToastMessageOptions } from 'primevue'

export const userProfileUpdateSuccessToast = (detail?: string): ToastMessageOptions => ({
  severity: 'success',
  summary: 'Success',
  detail: detail || 'User profile updated successfully',
  life: 3000,
})

export const passwordChangedSuccessToast: ToastMessageOptions = {
  severity: 'success',
  summary: 'Success',
  detail: 'Password has been changed!',
  life: 3000,
}

export const emailSentVerifyToast: ToastMessageOptions = {
  severity: 'success',
  summary: 'Email sent',
  detail:
    'Thanks! An email was sent to verify your account. If you don’t receive an email, please contact us.',
  life: 3000,
}

export const passwordResetSuccessToast: ToastMessageOptions = {
  severity: 'success',
  summary: 'Success',
  detail: 'Password has been changed!',
  life: 3000,
}

export const trainingErrorToast = (detail?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: 'Error',
  detail: detail || 'Training error. Change data for training.',
  life: 3000,
})

export const predictErrorToast = (detail?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: 'Error',
  detail: detail || 'Prediction error. Data is not correct.',
  life: 3000,
})

export const incorrectFileTypeErrorToast: ToastMessageOptions = {
  severity: 'error',
  summary: 'Error',
  detail: 'This file format is not supported',
  life: 3000,
}
