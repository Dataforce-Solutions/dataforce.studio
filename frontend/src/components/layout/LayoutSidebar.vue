<template>
  <aside class="sidebar" :class="{ closed: !isSidebarOpened }">
    <nav class="nav">
      <ul class="list">
        <li v-for="item in sidebarMenu" :key="item.id" class="item">
          <div
            v-if="item.disabled && isSidebarOpened"
            v-tooltip.bottom="item.tooltipMessage"
            class="menu-link disabled"
          >
            <component :is="item.icon" :size="14" class="icon"></component>
            <span>{{ item.label }}</span>
          </div>
          <div
            v-else-if="item.disabled && !isSidebarOpened"
            v-tooltip.right="item.tooltipMessage"
            class="menu-link disabled"
          >
            <component :is="item.icon" :size="14" class="icon"></component>
            <span>{{ item.label }}</span>
          </div>
          <router-link v-else :to="{ name: item.route }" class="menu-link">
            <component :is="item.icon" :size="14" class="icon"></component>
            <span>{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
    </nav>
    <div class="sidebar-bottom">
      <nav class="nav-bottom">
        <ul class="list">
          <li v-for="item in sidebarMenuBottom" :key="item.id" class="item">
            <a v-if="item.link" :href="item.link" target="_blank" class="menu-link">
              <component :is="item.icon" :size="14" class="icon"></component>
              <span>{{ item.label }}</span>
            </a>
          </li>
        </ul>
      </nav>
      <d-button
        severity="contrast"
        variant="text"
        rounded
        class="toggle-width-button"
        :class="{ closed: !isSidebarOpened }"
        @click="toggleSidebar"
      >
        <template #icon>
          <arrow-left-to-line :size="14" color="var(--p-button-text-plain-color)" />
        </template>
      </d-button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ArrowLeftToLine } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { sidebarMenu, sidebarMenuBottom } from '@/constants/constants'

const isSidebarOpened = ref(true)

const toggleSidebar = () => {
  isSidebarOpened.value = !isSidebarOpened.value
}

function windowResizeHandler() {
  if (document.documentElement.clientWidth < 992 && isSidebarOpened.value === true)
    isSidebarOpened.value = false
}

onMounted(() => {
  windowResizeHandler()

  window.addEventListener('resize', windowResizeHandler)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', windowResizeHandler)
})
</script>

<style scoped>
.sidebar {
  padding: 96px 16px 16px;
  background-color: var(--p-content-background);
  border-right: 1px solid var(--p-divider-border-color);
  width: 180px;
  position: relative;
  transition: width 0.3s;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.sidebar.closed {
  width: 67px;
}

.sidebar-bottom {
  display: flex;
  flex-direction: column;
}

.nav-bottom {
  padding-bottom: 8px;
  border-bottom: 1px solid var(--p-divider-border-color);
  margin-bottom: 4px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.menu-link {
  padding: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--p-menu-item-color);
  text-decoration: none;
  font-weight: 500;
  height: 32px;
  white-space: nowrap;
  overflow: hidden;
  width: 100%;
  font-size: 14px;
  transition:
    color 0.3s,
    background-color 0.3s,
    width 0.3s;
}

.menu-link.disabled,
.menu-link.disabled .icon {
  color: var(--p-surface-400);
}

.menu-link.router-link-active {
  background-color: var(--p-surface-0);
  color: var(--p-menu-item-focus-color);
  box-shadow: var(--card-shadow);
}

.icon {
  color: var(--p-menu-item-icon-color);
  flex: 0 0 auto;
  transition: color 0.3s;
}

.menu-link.router-link-active .icon {
  color: var(--p-menu-item-icon-focus-color);
}

.closed .menu-link {
  width: 30px;
}

[data-theme='dark'] .router-link-active {
  background-color: var(--p-surface-900);
  color: #fff;
  box-shadow: var(--card-shadow);
}

.toggle-width-button {
  align-self: flex-end;
  transition: transform 0.3s;
}

.toggle-width-button.closed {
  transform: rotate(180deg);
}

@media (any-hover: hover) {
  .menu-link:hover {
    background-color: var(--p-menu-item-focus-background);
    color: var(--p-menu-item-focus-color);
  }

  .menu-link.router-link-active:hover {
    background-color: var(--p-surface-0);
  }

  .menu-link:hover .icon {
    color: var(--p-menu-item-icon-focus-color);
  }

  .disabled:hover {
    background-color: transparent;
    color: var(--p-surface-400);
    box-shadow: none;
    cursor: default;
  }

  .disabled:hover .icon {
    color: var(--p-surface-400);
  }

  [data-theme='dark'] .menu-link.router-link-active {
    background-color: var(--p-surface-900);
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 100% !important;
  }
  .list {
    align-items: center;
  }
  .menu-link {
    width: auto !important;
  }
  .toggle-width-button {
    display: none;
  }
}
</style>
