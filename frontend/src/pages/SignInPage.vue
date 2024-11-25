<template>
  <authorization-wrapper
    title="Sign in"
    sub-title="Welcome to DataForce Studio"
    :image="MainImage"
    :services="services"
  >
    <template #form>
      <d-form v-slot="$form" :initialValues :resolver @submit="onFormSubmit" class="form">
        <div class="inputs">
          <div class="input-wrapper">
            <d-float-label variant="on">
              <d-input-text id="email" name="email" fluid type="text" autocomplete="off" />
              <label for="email" class="label">Email</label>
            </d-float-label>
            <d-message v-if="$form.email?.invalid" severity="error" size="small" variant="simple">
              {{ $form.email.error?.message }}
            </d-message>
          </div>
          <div class="input-wrapper">
            <d-float-label variant="on">
              <d-password
                id="password"
                name="password"
                fluid
                autocomplete="off"
                toggleMask
                :feedback="false"
              />
              <label for="password" class="label">Password</label>
            </d-float-label>
            <d-message v-if="$form.password?.invalid" severity="error" size="small" variant="simple"
              >{{ $form.password.error?.message }}
            </d-message>
          </div>
        </div>
        <d-button type="submit" label="Sign up" rounded />
      </d-form>
    </template>
    <template #footer>
      <div class="footer-message">
        <span>Don`t have an account? </span>
        <router-link :to="{ name: 'sign-up' }" class="link">Sign up</router-link>
      </div>
      <router-link :to="{ name: 'home' }" class="link">Forgot password?</router-link>
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
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

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

    router.push({ name: 'home' })
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
.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.input-wrapper:has(.p-filled) .label {
  opacity: 0;
}

.input-wrapper:has(input:focus) .label {
  opacity: 1;
}

.footer-message {
  margin-bottom: 16px;
}
</style>
