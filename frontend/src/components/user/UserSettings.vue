<template>
  <d-form
    class="wrapper"
    ref="formRef"
    v-slot="$form"
    :initialValues
    :resolver
    :validateOnValueUpdate="false"
    :validateOnSubmit="true"
    :validateOnBlur="true"
    @submit="onFormSubmit"
  >
    <!--<image-input
      @on-image-change="onAvatarChange"
      class="image-input"
      :image="userStore.getUserAvatar"
    />-->
    <d-avatar
      :image="userStore.getUserAvatar"
      shape="circle"
      size="xlarge"
      class="image-input"
    ></d-avatar>
    <div class="inputs">
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text
              ref="usernameRef"
              id="username"
              name="username"
              fluid
              v-model="initialValues.username"
            />
            <d-input-icon>
              <component
                :is="getCurrentInputIcon('username')"
                :size="14"
                @click="onIconClick('username')"
              />
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="username">Name</label>
        </d-float-label>
        <d-message v-if="$form.username?.invalid" severity="error" size="small" variant="simple">
          {{ $form.username.error?.message }}
        </d-message>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text
              ref="emailRef"
              id="email"
              name="email"
              fluid
              :disabled="isUserLoggedWithSSO"
              v-model="initialValues.email"
            />
            <d-input-icon v-if="!isUserLoggedWithSSO">
              <component
                :is="getCurrentInputIcon('email')"
                :size="14"
                @click="onIconClick('email')"
              />
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="email">Email</label>
        </d-float-label>
        <d-message v-if="$form.email?.invalid" severity="error" size="small" variant="simple">
          {{ $form.email.error?.message }}
        </d-message>
      </div>
    </div>
    <d-message v-if="formResponseError" severity="error" size="small" variant="simple">
      {{ formResponseError }}
    </d-message>
    <button
      v-if="!isUserLoggedWithSSO"
      class="link change-password-link"
      @click="$emit('showChangePassword')"
    >
      Change password
    </button>
    <div class="footer">
      <d-button
        label="delete account"
        severity="warn"
        variant="outlined"
        @click="deleteAccountConfirm"
      />
      <d-button label="save changes" type="submit" :disabled="userStore.isUserDisabled" />
    </div>
  </d-form>
  <d-confirm-dialog style="width: 21.75rem"></d-confirm-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { FormSubmitEvent } from '@primevue/forms'
import ImageInput from '../ui/ImageInput.vue'

import { useInputIcon } from '@/hooks/useInputIcon'
import { useUserStore } from '@/stores/user'
import { useConfirm } from 'primevue/useconfirm'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'

import type { IUpdateUserRequest } from '@/utils/api/DataforceApi.interfaces'
import { userSettingResolver } from '@/utils/forms/resolvers'
import { userProfileUpdateSuccessToast } from '@/utils/primevue/data/toasts'
import { storeToRefs } from 'pinia'

const userStore = useUserStore()
const { getUserFullName, getUserEmail, isUserLoggedWithSSO } = storeToRefs(userStore)

const confirm = useConfirm()
const router = useRouter()
const toast = useToast()

type TEmits = {
  (e: 'showChangePassword'): void
  (e: 'close'): void
}

defineEmits<TEmits>()

const initialValues = ref({
  username: getUserFullName.value || '',
  email: getUserEmail.value || '',
})
const resolver = ref(userSettingResolver)

const formRef = ref()
const usernameRef = ref<HTMLInputElement | null>()
const emailRef = ref<HTMLInputElement | null>()

const { getCurrentInputIcon, onIconClick } = useInputIcon(
  [usernameRef, emailRef],
  formRef,
  initialValues,
)

const newAvatar = ref<File | null>(null)
const formResponseError = ref('')

const showSuccess = (detail?: string) => {
  toast.add(userProfileUpdateSuccessToast(detail))
}

const deleteAccountConfirm = () => {
  confirm.require({
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
    accept: async () => {
      await userStore.deleteAccount()

      router.push({ name: 'sign-up' })
    },
  })
}

const onAvatarChange = (payload: File | null) => {
  newAvatar.value = payload
}

const onFormSubmit = async ({ valid }: FormSubmitEvent) => {
  if (!valid) return

  const data: IUpdateUserRequest = {}

  if (userStore.getUserFullName !== initialValues.value.username)
    data.full_name = initialValues.value.username

  if (userStore.getUserEmail !== initialValues.value.email) data.email = initialValues.value.email

  if (newAvatar.value) data.photo = newAvatar.value

  if (!Object.keys(data).length) return

  try {
    const response = await userStore.updateUser(data)

    showSuccess(response.detail)
  } catch (e: any) {
    formResponseError.value = e.response.data.detail || 'Form is invalid'
  }
}

watch(
  initialValues,
  () => {
    formResponseError.value = ''
  },
  { deep: true },
)
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

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
</style>
