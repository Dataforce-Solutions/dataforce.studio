<template>
  <div class="wrapper">
    <d-button severity="help" class="user-open-button" @click="toggleMenu">
      <d-avatar :image="getUserAvatar" shape="circle"></d-avatar>
      <span>{{ mainButtonLabel }}</span>
      <chevron-down :size="14" />
    </d-button>
    <d-dialog v-model:visible="isDialogVisible" position="topright" :closable="false" :draggable="false" modal dismissableMask :style="{ marginTop: '85px'}" class="modal-transparent-mask">
       <template #header>
          <header class="header">
            <d-avatar :image="getUserAvatar" shape="circle" size="large"></d-avatar>
            <div class="user-info">
              <div class="user-name">{{ getUserFullName }}</div>
              <div class="user-email">{{ getUserEmail }}</div>
            </div>
          </header>
        </template>
      <d-menu :model="menuItems" :style="{backgroundColor:'transparent',border:'none',padding:'0',minWidth:'228px'}">
        <template #item="{ item, props }">
          <div v-if="item.themeToggle" class="appearance">
            <span>{{ item.label }}</span>
            <div class="custom-toggle">
              <div class="custom-toggle-wrapper" @click="themeStore.changeTheme()">
                <div class="custom-toggle-item custom-toggle-item-active">
                  <sun :size="14" />
                </div>
                <div class="custom-toggle-item">
                  <moon :size="14" />
                </div>
              </div>
            </div>
          </div>
          <button type="button" v-else class="menu-item" v-bind="props.action" @click="item.action">
            <span>{{ item.label }}</span>
          </button>
        </template>
      </d-menu>
      <template #footer>
          <footer class="footer">
            <button type="button" class="logout-button" @click="onButtonLogoutClick">Log out</button>
          </footer>
        </template>
    </d-dialog>
  </div>
  <d-dialog v-model:visible="isSettingsPopupVisible" modal :style="{ width: '37rem' }">
    <template #header>
      <h2 style="font-weight: 600; font-size: 20px">ACCOUNT SETTINGS</h2>
    </template>
    <user-settings
      @show-change-password="onShowChangePassword"
      @close="isSettingsPopupVisible = !isSettingsPopupVisible"
    />
  </d-dialog>
  <d-dialog v-model:visible="isChangePasswordPopupVisible" modal :style="{ width: '37rem' }">
    <template #header>
      <h2 style="font-weight: 600; font-size: 20px">CHANGE PASSWORD</h2>
    </template>
    <user-change-password @success="onChangePasswordSuccess" />
  </d-dialog>
</template>

<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'

import UserSettings from './UserSettings.vue'
import UserChangePassword from './UserChangePassword.vue'

import { ChevronDown, Sun, Moon } from 'lucide-vue-next'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useToast } from 'primevue/usetoast'
import { passwordChangedSuccessToast } from '@/lib/primevue/data/toasts'

const userStore = useUserStore()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const toast = useToast()

const showChangePasswordSuccess = () => {
  toast.add(passwordChangedSuccessToast)
}

const { getUserEmail, getUserFullName, getUserAvatar } = storeToRefs(userStore)

const mainButtonLabel = computed(() => getUserFullName.value || 'Account')

const isDialogVisible = ref(false);
const menuItems = ref([
  {
    label: 'Account',
    action: () => {
      isSettingsPopupVisible.value = true
    },
  },
  {
    label: 'Feedback',
    action: () => {},
  },
  {
    label: 'Community',
    action: () => {},
  },
  {
    label: 'About',
    action: () => {},
  },
  {
    label: 'Appearance',
    themeToggle: true,
  },
])

const isSettingsPopupVisible = ref(false)
const isChangePasswordPopupVisible = ref(false)

const toggleMenu = () => {
  isDialogVisible.value = !isDialogVisible.value
}

const onButtonLogoutClick = async () => {
  await authStore.logout()
}

const onShowChangePassword = () => {
  isSettingsPopupVisible.value = false
  isChangePasswordPopupVisible.value = true
}

const onChangePasswordSuccess = () => {
  isSettingsPopupVisible.value = true
  isChangePasswordPopupVisible.value = false

  setTimeout(() => {
    showChangePasswordSuccess()
  }, 100)
}
</script>

<style scoped>
.wrapper {
  --menu-item-color: #334155;
}
.user-open-button {
  font-size: 1.125rem;
  font-weight: 500;
  padding: 8px;
  display: flex;
  color: var(--color-text);
}

@media (any-hover: hover) {
  .user-open-button:not(:disabled):hover {
    color: var(--color-text);
  }
}

.content {
  padding: 24px 16px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 260px;
  margin-top: 24px;
  box-shadow: var(--card-shadow);
}

.header {
  width: 100%;
  display: flex;
  gap: 12px;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-divider-border);
}

.user-info-avatar {
  width: 42px;
  height: 42px;
}
.user-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.user-email {
  color: var(--color-text-muted);
  font-size: 14px;
}

.buttons {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.menu-item {
  padding: 7px;
  text-align: left;
}

.appearance {
  display: flex;
  justify-content: space-between;
  padding: 7px;
  gap: 5px;
  align-items: center;
}

.custom-toggle {
  --toggleswitch-background: #f1f5f9;
  --toggle-switch-handle-color: #64748b;
  --toggle-switch-handle-checked-color: #0a0a0a;
  --toggleswitch-handle-checked-background: #fff;
}
.custom-toggle-wrapper {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 16px;
  background-color: var(--toggleswitch-background);
  cursor: pointer;
}
.custom-toggle-item {
  width: 18px;
  height: 18px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: transparent;
  color: var(--toggle-switch-handle-color);
}

.custom-toggle-item-active {
  color: var(--toggle-switch-handle-checked-color);
  background-color: var(--toggleswitch-handle-checked-background);
}

.footer {
  width: 100%;
  padding-top: 24px;
  border-top: 1px solid var(--color-divider-border);
}

.logout-button {
  padding: 4px;
  color: var(--p-orange-600);
  cursor: pointer;
}
</style>
