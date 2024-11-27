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
    <d-button
      severity="help"
      rounded
      class="toggle-width-button"
      :class="{ closed: !isSidebarOpened }"
      @click="toggleSidebar"
    >
      <template #icon>
        <arrow-left-to-line :size="14" />
      </template>
    </d-button>
  </aside>
</template>

<script setup lang="ts">
import { ArrowLeftToLine } from 'lucide-vue-next'
import { ref } from 'vue'

import { sidebarMenu } from './data'

const isSidebarOpened = ref(true)

const toggleSidebar = () => {
  isSidebarOpened.value = !isSidebarOpened.value
}
</script>

<style scoped>
.sidebar {
  padding: 108px 16px 70px;
  background-color: var(--color-content-background);
  border-right: 1px solid var(--color-divider-border);
  width: 180px;
  position: relative;
  transition: width 0.3s;
}

.sidebar.closed {
  width: 67px;
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
  color: var(--p-surface-400);
  text-decoration: none;
  font-weight: 500;
  height: 30px;
  white-space: nowrap;
  overflow: hidden;
  width: 100%;
  transition:
    color 0.3s,
    background-color 0.3s,
    width 0.3s;
}

.closed .menu-link {
  width: 30px;
}

.router-link-active {
  background-color: var(--p-surface-0);
  color: #1e293b;
  box-shadow: var(--card-shadow);
}

[data-theme='dark'] .router-link-active {
  background-color: var(--p-surface-900);
  color: #fff;
  box-shadow: var(--card-shadow);
}

.icon {
  flex: 0 0 auto;
}

.toggle-width-button {
  box-shadow: var(--card-shadow);
  position: absolute;
  bottom: 16px;
  left: 16px;
  transition: transform 0.3s;
}

.toggle-width-button.closed {
  transform: rotate(180deg);
}

@media (any-hover: hover) {
  .menu-link:hover {
    background-color: var(--p-surface-0);
    color: #1e293b;
    box-shadow: var(--card-shadow);
  }

  .disabled:hover {
    background-color: transparent;
    color: var(--p-surface-400);
    box-shadow: none;
    cursor: default;
  }

  [data-theme='dark'] .menu-link:hover {
    background-color: var(--p-surface-900);
    color: #fff;
    box-shadow: var(--card-shadow);
  }

  [data-theme='dark'] .disabled:hover {
    background-color: transparent;
    color: var(--p-surface-400);
    box-shadow: none;
    cursor: default;
  }
}
</style>
