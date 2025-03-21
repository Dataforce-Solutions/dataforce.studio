<template>
  <div class="wrapper">
    <presentation-area :initial-nodes="initialNodes"/>
    <Transition>
      <sidebar v-if="activeNode" :data="activeNode.data" class="sidebar" @close="closeSidebar" />
    </Transition>
    <control-center />
    <navigation @go-back="$emit('goBack')"/>
    <toolbar />
  </div>
</template>

<script setup lang="ts">
import type { PromptNode } from '../interfaces'
import { ref } from 'vue'
import { useVueFlow, type GraphNode } from '@vue-flow/core'
import PresentationArea from '@/components/prompt-fusion/step-main/PresentationArea.vue'
import Sidebar from '@/components/prompt-fusion/step-main/sidebar/index.vue'
import Navigation from '@/components/prompt-fusion/step-main/Navigation.vue'
import Toolbar from '@/components/prompt-fusion/step-main/Toolbar.vue'
import ControlCenter from '@/components/prompt-fusion/step-main/control-center/index.vue'

type Props = {
  initialNodes: PromptNode[]
}
type Emits = {
  goBack: []
}

defineProps<Props>()
defineEmits<Emits>()

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
  z-index: 10;
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
