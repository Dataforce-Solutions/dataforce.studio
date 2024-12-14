<template>
  <authorization-wrapper title="Reset password" :image="MainImage">
    <template #form>
      <d-form
        v-slot="$form"
        :initialValues
        :resolver
        :validateOnValueUpdate="false"
        :validateOnSubmit="true"
        :validateOnBlur="true"
        @submit="onFormSubmit"
        class="form"
      >
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
            <label for="password" class="label">New password</label>
          </d-float-label>
          <d-message v-if="$form.password?.invalid" severity="error" size="small" variant="simple">
            {{ $form.password.error?.message }}
          </d-message>
        </div>
        <div class="input-wrapper">
          <d-float-label variant="on">
            <d-password
              id="password_confirm"
              name="password_confirm"
              fluid
              autocomplete="off"
              toggleMask
              :feedback="false"
            />
            <label for="password_confirm" class="label">Confirm password</label>
          </d-float-label>
          <d-message
            v-if="$form.password_confirm?.invalid"
            severity="error"
            size="small"
            variant="simple"
            >{{ $form.password_confirm.error?.message }}
          </d-message>
        </div>
        <d-button type="submit" label="Save" rounded />
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
import type { FormSubmitEvent } from '@primevue/forms'

import { useUserStore } from '@/stores/user'
import { resetPasswordInitialValues } from '@/utils/forms/initialValues'
import { resetPasswordResolver } from '@/utils/forms/resolvers'

const userStore = useUserStore()

const initialValues = ref(resetPasswordInitialValues)

const resolver = ref(resetPasswordResolver)

const onFormSubmit = async ({ valid }: FormSubmitEvent) => {
  if (!valid) {
    console.error('Form invalid')

    return
  }

  userStore.resetPassword()
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
