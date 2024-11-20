<template>
  <d-form :initialValues :resolver class="wrapper" @submit="onFormSubmit">
    <div class="left">
      <div class="inputs">
        <d-float-label variant="on">
          <d-input-text id="username" name="username" />
          <label for="username">Name</label>
        </d-float-label>
        <d-float-label variant="on">
          <d-input-text id="email" name="email" />
          <label for="email">Email</label>
        </d-float-label>
      </div>
      <d-button variant="link" label="Change password" @click="$emit('showChangePassword')" />
      <div class="actives">
        <d-button label="save" type="submit" />
        <d-button
          label="delete account"
          variant="link"
          severity="danger"
          @click="onDeleteButtonClick"
        />
      </div>
    </div>
    <div class="right">
      <image-input width="150px" @on-image-change="onAvatarChange" />
    </div>
  </d-form>
</template>

<script setup lang="ts">
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { ref } from 'vue'
import { z } from 'zod'
import type { FormSubmitEvent } from '@primevue/forms'
import ImageInput from '../ui/ImageInput.vue'

import { useUserStore } from '@/stores/user'

type TEmits = {
  (e: 'showChangePassword'): void
  (e: 'close'): void
}

const emit = defineEmits<TEmits>()

const userStore = useUserStore()

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
  gap: 48px;
  align-items: flex-start;
}
.left {
  flex: 1 1 auto;
}
.right {
  flex: 0 0 auto;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.left {
  padding-top: 10px;
}
</style>
