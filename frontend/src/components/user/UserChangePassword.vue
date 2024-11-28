<template>
  <d-form v-slot="$form" :initialValues :resolver class="wrapper" @submit="onFormSubmit">
    <div class="inputs">
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-password id="oldPassword" name="current_password" :feedback="false" fluid />
          <label class="label" for="oldPassword">Old password</label>
        </d-float-label>
        <d-message
          v-if="$form.current_password?.invalid"
          severity="error"
          size="small"
          variant="simple"
        >
          {{ $form.current_password.error?.message }}
        </d-message>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-password id="newPassword" name="new_password" :feedback="false" fluid toggleMask />
          <label class="label" for="newPassword">New password</label>
        </d-float-label>
        <d-message
          v-if="$form.new_password?.invalid"
          severity="error"
          size="small"
          variant="simple"
        >
          {{ $form.new_password.error?.message }}
        </d-message>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-password id="confirmPassword" name="confirmPassword" :feedback="false" fluid />
          <label class="label" for="confirmPassword">Confirm password</label>
        </d-float-label>
        <d-message
          v-if="$form.confirmPassword?.invalid"
          severity="error"
          size="small"
          variant="simple"
        >
          {{ $form.confirmPassword.error?.message }}
        </d-message>
      </div>
    </div>
    <div class="footer">
      <d-button
        label="Forgot password?"
        variant="link"
        @click="$router.push({ name: 'forgot-password' })"
      />
      <d-button label="save" type="submit" />
    </div>
  </d-form>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { ref } from 'vue'
import { z } from 'zod'
import { useUserStore } from '@/stores/user'

const emit = defineEmits(['success'])

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

    emit('success')
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
  margin-bottom: 32px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.footer {
  display: flex;
  justify-content: space-between;
}
</style>
