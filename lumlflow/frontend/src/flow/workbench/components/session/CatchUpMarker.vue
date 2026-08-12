<template>
  <div class="inline-flex flex-col gap-1">
    <div
      class="inline-flex items-center gap-2 rounded-full border border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-500/30 dark:bg-primary-500/10 dark:text-primary-300 px-3 py-1.5 text-sm"
    >
      <History :size="14" class="shrink-0" />
      <span>{{ formatCount(count, 'change') }} since you were here</span>
      <button
        class="underline underline-offset-2 decoration-primary-300 dark:decoration-primary-500/50 hover:decoration-current"
        @click="emit('open')"
      >
        open at cursor
      </button>
    </div>
    <p class="text-xs text-muted-color px-1">
      a marker, not an inbox — reopening still lands on the active branch
    </p>
  </div>
</template>

<script setup lang="ts">
import { History } from 'lucide-vue-next'
import { formatCount } from '../../model/format'

defineProps<{ count: number }>()

const emit = defineEmits<{ open: [] }>()
</script>
