import type { ConfirmationOptions } from 'primevue/confirmationoptions'

export const dashboardFinishConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: 'Before finishing, make sure you have saved all the necessary data.',
  header: 'Are you sure?',
  rejectProps: {
    label: 'cancel',
    outlined: true,
  },
  acceptProps: {
    label: 'finish',
  },
  accept,
})

export const deleteAccountConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: 'Deleting your account is permanent and irreversible. ',
  header: 'Are you sure?',
  rejectProps: {
    label: 'cancel',
  },
  acceptProps: {
    label: 'delete account',
    severity: 'warn',
    outlined: true,
  },
  accept,
})
