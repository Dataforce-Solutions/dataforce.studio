<template>
  <div class="wrapper">
    <presentation-area />
    <Transition>
      <sidebar v-if="activeNode" :data="activeNode.data" class="sidebar" @close="closeSidebar" />
    </Transition>
  </div>
</template>

<script setup lang="ts">
import PresentationArea from '@/components/prompt-fusion/PresentationArea.vue'
import Sidebar from '@/components/prompt-fusion/sidebar/index.vue'
import { useVueFlow, type GraphNode } from '@vue-flow/core'
import { ref } from 'vue'

const { onNodeClick, onPaneClick } = useVueFlow()

const activeNode = ref<GraphNode | null>(null)

function closeSidebar() {
  activeNode.value = null
}

onNodeClick(({ node }) => {
  activeNode.value = node
})
onPaneClick(() => {
  activeNode.value = null
})
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
