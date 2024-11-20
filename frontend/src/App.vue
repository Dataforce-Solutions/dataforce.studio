<template>
  <app-template>
    <RouterView />
  </app-template>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppTemplate from './templates/AppTemplate.vue'
import { onBeforeMount } from 'vue'

import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

onBeforeMount(() => {
  authStore.checkIsLoggedId()
})
</script>

<style scoped></style>
