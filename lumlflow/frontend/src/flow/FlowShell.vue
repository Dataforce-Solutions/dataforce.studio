<template>
  <div class="h-full flex flex-col">
    <header class="flex items-center gap-4 pb-3 border-b border-surface-200 dark:border-surface-700">
      <div>
        <p class="text-xs text-muted-color">{{ session.projectName }}</p>
        <h2 class="font-medium">{{ session.name }}</h2>
      </div>

      <nav class="flex gap-1 ml-4">
        <RouterLink
          v-for="concept in concepts"
          :key="concept.path"
          :to="concept.path"
          class="px-3 py-1 rounded text-sm border"
          :class="
            route.path === concept.path
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-muted-color hover:border-surface-300 dark:hover:border-surface-600'
          "
        >
          {{ concept.label }}
        </RouterLink>
      </nav>

      <div class="ml-auto flex items-center gap-3">
        <select
          v-model="fixtureId"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-2 py-1 text-sm"
        >
          <option v-for="entry in fixtures" :key="entry.id" :value="entry.id">
            {{ entry.label }}
          </option>
        </select>
        <div class="flex -space-x-1.5">
          <span
            v-for="agent in Object.values(session.agents)"
            :key="agent.agentId"
            class="w-6 h-6 rounded-full border-2 border-surface-0 dark:border-surface-900 flex items-center justify-center text-[10px] text-white"
            :style="{ background: agent.color }"
            :title="`${agent.label} — ${agent.activeBranchId ?? 'idle'}`"
          >
            {{ agent.label.slice(0, 2) }}
          </span>
        </div>
      </div>
    </header>

    <p class="text-xs text-muted-color py-2">{{ activeFixture?.description }}</p>

    <div class="flex-1 min-h-0 overflow-auto">
      <!-- Remount on fixture change so each concept rebuilds its playback state. -->
      <RouterView :key="fixtureId" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useWorkspace } from './composables/useWorkspace'

const route = useRoute()
const { fixtureId, fixtures, session } = useWorkspace()

const activeFixture = computed(() => fixtures.find((entry) => entry.id === fixtureId.value))

const concepts = [
  { path: '/flow/railroad', label: '1 · Canvas + railroad' },
  { path: '/flow/compare', label: '2 · Compare & compose' },
  { path: '/flow/catchup', label: '3 · Catch-up first' },
]
</script>
