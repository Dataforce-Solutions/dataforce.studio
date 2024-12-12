<template>
  <d-toast style="top: 105px" />
  <app-template>
    <RouterView />
  </app-template>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppTemplate from './templates/AppTemplate.vue'
import { onBeforeMount } from 'vue'

import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

const authStore = useAuthStore()
const themeStore = useThemeStore()

onBeforeMount(() => {
  authStore.checkIsLoggedId()

  themeStore.checkTheme()
})
</script>

<style scoped></style>
