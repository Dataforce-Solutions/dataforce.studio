<template>
  <d-form :initialValues :resolver class="wrapper" @submit="onFormSubmit">
    <image-input @on-image-change="onAvatarChange" class="image-input" />
    <div class="inputs">
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text ref="usernameRef" id="username" name="username" fluid />
            <d-input-icon>
              <component :is="getCurrentInputIcon('username')" :size="14" />
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="username">Name</label>
        </d-float-label>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text ref="emailRef" id="email" name="email" fluid />
            <d-input-icon>
              <component :is="getCurrentInputIcon('email')" :size="14" />
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="email">Email</label>
        </d-float-label>
      </div>
    </div>
    <button class="link change-password-link" @click="$emit('showChangePassword')">
      Change password
    </button>
    <div class="footer">
      <d-button
        label="delete account"
        severity="warn"
        variant="outlined"
        @click="onDeleteButtonClick"
      />
      <d-button label="save changes" type="submit" />
    </div>
  </d-form>
</template>

<script setup lang="ts">
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { ref } from 'vue'
import { z } from 'zod'
import type { FormSubmitEvent } from '@primevue/forms'
import ImageInput from '../ui/ImageInput.vue'
import { useInputIcon } from '@/hooks/useInputIcon'

import { useUserStore } from '@/stores/user'

type TEmits = {
  (e: 'showChangePassword'): void
  (e: 'close'): void
}

const emit = defineEmits<TEmits>()

const userStore = useUserStore()

const usernameRef = ref<HTMLInputElement | null>()
const emailRef = ref<HTMLInputElement | null>()

const { getCurrentInputIcon } = useInputIcon([usernameRef, emailRef])

const initialValues = ref({
  username: userStore.getUserFullName || '',
  email: userStore.getUserEmail || '',
})

const resolver = ref(
  zodResolver(
    z.object({
      username: z.string().min(3, { message: 'Name must be more 3 characters' }),
      email: z.string().email({ message: 'Email is incorrect' }),
    }),
  ),
)

const newAvatarFile = ref<File | null>(null)
const fileupload = ref(null)

const onAvatarChange = (payload: File | null) => {
  newAvatarFile.value = payload
}

const onDeleteButtonClick = async () => {
  try {
    await userStore.deleteAccount()

    emit('close')
  } catch (e) {
    console.error(e)
  }
}

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) {
    console.error('Invalid Data')

    return
  }

  const data = {
    username: values.username,
    email: values.email,
  }

  //   if (newAvatarFile.value) data.avatar = newAvatarFile.value

  console.log(data)
}
</script>

<style scoped>
.wrapper {
  display: flex;
  flex-direction: column;
}

.image-input {
  align-self: flex-start;
  margin-bottom: 24px;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-bottom: 12px;
}

.change-password-link {
  align-self: flex-start;
  padding: 10px 0;
}

.footer {
  padding-top: 32px;
  display: flex;
  justify-content: space-between;
}
</style>
