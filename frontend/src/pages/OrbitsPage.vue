<template>
  <div class="content">
    <h2 class="sub-title">Coming Soon</h2>
    <h1 class="title">Orbits <img :src="image" width="42" height="42" alt="Orbits" /></h1>
    <p class="text">
      Orbits is a zero-trust orchestration module for managing and deploying models across any
      infrastructure — cloud or on-prem.
    </p>
    <ui-email-form class="form" />
  </div>
</template>

<script setup lang="ts">
import image from '@/assets/img/orbits.svg'
import UiEmailForm from '@/components/ui/UiEmailForm.vue'
</script>

<style scoped>
.content {
  min-height: calc(100vh - 130px);
  max-width: 512px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.sub-title {
  margin-bottom: 12px;
  font-size: 20px;
  color: var(--p-text-muted-color);
}

.title {
  margin-bottom: 24px;
  font-size: 48px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.text {
  margin-bottom: 44px;
  font-size: 16px;
  line-height: 1.5;
  margin-bottom: 44px;
}

.form {
}
</style>
