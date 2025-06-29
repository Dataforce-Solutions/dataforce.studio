import type { ConfirmationOptions } from 'primevue/confirmationoptions'

export const dashboardFinishConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: "Before finishing, please ensure you've downloaded your predictions.",
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

export const runOptimizationConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: "Please confirm that you've reviewed all settings before proceeding.",
  header: 'Ready to start optimization?',
  rejectProps: {
    label: 'cancel',
    severity: 'secondary',
  },
  acceptProps: {
    label: 'confirm and run',
  },
  accept,
})

export const leaveOrganizationConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message:
    'You’ll lose access to all workspaces and data within this organization. This action can’t be undone.',
  header: 'Leave this organization?',
  rejectProps: {
    label: 'cancel',
  },
  acceptProps: {
    label: 'leave',
    severity: 'warn',
    outlined: true,
  },
  accept,
})

export const deleteUserConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: 'Deleting this account is a permanent action and cannot be reversed.',
  header: 'Delete this user?',
  rejectProps: {
    label: 'cancel',
  },
  acceptProps: {
    label: 'delete',
    severity: 'warn',
    outlined: true,
  },
  accept,
})

export const deleteOrbitConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: 'Deleting this orbit is a permanent action and cannot be reversed.',
  header: 'Delete orbit?',
  rejectProps: {
    label: 'cancel',
  },
  acceptProps: {
    label: 'delete',
    severity: 'warn',
    outlined: true,
  },
  accept,
})

export const deleteCollectionConfirmOptions = (accept: () => void): ConfirmationOptions => ({
  message: 'This action is permanent and cannot be undone.',
  header: 'Delete collection?',
  rejectProps: {
    label: 'cancel',
  },
  acceptProps: {
    label: 'delete',
    severity: 'warn',
    outlined: true,
  },
  accept,
})

export const deleteModelConfirmOptions = (
  accept: () => void,
  count: number,
): ConfirmationOptions => ({
  message: 'This action is permanent and cannot be undone.',
  header: count > 1 ? `Delete ${count}  models?` : 'Delete model?',
  rejectProps: {
    label: 'cancel',
  },
  acceptProps: {
    label: count > 1 ? 'delete models' : 'delete model',
    severity: 'warn',
    outlined: true,
  },
  accept,
})
