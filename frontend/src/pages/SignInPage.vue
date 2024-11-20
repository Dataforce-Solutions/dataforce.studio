<template>
  <authorization-wrapper
    title="Sign in"
    sub-title="Welcome to DataForce Studio"
    :image="MainImage"
    :services="services"
  >
    <template #form>
      <d-form :initialValues :resolver @submit="onFormSubmit" class="form">
        <div class="inputs">
          <div>
            <d-input-text name="email" type="text" placeholder="Email" fluid />
          </div>
          <div>
            <d-input-text name="password" type="text" placeholder="Password" fluid />
          </div>
        </div>
        <d-button type="submit" severity="secondary" label="Sign in" />
      </d-form>
    </template>
    <template #footer>
      <div>
        <span>Don`t have an account? </span>
        <router-link :to="{ name: 'sign-up' }">Sign up</router-link>
      </div>
      <router-link :to="{ name: 'home' }">Forgot password?</router-link>
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import type { IAuthorizationService } from '@/components/authorization/types'

import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'
import MainImage from '@/assets/img/sign-up.png'
import GoogleIcon from '@/assets/img/authorization-services/google.svg'
import MicrosoftIcon from '@/assets/img/authorization-services/microsoft.svg'
import GitHubIcon from '@/assets/img/authorization-services/github.svg'

import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import { ref } from 'vue'
import type { FormSubmitEvent } from '@primevue/forms'
import type { IPostSignInRequest } from '@/utils/api/DataforceApi.interfaces'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const services: IAuthorizationService[] = [
  {
    id: 'google',
    label: 'Sign in with Google',
    icon: GoogleIcon,
    action: () => console.log('Google'),
  },
  {
    id: 'microsoft',
    label: 'Sign in with Microsoft',
    icon: MicrosoftIcon,
    action: () => console.log('Microsoft'),
  },
  {
    id: 'github',
    label: 'Sign in with Github',
    icon: GitHubIcon,
    action: () => console.log('Github'),
  },
]

const initialValues = ref({
  email: '',
  password: '',
})

const resolver = ref(
  zodResolver(
    z.object({
      email: z.string().email({ message: 'Email is incorrect' }),
      password: z.string().min(8, { message: 'Minimum password length 8 characters' }),
    }),
  ),
)

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) {
    console.error('Form invalid')

    return
  }

  const data: IPostSignInRequest = {
    username: values.email,
    password: values.password,
  }

  try {
    await authStore.signIn(data)
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
