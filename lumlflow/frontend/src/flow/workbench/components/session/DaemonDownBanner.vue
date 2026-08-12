<template>
  <div
    class="flex flex-col gap-2.5 rounded-lg border border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10 p-3"
  >
    <div class="flex items-start gap-2 text-sm">
      <ServerOff :size="15" class="shrink-0 mt-0.5 text-red-600 dark:text-red-400" />
      <p class="min-w-0">
        <span class="font-medium text-red-700 dark:text-red-300">daemon down</span>
        <span class="text-red-700/80 dark:text-red-300/80">
          — nothing live; showing last-known state, marked stale</span
        >
      </p>
    </div>
    <div class="max-w-md">
      <CopyField value="lumlflow ui" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ServerOff } from 'lucide-vue-next'
import CopyField from '../../ui/CopyField.vue'
</script>
