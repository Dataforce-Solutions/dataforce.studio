<template>
  <d-toast style="top: 105px" />
  <d-confirm-dialog style="width: 21.75rem" />
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
import { useAppScrollbarFix } from './hooks/useAppScrollbarFix'

import { DataProcessingWorker } from './lib/data-processing/DataProcessingWorker'

const authStore = useAuthStore()
const themeStore = useThemeStore()
useAppScrollbarFix()

onBeforeMount(() => {
  DataProcessingWorker.initPyodide()
  authStore.checkIsLoggedId()
  themeStore.checkTheme()
})
</script>

<style scoped></style>
