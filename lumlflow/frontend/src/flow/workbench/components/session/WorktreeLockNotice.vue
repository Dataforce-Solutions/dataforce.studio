<template>
  <div
    class="flex items-start gap-2 rounded border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 px-2.5 py-2 text-xs"
  >
    <Lock :size="13" class="shrink-0 mt-0.5 text-muted-color" />
    <p class="min-w-0 text-muted-color">
      worktree locked by <code class="font-mono text-[11px]">{{ holder }}</code> — checkout, rewind
      and adopt wait; your edits land in the store and project later
      <button
        v-tooltip.top="'Take the worktree anyway — the agent loses its file view'"
        class="underline underline-offset-2 hover:text-surface-700 dark:hover:text-surface-200"
        @click="emit('force')"
      >
        force
      </button>
    </p>
  </div>
</template>

<script setup lang="ts">
import { Lock } from 'lucide-vue-next'

withDefaults(defineProps<{ holder?: string }>(), { holder: 'claude-1' })

const emit = defineEmits<{ force: [] }>()
</script>
