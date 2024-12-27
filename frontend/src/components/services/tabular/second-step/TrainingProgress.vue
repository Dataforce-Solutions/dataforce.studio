<template>
  <div class="wrapper">
    <div class="loader">
      <ui-loader />
    </div>
    <div class="content">
      <h2 class="title">Training in progress...</h2>
      <div class="text">
        Training duration may vary depending on the volume of data, typically ranging from 1 to 10
        minutes.
      </div>
      <progress-bar mode="indeterminate" style="height: 6px" />
      <div class="info">Estimated loading time: {{ time }}m</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ProgressBar } from 'primevue'

import UiLoader from '@/components/ui/UiLoader.vue'

type Props = {
  time: number
}

defineProps<Props>()
</script>

<style scoped>
.wrapper {
  padding: 48px;
  display: flex;
  align-items: center;
  gap: 60px;
  max-width: 901px;
  width: 100%;
}
.loader {
  padding: 80px;
}
.title {
  margin-bottom: 1rem;
  font-size: 2rem;
}
.text {
  margin-bottom: 2rem;
  color: var(--p-text-muted-color);
}
.info {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

@media (max-width: 992px) {
  .wrapper {
    flex-direction: column;
    gap: 36px;
    max-width: 600px;
  }
  .loader {
    padding: 48px;
  }
}
</style>
