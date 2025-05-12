<template>
  <div class="wrapper" :style="`padding-left:${sidebarWidth}px`">
    <layout-header
      class="header"
      :is-burger-open="isBurgerOpen"
      @burger-click="() => (isBurgerOpen = !isBurgerOpen)"
    />
    <transition>
      <layout-sidebar
        v-if="isBurgerAvailable ? isBurgerOpen : true"
        class="sidebar"
        ref="sidebarRef"
        @change-width="calcSidebarWidth"
      />
    </transition>
    <layout-footer class="footer" :style="`left:${sidebarWidth}px`" />
    <main class="page">
      <MobileNotAvailablePlug v-if="showMobileNotAvailablePlug" class="mobile-not-available-plug"/>
      <slot v-else/>
    </main>
  </div>
</template>

<script setup lang="ts">
import LayoutHeader from '@/components/layout/LayoutHeader.vue'
import LayoutSidebar from '@/components/layout/LayoutSidebar.vue'
import LayoutFooter from '@/components/layout/LayoutFooter.vue'
import MobileNotAvailablePlug from '@/components/plugs/MobileNotAvailablePlug.vue'
import { computed, onBeforeMount, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()

const sidebarRef = ref<InstanceType<typeof LayoutSidebar> | null>(null)
const sidebarWidth = ref(0)
const isBurgerOpen = ref(false)
const windowWidth = ref(window.innerWidth)

const isBurgerAvailable = computed(() => windowWidth.value <= 768)
const mobileNotAvailable = computed(() => route.meta.mobileAvailable === false)
const showMobileNotAvailablePlug = computed(() => mobileNotAvailable.value && windowWidth.value <= 768)

function calcSidebarWidth() {
  if (!sidebarRef.value) return
  sidebarWidth.value = sidebarRef.value.$el.offsetWidth
}
function onWindowResize() {
  windowWidth.value = window.innerWidth
}

let resizeObserver: ResizeObserver
router.afterEach(() => {
  isBurgerOpen.value = false
})
onBeforeMount(() => {
  window.addEventListener('resize', onWindowResize)
})
onMounted(() => {
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
  window.removeEventListener('resize', onWindowResize)
})
</script>

<style scoped>
.wrapper {
  min-height: 100svh;
  padding-top: 64px;
  padding-bottom: 60px;
  overflow-x: hidden;
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

.v-enter-active,
.v-leave-active {
  transition: left 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  left: -100%;
}

.mobile-not-available-plug {
  height: calc(100vh - 150px);
}

@media (max-width: 768px) {
  .wrapper {
    padding-left: 0 !important;
  }
  .footer {
    left: 0 !important;
  }
  .page {
    padding: 0 15px;
  }
}
</style>
