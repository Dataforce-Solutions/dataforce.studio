<template>
  <d-form :initialValues :resolver class="wrapper" @submit="onFormSubmit">
    <div class="inputs">
      <d-float-label variant="on">
        <d-password id="oldPassword" name="current_password" :feedback="false" fluid />
        <label for="oldPassword">Old password</label>
      </d-float-label>
      <d-float-label variant="on">
        <d-password id="newPassword" name="new_password" :feedback="false" fluid />
        <label for="newPassword">New password</label>
      </d-float-label>
      <d-float-label variant="on">
        <d-password id="confirmPassword" name="confirmPassword" :feedback="false" fluid />
        <label for="confirmPassword">Confirm password</label>
      </d-float-label>
    </div>
    <div class="actives">
      <d-button label="save" type="submit" />
      <d-button label="Forgot password?" variant="link" />
    </div>
  </d-form>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { ref } from 'vue'
import { z } from 'zod'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const initialValues = ref({
  current_password: '',
  new_password: '',
  confirmPassword: '',
})
const resolver = ref(
  zodResolver(
    z
      .object({
        current_password: z
          .string()
          .min(8, { message: 'The password must be more than 8 characters' }),
        new_password: z.string().min(8, { message: 'The password must be more than 8 characters' }),
        confirmPassword: z
          .string()
          .min(8, { message: 'The password must be more than 8 characters' }),
      })
      .refine((data) => data.new_password === data.confirmPassword, {
        message: 'Passwords must match',
        path: ['confirmPassword'],
      }),
  ),
)

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) {
    console.error('Invalid Data')

    return
  }

  console.log(values)

  const data = {
    current_password: values.current_password,
    new_password: values.new_password,
  }

  try {
    await userStore.changePassword(data)

    console.log('its ok')
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped>
.wrapper {
  padding-top: 10px;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 20px;
}
</style>
