<template>
  <aside class="sidebar">
    <nav class="nav">
      <ul class="list">
        <li class="item">
          <router-link :to="{ name: 'home' }" class="menu-link">
            <rabbit :size="14" />
            <span>Express task</span>
          </router-link>
        </li>
        <li class="item">
          <router-link :to="{ name: 'sign-up' }" class="menu-link">
            <timer :size="14" />
            <span>Run time</span>
          </router-link>
        </li>
        <li class="item">
          <router-link :to="{ name: 'sign-up' }" class="menu-link">
            <frame :size="14" />
            <span>Projects</span>
          </router-link>
        </li>
      </ul>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { Rabbit, Timer, Frame } from 'lucide-vue-next'
</script>

<style scoped>
.sidebar {
  padding: 108px 16px 16px;
  background-color: var(--color-content-background);
  border-right: 1px solid var(--color-divider-border);
  width: 180px;
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
  gap: 7px;
  color: var(--p-surface-400);
  text-decoration: none;
  font-weight: 500;
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
</style>
