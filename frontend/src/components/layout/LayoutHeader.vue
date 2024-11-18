<template>
  <header class="header">
    <router-link :to="{ name: 'home' }" class="logo">
      <img :src="logo" alt="Dataforce Studio" class="logo-img" />
    </router-link>
    <div v-if="isActivesVisible" class="actives">
      <div class="buttons">
        <d-button label="Log in" variant="link" @click="$router.push({ name: 'sign-in' })" />
        <d-button label="Sign up" @click="$router.push({ name: 'sign-up' })" />
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import logo from '@/assets/img/logo.svg'

defineProps({
  isActivesVisible: {
    type: Boolean,
    default: true,
  },
})
</script>

<style scoped>
.header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 40px;
  background-color: #2673fd;
}
.logo {
}
.logo-img {
  max-width: 202px;
}
.actives {
}
.buttons {
  display: flex;
  gap: 11px;
  align-items: center;
}
</style>
