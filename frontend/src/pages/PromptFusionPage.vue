<template>
  <div class="wrapper">
    <presentation-area />
    <Transition>
      <sidebar v-if="activeNode" :data="activeNode.data" class="sidebar" @close="removeSelectedNodes([activeNode])"/>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import PresentationArea from '@/components/prompt-fusion/PresentationArea.vue'
import Sidebar from '@/components/prompt-fusion/sidebar/index.vue'
import { useVueFlow } from '@vue-flow/core';
import { computed } from 'vue';

const { getSelectedNodes, removeSelectedNodes } = useVueFlow()

const activeNode = computed(() => getSelectedNodes.value[getSelectedNodes.value.length - 1])
</script>

<style scoped>
.wrapper {
  position: relative;
}
@media (min-width: 768px) {
  .wrapper {
    margin: 0 -100px;
    height: calc(100vh - 124px);
  }
}

.sidebar {
  position: absolute;
  width: 100%;
  top: 20px;
  bottom: 0;
  right: 10px;
  z-index: 2;
}

.v-enter-active,
.v-leave-active {
  transition: transform 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  transform: translateX(100%);
}
</style>
