<template>
  <div
    class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-3 text-sm"
  >
    <RefreshCw :size="15" class="shrink-0 mt-0.5 animate-spin text-amber-600 dark:text-amber-400" />
    <p class="min-w-0">
      <span class="font-medium text-amber-700 dark:text-amber-300"
        >connection dropped — reconnecting</span
      >
      <span class="text-amber-700/80 dark:text-amber-300/80">
        · will replay from cursor · no refresh needed</span
      >
    </p>
  </div>
</template>

<script setup lang="ts">
import { RefreshCw } from 'lucide-vue-next'

// A dropped socket is a latency event, never a data event: the cursor replay
// restores everything, so the banner promises exactly that and nothing more.
</script>
