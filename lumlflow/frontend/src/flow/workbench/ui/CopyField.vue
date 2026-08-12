<template>
  <div
    class="flex items-center gap-2 rounded border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 px-3 py-2"
  >
    <code class="font-mono text-[13px] flex-1 truncate select-all">{{ value }}</code>
    <Button
      v-tooltip.top="copied ? 'Copied' : 'Copy'"
      text
      rounded
      severity="secondary"
      size="small"
      :aria-label="`Copy ${value}`"
      @click="copy"
    >
      <template #icon>
        <Check v-if="copied" :size="14" class="text-emerald-500" />
        <Copy v-else :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from 'primevue'
import { Check, Copy } from 'lucide-vue-next'

const props = defineProps<{ value: string }>()

const copied = ref(false)

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    // Clipboard unavailable (insecure context) — selection via select-all still works.
  }
}
</script>
