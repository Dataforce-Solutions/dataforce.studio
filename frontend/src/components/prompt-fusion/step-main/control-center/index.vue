<template>
  <div class="content">
    <d-button severity="secondary">
      <span>provider</span>
      <brain :size="14" />
    </d-button>
    <d-button severity="secondary">
      <span>optimization</span>
      <sliders-horizontal :size="14" />
    </d-button>
    <div class="other-buttons">
      <d-button v-tooltip.bottom="'Run the model'" severity="secondary" variant="text">
        <template #icon>
          <play :size="14" />
        </template>
      </d-button>
      <d-button v-tooltip.left="'Download the model'" severity="secondary" variant="text">
        <template #icon>
          <cloud-download :size="14" />
        </template>
      </d-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Brain, SlidersHorizontal, Play, CloudDownload } from 'lucide-vue-next'
</script>

<style scoped>
.content {
  position: absolute;
  top: 16px;
  right: 18px;
  z-index: 2;
  display: flex;
  gap: 8px;
}
.other-buttons {
  padding: 0 2px;
  display: flex;
  gap: 4px;
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}
</style>
