<template>
  <div class="wrapper">
    <presentation-area />
  </div>
</template>

<script setup lang="ts">
import PresentationArea from '@/components/prompt-fusion/PresentationArea.vue'
import { usePromptFusion } from '@/hooks/usePromptFusion'

const { getActiveNode } = usePromptFusion()
</script>

<style scoped>
@media (min-width: 768px) {
  .wrapper {
    margin: 0 -100px;
    height: calc(100vh - 93px);
  }
}
</style>
