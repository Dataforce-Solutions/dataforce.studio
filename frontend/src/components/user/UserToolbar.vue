<template>
  <div class="wrapper">
    <d-button :label="mainButtonLabel" @click="togglePopover">
      <template #icon>
        <img :src="avatarPlaceholder" alt="" class="avatar" />
      </template>
    </d-button>
    <d-popover ref="popover">
      <div class="content">
        <header class="header"></header>
        <div class="buttons">
          <d-button
            label="Account"
            variant="link"
            class="button"
            @click="isSettingsPopupVisible = !isSettingsPopupVisible"
          />
          <d-button label="Feedback" variant="link" class="button" />
          <d-button label="Community" variant="link" class="button" />
          <d-button variant="link">
            <span>About</span>
            <span>v2024.09 alpha1</span>
          </d-button>
          <div>
            <span>Appearance</span>
            <d-toggle-button v-model="isDarkTheme" on-label="dark" off-label="light" />
          </div>
        </div>
        <footer class="footer">
          <d-button
            label="logout"
            variant="link"
            severity="danger"
            class="button"
            @click="onButtonLogoutClick"
          />
        </footer>
      </div>
    </d-popover>
  </div>
  <d-dialog
    v-model:visible="isSettingsPopupVisible"
    modal
    header="Account settings"
    :style="{ width: '41rem' }"
  >
    <user-settings
      @show-change-password="onShowChangePassword"
      @close="isSettingsPopupVisible = !isSettingsPopupVisible"
    />
  </d-dialog>
  <d-dialog
    v-model:visible="isChangePasswordPopupVisible"
    modal
    header="Change password"
    :style="{ width: '41rem' }"
  >
    <user-change-password />
  </d-dialog>
</template>

<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'

import avatarPlaceholder from '@/assets/img/avatar-placeholder.png'

import UserSettings from './UserSettings.vue'
import UserChangePassword from './UserChangePassword.vue'

import { useAuthStore } from '@/stores/auth'

const userStore = useUserStore()
const authStore = useAuthStore()

const { getUserEmail, getUserFullName } = storeToRefs(userStore)

const mainButtonLabel = computed(() => getUserFullName.value || getUserEmail.value)

const popover = ref()
const isDarkTheme = ref(false)
const isSettingsPopupVisible = ref(false)
const isChangePasswordPopupVisible = ref(false)

const togglePopover = (event: MouseEvent) => {
  popover.value.toggle(event)
}

const onButtonLogoutClick = async () => {
  await authStore.logout()
}

const onShowChangePassword = () => {
  isSettingsPopupVisible.value = false
  isChangePasswordPopupVisible.value = true
}
</script>

<style scoped>
.buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.button {
  justify-content: flex-start;
}

.avatar {
  width: 24px;
  height: 24px;
  object-fit: cover;
  border-radius: 50%;
}
</style>
