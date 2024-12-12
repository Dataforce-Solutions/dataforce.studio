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
