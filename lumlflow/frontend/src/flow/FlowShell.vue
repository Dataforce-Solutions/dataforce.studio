<template>
  <div class="h-full flex flex-col">
    <header class="flex items-center gap-4 pb-3 border-b border-surface-200 dark:border-surface-700">
      <div>
        <p class="text-xs text-muted-color">lumlflow</p>
        <h2 class="font-medium">Flow workbench — UI draft</h2>
      </div>

      <nav class="flex gap-1 ml-4">
        <RouterLink
          v-for="entry in nav"
          :key="entry.path"
          :to="entry.path"
          class="px-3 py-1 rounded text-sm border"
          :class="
            route.path.startsWith(entry.path)
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-muted-color hover:border-surface-300 dark:hover:border-surface-600'
          "
        >
          {{ entry.label }}
        </RouterLink>
      </nav>

      <div v-if="onRailroad" class="ml-auto flex items-center gap-3">
        <select
          v-model="fixtureId"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-2 py-1 text-sm"
        >
          <option v-for="entry in fixtures" :key="entry.id" :value="entry.id">
            {{ entry.label }}
          </option>
        </select>
      </div>
    </header>

    <div class="flex-1 min-h-0 overflow-auto pt-3">
      <RouterView :key="onRailroad ? fixtureId : route.fullPath" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useWorkspace } from './composables/useWorkspace'

const route = useRoute()
const { fixtureId, fixtures } = useWorkspace()

const onRailroad = computed(() => route.path.startsWith('/flow/railroad'))

const nav = [
  { path: '/flow/design', label: 'Design system' },
  { path: '/flow/flows', label: 'Flows' },
  { path: '/flow/work', label: 'Workbench' },
  { path: '/flow/compare', label: 'Compare' },
  { path: '/flow/railroad', label: 'Reference · railroad' },
]
</script>
