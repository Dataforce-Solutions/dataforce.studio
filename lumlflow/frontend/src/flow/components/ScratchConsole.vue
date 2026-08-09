<template>
  <div class="border border-dashed border-surface-400 dark:border-surface-600 rounded p-3">
    <div class="flex items-center justify-between mb-2">
      <p class="text-sm">
        Scratch — scoped to
        <span class="font-mono text-xs">{{ assetName }}</span>
      </p>
      <span class="text-xs text-muted-color">ephemeral · not part of the graph</span>
    </div>

    <div class="space-y-2 mb-2">
      <div v-for="(entry, index) in history" :key="index">
        <p class="font-mono text-xs">&gt;&gt;&gt; {{ entry.input }}</p>
        <pre class="font-mono text-xs text-muted-color whitespace-pre-wrap">{{ entry.output }}</pre>
      </div>
    </div>

    <div class="flex gap-2">
      <input
        v-model="draft"
        placeholder="df.tenure.describe()"
        class="flex-1 bg-transparent border border-surface-300 dark:border-surface-600 rounded px-2 py-1 text-xs font-mono"
        @keyup.enter="run"
      />
      <button
        class="px-2 py-1 rounded border border-surface-300 dark:border-surface-600 text-xs"
        @click="run"
      >
        run
      </button>
      <button
        class="px-2 py-1 rounded border border-primary-500 text-primary-600 dark:text-primary-400 text-xs"
        :disabled="!history.length"
        @click="emit('promote', history[history.length - 1].input)"
      >
        promote to asset
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

/**
 * The home for throwaway work.
 *
 * Without this, every `df.head()` costs a class definition and leaves a
 * permanent node in an append-only graph — which is why nobody explores in an
 * asset framework. Scratch runs against the *cached materialization*, so it
 * works unchanged while time-travelling and never touches the kernel's state.
 * Promotion is the explicit gesture that turns a peek into an asset.
 */
defineProps<{ assetName: string }>()
const emit = defineEmits<{ promote: [expression: string] }>()

const draft = ref('')
const history = ref<{ input: string; output: string }[]>([
  {
    input: 'df.tenure.describe()',
    output:
      'count    7032.000\nmean       32.421\nstd        24.545\nmin         1.000\n50%        29.000\nmax        72.000',
  },
])

const canned: Record<string, string> = {
  'df.head()': 'customer_id  tenure  contract        monthly_charges  churn\nC07000        0      Month-to-month  19.50            1',
  'df.churn.mean()': '0.2654',
  'df.shape': '(7032, 21)',
}

const run = (): void => {
  const input = draft.value.trim()
  if (!input) return
  history.value.push({
    input,
    output: canned[input] ?? '<Frame 7032 x 21>',
  })
  draft.value = ''
}
</script>
