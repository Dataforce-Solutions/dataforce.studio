<template>
  <div
    data-scratch-console
    class="border border-dashed border-surface-400 dark:border-surface-600 rounded p-3"
  >
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
        <pre
          v-if="entry.stdout"
          class="font-mono text-xs text-muted-color whitespace-pre-wrap"
          >{{ entry.stdout }}</pre
        >
        <PreviewPrimitives
          v-if="entry.preview"
          data-scratch-result
          :preview="entry.preview"
        />
        <pre v-else class="font-mono text-xs text-muted-color whitespace-pre-wrap">{{
          entry.output
        }}</pre>
      </div>
    </div>

    <p v-if="error" role="alert" data-scratch-error class="mb-2 text-xs text-red-600">
      {{ error }}
    </p>

    <div class="flex gap-2">
      <input
        v-model="draft"
        data-scratch-input
        placeholder="df.tenure.describe()"
        class="flex-1 bg-transparent border border-surface-300 dark:border-surface-600 rounded px-2 py-1 text-xs font-mono"
        :disabled="pending"
        @keyup.enter="run"
      />
      <button
        data-run-scratch
        class="px-2 py-1 rounded border border-surface-300 dark:border-surface-600 text-xs"
        :disabled="pending || !draft.trim()"
        @click="run"
      >
        {{ pending ? 'running…' : 'run' }}
      </button>
      <button
        v-if="!client"
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
import type { FlowSessionClient } from '../api/client'
import type { JsonValue, PreviewPayload } from '../api/types'
import PreviewPrimitives from './PreviewPrimitives.vue'

/**
 * The home for throwaway work.
 *
 * Without this, every `df.head()` costs a class definition and leaves a
 * permanent node in an append-only graph — which is why nobody explores in an
 * asset framework. Scratch runs against the *cached materialization*, so it
 * works unchanged while time-travelling and never touches the kernel's state.
 * Promotion is the explicit gesture that turns a peek into an asset.
 */
const props = defineProps<{
  assetName: string
  client?: FlowSessionClient
  branch?: string
}>()
const emit = defineEmits<{ promote: [expression: string] }>()

const draft = ref('')
interface ScratchHistoryEntry {
  input: string
  output?: string
  stdout?: string
  preview?: PreviewPayload
}

const history = ref<ScratchHistoryEntry[]>(
  props.client
    ? []
    : [
        {
          input: 'df.tenure.describe()',
          output:
            'count    7032.000\nmean       32.421\nstd        24.545\nmin         1.000\n50%        29.000\nmax        72.000',
        },
      ],
)
const pending = ref(false)
const error = ref('')

const canned: Record<string, string> = {
  'df.head()': 'customer_id  tenure  contract        monthly_charges  churn\nC07000        0      Month-to-month  19.50            1',
  'df.churn.mean()': '0.2654',
  'df.shape': '(7032, 21)',
}

const run = async (): Promise<void> => {
  const input = draft.value.trim()
  if (!input || pending.value) return
  error.value = ''
  if (!props.client) {
    history.value.push({
      input,
      output: canned[input] ?? '<Frame 7032 x 21>',
    })
    draft.value = ''
    return
  }

  pending.value = true
  try {
    const result = await props.client.rpc('eval', {
      code: input,
      ...(props.branch ? { branch: props.branch } : {}),
    })
    history.value.push(normalizeEvalResult(input, result))
    draft.value = ''
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    pending.value = false
  }
}

const normalizeEvalResult = (input: string, value: JsonValue): ScratchHistoryEntry => {
  if (!isJsonObject(value) || typeof value.result !== 'string') {
    throw new Error('The daemon returned an invalid evaluation result.')
  }
  const resultType = typeof value.result_type === 'string' ? value.result_type : 'value'
  const preview = parsePreview(value.preview)
  return {
    input,
    stdout: typeof value.stdout === 'string' ? value.stdout : '',
    preview: preview
      ? preview
      : {
          schema: 1,
          kind: resultType,
          blocks: [{ type: 'markdown', text: value.result }],
        },
  }
}

const parsePreview = (value: JsonValue | undefined): PreviewPayload | null => {
  if (
    !isJsonObject(value) ||
    typeof value.schema !== 'number' ||
    typeof value.kind !== 'string' ||
    !Array.isArray(value.blocks) ||
    !value.blocks.every(isJsonObject)
  ) {
    return null
  }
  return {
    schema: value.schema,
    kind: value.kind,
    blocks: value.blocks,
    ...(typeof value.truncated === 'boolean' ? { truncated: value.truncated } : {}),
  }
}

const isJsonObject = (value: JsonValue | undefined): value is Record<string, JsonValue> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
</script>
