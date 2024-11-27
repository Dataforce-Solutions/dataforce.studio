<template>
  <d-toast />
  <authorization-wrapper
    title="Forgot password?"
    sub-title="Enter your email to receive a new password"
    :image="MainImage"
  >
    <template #form>
      <d-form v-slot="$form" :initialValues :resolver @submit="onFormSubmit" class="form">
        <div class="input-wrapper">
          <d-float-label variant="on">
            <d-input-text id="email" name="email" type="email" autocomplete="off" fluid />
            <label for="email" class="label">Email</label>
          </d-float-label>
          <d-message v-if="$form.email?.invalid" severity="error" size="small" variant="simple">
            {{ $form.email.error?.message }}
          </d-message>
        </div>
        <d-button type="submit" label="Sign up" rounded />
      </d-form>
    </template>
    <template #footer>
      <router-link :to="{ name: 'sign-in' }" class="link">Back to Sign in</router-link>
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'

import MainImage from '@/assets/img/sign-up.png'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import type { FormSubmitEvent } from '@primevue/forms'

import { useToast } from 'primevue/usetoast'
const toast = useToast()

const showSuccess = () => {
  toast.add({
    severity: 'success',
    summary: 'Email sent',
    detail:
      'Thanks! A new password has been sent to your email account. You can change it later in your user account settings.',
    life: 3000,
  })
}

const initialValues = ref({
  email: '',
})

const resolver = ref(
  zodResolver(
    z.object({
      email: z.string().email({ message: 'Email is incorrect' }),
    }),
  ),
)

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) {
    console.error('Form invalid')

    return
  }

  showSuccess()
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
</style>
