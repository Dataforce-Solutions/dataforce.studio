<template>
  <aside
    class="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10 px-4 py-3"
  >
    <span
      class="w-7 h-7 rounded-full bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300 flex items-center justify-center shrink-0 mt-0.5"
    >
      <ZapOff :size="15" />
    </span>
    <div class="flex flex-col gap-0.5 flex-1 min-w-0">
      <p class="text-sm font-medium">the kernel died — {{ cause ?? 'out of memory' }}</p>
      <p class="text-xs text-muted-color" v-html="detailHtml" />
      <p class="text-xs text-muted-color">
        nothing recorded is lost — the store and journal are intact; the run queue is drained, not
        retried
      </p>
    </div>
    <Button size="small" outlined label="restart kernel" @click="emit('restart-kernel')">
      <template #icon><RefreshCw :size="13" /></template>
    </Button>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button } from 'primevue'
import { RefreshCw, ZapOff } from 'lucide-vue-next'
import { inlineCodeHtml } from './inlineCode'

/**
 * Kernel death is observable (exit status / OOM kill) and recoverable: the
 * kernel is stateless relative to the store, so the banner can honestly say
 * nothing recorded is lost.
 */
const props = defineProps<{
  /** The cell that was materializing when the kernel died. */
  slug: string
  cause?: string
}>()

const emit = defineEmits<{ 'restart-kernel': [] }>()

const detailHtml = computed(() =>
  inlineCodeHtml(`\`${props.slug}\` was materializing when it died`),
)
</script>
