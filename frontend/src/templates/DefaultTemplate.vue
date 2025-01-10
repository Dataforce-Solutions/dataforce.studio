<template>
  <div class="wrapper" :style="`padding-left:${sidebarWidth}px`">
    <layout-header class="header" />
    <layout-sidebar class="sidebar" ref="sidebarRef" @change-width="calcSidebarWidth" />
    <layout-footer class="footer" :style="`left:${sidebarWidth}px`" />
    <main class="page">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import LayoutHeader from '@/components/layout/LayoutHeader.vue'
import LayoutSidebar from '@/components/layout/LayoutSidebar.vue'
import LayoutFooter from '@/components/layout/LayoutFooter.vue'

import { onBeforeUnmount, onMounted, ref } from 'vue'

const sidebarRef = ref<InstanceType<typeof LayoutSidebar> | null>(null)
const sidebarWidth = ref(0)

function calcSidebarWidth() {
  if (!sidebarRef.value) return

  sidebarWidth.value = sidebarRef.value.$el.offsetWidth
}

let resizeObserver: ResizeObserver

onMounted(() => {
  calcSidebarWidth()

  resizeObserver = new ResizeObserver(() => {
    calcSidebarWidth()
  })

  if (sidebarRef.value) {
    resizeObserver.observe(sidebarRef.value.$el)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver && sidebarRef.value) {
    resizeObserver.unobserve(sidebarRef.value.$el)
  }
})
</script>

<style scoped>
.wrapper {
  min-height: 100svh;
  padding-top: 100px;
  padding-bottom: 100px;
}
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 90;
}
.page {
  padding: 0 100px;
}
.footer {
  position: fixed;
  bottom: 0;
  right: 0;
  z-index: 80;
}
</style>
