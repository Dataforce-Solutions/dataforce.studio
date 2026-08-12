<template>
  <div
    class="flex items-center gap-3 flex-wrap rounded-md border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 px-3 py-2"
  >
    <GitBranch :size="14" class="text-amber-600 dark:text-amber-400 shrink-0" />
    <span class="text-xs text-amber-800 dark:text-amber-200 flex-1 min-w-40">
      your edit landed on a moved head
    </span>
    <div class="flex items-center gap-2 shrink-0">
      <Button size="small" severity="warn" label="fork my edit" @click="emit('resolve', 'fork')">
        <template #icon><GitFork :size="13" /></template>
      </Button>
      <Button
        size="small"
        text
        severity="secondary"
        label="overwrite"
        @click="emit('resolve', 'overwrite')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { GitBranch, GitFork } from 'lucide-vue-next'

// Fork is the promoted resolution: overwriting a moved head loses someone
// else's version, forking loses nothing.
const emit = defineEmits<{ resolve: [choice: 'overwrite' | 'fork'] }>()
</script>
