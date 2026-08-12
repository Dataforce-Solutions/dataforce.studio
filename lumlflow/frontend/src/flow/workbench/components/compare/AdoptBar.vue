<template>
  <div
    class="flex flex-wrap items-start gap-x-10 gap-y-4 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
  >
    <div class="flex flex-col gap-1.5">
      <Button size="small" @click="emit('adopt')">
        <GitMerge :size="14" />
        <span>
          Adopt <span class="font-mono">{{ asset }}</span> from
          <span class="font-mono">{{ winner }}</span> onto
          <span class="font-mono">{{ target }}</span>
        </span>
      </Button>
      <p class="text-xs text-muted-color">
        Per-asset cherry-pick with three-way conflict detection — conflicts resolve by pick-a-side.
      </p>
    </div>

    <div class="flex flex-col gap-1.5">
      <Button size="small" severity="secondary" outlined @click="emit('export')">
        <FileDown :size="14" />
        <span>Export the chosen slice</span>
      </Button>
      <p class="text-xs text-muted-color">
        export flow file — a file export, not a platform upload
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { FileDown, GitMerge } from 'lucide-vue-next'

defineProps<{
  winner: string
  asset: string
  target: string
}>()

const emit = defineEmits<{
  adopt: []
  export: []
}>()
</script>
