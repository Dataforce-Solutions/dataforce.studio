<template>
  <aside class="sidebar" :class="{ closed: !isSidebarOpened }">
    <nav class="nav">
      <ul class="list">
        <li v-for="item in sidebarMenu" :key="item.id" class="item">
          <router-link :to="{ name: item.route }" class="menu-link">
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
  width: 63px;
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
  height: 35px;
  white-space: nowrap;
  overflow: hidden;
  transition:
    color 0.3s,
    background-color 0.3s;
}

@media (any-hover: hover) {
  .menu-link:hover {
    background-color: var(--p-surface-0);
    color: #1e293b;
    box-shadow: var(--card-shadow);
  }
}

@media (any-hover: hover) {
  [data-theme='dark'] .menu-link:hover {
    background-color: var(--p-surface-900);
    color: #fff;
    box-shadow: var(--card-shadow);
  }
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
  left: 10px;
  transition: transform 0.3s;
}

.toggle-width-button.closed {
  transform: rotate(180deg);
}
</style>
