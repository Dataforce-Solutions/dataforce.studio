<template>
  <div class="wrapper">
    <LayoutHeader class="header" :is-actives-visible="false" />
    <main class="page">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import LayoutHeader from '@/components/layout/LayoutHeader.vue'
</script>

<style scoped>
.page {
  padding: 75px 40px;
}
</style>
