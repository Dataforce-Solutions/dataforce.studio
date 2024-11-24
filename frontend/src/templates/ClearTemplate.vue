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
.header {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
}

.page {
  padding: 160px 40px 20px;
}

@media (max-width: 768px) {
  .page {
    padding: 120px 20px 20px;
  }
}
</style>
