<template>
  <article
    data-live-canvas-card
    :data-cell-slug="cell.slug"
    class="rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm"
  >
    <div class="flex items-center gap-2 mb-3">
      <h3 class="font-medium">{{ cell.slug }}</h3>
      <span class="text-xs rounded px-2 py-0.5 bg-surface-100 dark:bg-surface-800">
        {{ cell.verdict.transitive.state }}
      </span>
      <span v-if="cell.verdict.transitive.causes.length" class="text-xs text-muted-color">
        {{ plainCauses }}
      </span>
      <span v-if="cell.run_id" data-running-badge class="text-xs text-primary-600">Running</span>
      <span
        v-if="cell.computed_under_older_env"
        data-older-env-badge
        class="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200"
      >
        computed under older environment
      </span>
      <div class="ml-auto flex gap-1">
        <button
          type="button"
          data-run-cell
          class="rounded border border-surface-300 dark:border-surface-600 px-2 py-1 text-xs"
          :disabled="requestPending || cell.run_id !== null"
          @click="run(false)"
        >
          Run
        </button>
        <button
          type="button"
          data-force-run-cell
          class="rounded border border-surface-300 dark:border-surface-600 px-2 py-1 text-xs"
          :disabled="requestPending || cell.run_id !== null"
          @click="run(true)"
        >
          Force run
        </button>
        <button
          v-if="cell.run_id"
          type="button"
          data-cancel-cell
          class="rounded border border-red-300 px-2 py-1 text-xs text-red-600"
          :disabled="cancelPending"
          @click="cancelRun"
        >
          {{ cancelPending ? 'Cancelling…' : 'Cancel' }}
        </button>
      </div>
    </div>

    <p v-if="requestError" data-run-error role="alert" class="mb-3 text-xs text-red-600">
      {{ requestError }}
    </p>
    <div
      v-if="runStatus === 'memo-hit'"
      data-cache-skip
      class="mb-3 rounded border border-emerald-400 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
    >
      Reused this materialization from cache — no kernel execution.
    </div>
    <button
      v-if="failed"
      type="button"
      data-run-failure
      class="mb-3 block w-full rounded border border-red-400 bg-red-50 px-3 py-1.5 text-left text-sm text-red-800 dark:bg-red-950/30 dark:text-red-300"
      @click="selected = 'logs'"
    >
      Run failed — {{ plainCauses || 'open logs for the traceback' }}
    </button>
    <p
      v-else-if="runStatus === 'cancelled'"
      data-run-cancelled
      class="mb-3 text-sm text-muted-color"
    >
      Run cancelled.
    </p>

    <form
      v-if="parameterEntries.length"
      data-param-inspector
      class="grid grid-cols-[auto_1fr] gap-2 items-center mb-3 text-sm"
      @submit.prevent="saveParams"
    >
      <template v-for="entry in parameterEntries" :key="entry.name">
        <label :for="`${cell.uid}-${entry.name}`">{{ entry.name }}</label>
        <input
          :id="`${cell.uid}-${entry.name}`"
          v-model="paramDraft[entry.name]"
          class="rounded border border-surface-300 dark:border-surface-600 bg-transparent px-2 py-1 font-mono"
        />
      </template>
      <span />
      <div>
        <button
          type="submit"
          class="rounded border border-surface-300 dark:border-surface-600 px-2 py-1"
          :disabled="paramsSaving"
        >
          {{ paramsSaving ? 'Saving…' : 'Save parameters' }}
        </button>
        <button
          type="button"
          data-open-sweep
          class="ml-2 rounded border border-surface-300 px-2 py-1 dark:border-surface-600"
          @click="sweepOpen = !sweepOpen"
        >
          Sweep…
        </button>
        <span v-if="paramsError" class="ml-2 text-xs text-red-600">{{ paramsError }}</span>
      </div>
    </form>

    <form
      v-if="sweepOpen"
      data-sweep-form
      class="mb-3 rounded border border-surface-200 p-3 text-sm dark:border-surface-700"
      @submit.prevent="launchSweep"
    >
      <div class="grid grid-cols-[auto_1fr] items-center gap-2">
        <label :for="`${cell.uid}-sweep-param`">Parameter</label>
        <select
          :id="`${cell.uid}-sweep-param`"
          v-model="sweepParam"
          data-sweep-param
          class="rounded border border-surface-300 bg-transparent px-2 py-1 dark:border-surface-600"
        >
          <option v-for="entry in parameterEntries" :key="entry.name" :value="entry.name">
            {{ entry.name }}
          </option>
        </select>
        <label :for="`${cell.uid}-sweep-values`">Values</label>
        <input
          :id="`${cell.uid}-sweep-values`"
          v-model="sweepValues"
          data-sweep-values
          class="rounded border border-surface-300 bg-transparent px-2 py-1 font-mono dark:border-surface-600"
          placeholder="[0.01, 0.05, 0.1]"
        />
      </div>
      <p class="mt-1 text-xs text-muted-color">Enter a non-empty JSON array.</p>
      <div class="mt-2 flex items-center gap-2">
        <button
          type="submit"
          class="rounded border border-surface-300 px-2 py-1 dark:border-surface-600"
          :disabled="sweepPending"
        >
          {{ sweepPending ? 'Running sweep…' : 'Launch sweep' }}
        </button>
        <button type="button" class="text-xs text-muted-color" @click="sweepOpen = false">
          Cancel
        </button>
      </div>
      <p v-if="sweepError" role="alert" data-sweep-error class="mt-2 text-xs text-red-600">
        {{ sweepError }}
      </p>
      <p
        v-else-if="sweepStatus"
        role="status"
        data-sweep-status
        class="mt-2 text-xs text-emerald-600"
      >
        {{ sweepStatus }}
      </p>
    </form>

    <div role="tablist" class="flex gap-1 border-b border-surface-200 dark:border-surface-700 mb-3">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        role="tab"
        type="button"
        class="px-3 py-1.5 text-sm border-b-2"
        :class="selected === tab.id ? 'border-primary-500' : 'border-transparent text-muted-color'"
        :aria-selected="selected === tab.id"
        @click="selected = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <template v-if="selectedOutput">
      <PreviewPrimitives :preview="selectedOutput.preview" :page="page" />
      <div v-if="selectedOutput.content_hash" class="mt-3 flex items-center gap-2">
        <button
          type="button"
          data-promote-output
          class="rounded border border-surface-300 px-2 py-1 text-xs dark:border-surface-600"
          :disabled="promotionDisabled"
          @click="promoteOutput"
        >
          {{ promoteLabel }}
        </button>
        <span
          v-if="selectedUploadState"
          data-upload-state
          :data-state="selectedUploadState.state"
          class="text-xs text-muted-color"
        >
          Publication {{ selectedUploadState.state }}
          <template v-if="selectedUploadState.attempts">
            · attempt {{ selectedUploadState.attempts }}
          </template>
        </span>
        <span
          v-else-if="promotionAwaiting === selectedOutput.name"
          data-promote-awaiting
          class="text-xs text-muted-color"
        >
          Waiting for journal acceptance…
        </span>
      </div>
      <p
        v-if="selectedUploadState?.error"
        data-upload-error
        role="alert"
        class="mt-2 text-xs text-red-600"
      >
        {{ selectedUploadState.error }}
      </p>
      <p
        v-else-if="promotionError"
        data-promote-error
        role="alert"
        class="mt-2 text-xs text-red-600"
      >
        {{ promotionError }}
      </p>
      <button
        v-if="selectedOutput.kind === 'frame' && selectedOutput.content_hash"
        data-expand-page
        type="button"
        class="mt-3 px-2 py-1 text-xs rounded border border-surface-300 dark:border-surface-600"
        :disabled="pageLoading"
        @click="expandPage"
      >
        {{ pageLoading ? 'Loading…' : 'Expand rows' }}
      </button>
      <p v-if="pageError" class="mt-2 text-xs text-red-600">{{ pageError }}</p>
    </template>
    <form
      v-else-if="selected === 'code'"
      data-code-editor-form
      class="space-y-2"
      @submit.prevent="saveCode"
    >
      <textarea
        v-model="codeDraft"
        data-code-editor
        :aria-label="`Code for ${cell.slug}`"
        class="block min-h-64 w-full resize-y rounded border border-surface-300 bg-transparent p-3 font-mono text-xs dark:border-surface-600"
        spellcheck="false"
      />
      <div
        v-if="editConflict"
        data-edit-conflict
        role="alert"
        class="rounded border border-amber-400 p-3 text-sm"
      >
        <p>{{ editConflict.message }}</p>
        <button
          type="button"
          data-reload-code
          class="mt-2 rounded border border-amber-500 px-2 py-1 text-xs"
          @click="reloadConflictingCode"
        >
          Reload latest code
        </button>
      </div>
      <p v-else-if="codeError" role="alert" class="text-xs text-red-600">{{ codeError }}</p>
      <p
        v-if="codeAwaitingAcceptance"
        data-edit-pending-acceptance
        class="text-xs text-muted-color"
      >
        Saved. Waiting for journal acceptance before updating the card.
      </p>
      <div class="flex items-center gap-2">
        <button
          type="submit"
          data-save-code
          class="rounded border border-surface-300 px-2 py-1 text-sm dark:border-surface-600"
          :disabled="!codeDirty || codeSaving || codeAwaitingAcceptance"
        >
          {{ codeSaving ? 'Saving…' : 'Save code' }}
        </button>
        <button
          v-if="codeDirty && !codeAwaitingAcceptance"
          type="button"
          class="text-xs text-muted-color"
          @click="resetCode"
        >
          Reset
        </button>
      </div>
    </form>
    <pre v-else-if="selected === 'logs'" class="text-xs whitespace-pre-wrap font-mono">{{
      persistentLogs
    }}</pre>
    <pre v-else-if="selected === 'console'" class="text-xs whitespace-pre-wrap font-mono">{{
      consoleText
    }}</pre>
  </article>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { FlowRpcError, type FlowSessionClient, type StreamSubscription } from '../api/client'
import type { AssetPage, JsonValue, LiveCell, UploadQueueState } from '../api/types'
import PreviewPrimitives from './PreviewPrimitives.vue'

const props = defineProps<{
  cell: LiveCell
  client: FlowSessionClient
  branch?: string
  runStatus?: 'memo-hit' | 'failed' | 'cancelled' | null
  uploadStates?: Record<string, UploadQueueState>
}>()
const selected = ref(props.cell.outputs[0]?.name ?? 'code')
const consoleChunks = ref<string[]>([])
const hasConsole = ref(props.cell.run_id !== null)
const page = ref<AssetPage | null>(null)
const pageError = ref('')
const pageLoading = ref(false)
const paramsSaving = ref(false)
const paramsError = ref('')
const sweepOpen = ref(false)
const sweepParam = ref('')
const sweepValues = ref('')
const sweepPending = ref(false)
const sweepError = ref('')
const sweepStatus = ref('')
const requestPending = ref(false)
const cancelPending = ref(false)
const requestError = ref('')
const promotionPending = ref(false)
const promotionAwaiting = ref<string | null>(null)
const promotionError = ref('')
const paramDraft = ref<Record<string, string>>({})
const codeDraft = ref(props.cell.source)
const acceptedCode = ref(props.cell.source)
const editBaseDefinitionHash = ref(props.cell.definition_hash)
const codeSaving = ref(false)
const codeError = ref('')
const codeAwaitingAcceptance = ref(false)
const editConflict = ref<{
  message: string
  currentSource: string
  currentDefinitionHash: string
} | null>(null)
let logSubscription: StreamSubscription | null = null

const tabs = computed(() => [
  ...props.cell.outputs.map((output) => ({ id: output.name, label: output.name })),
  { id: 'code', label: 'code' },
  { id: 'logs', label: 'logs' },
  ...(props.cell.run_id || hasConsole.value ? [{ id: 'console', label: 'console' }] : []),
])
const selectedOutput = computed(() =>
  props.cell.outputs.find((output) => output.name === selected.value),
)
const selectedUploadState = computed(() =>
  selectedOutput.value ? (props.uploadStates?.[selectedOutput.value.name] ?? null) : null,
)
const promotionDisabled = computed(
  () =>
    promotionPending.value ||
    promotionAwaiting.value === selectedOutput.value?.name ||
    selectedUploadState.value?.state === 'queued' ||
    selectedUploadState.value?.state === 'uploading' ||
    selectedUploadState.value?.state === 'done',
)
const promoteLabel = computed(() => {
  if (promotionPending.value) return 'Queuing…'
  if (selectedUploadState.value?.state === 'done') return 'Published'
  if (selectedUploadState.value?.state === 'failed') return 'Retry publication'
  return 'Promote output'
})
const codeDirty = computed(() => codeDraft.value !== acceptedCode.value)
const persistentLogs = computed(() => props.cell.logs.map((event) => event.bytes).join(''))
const consoleText = computed(() => consoleChunks.value.join(''))
const failed = computed(
  () => props.runStatus === 'failed' || props.cell.verdict.transitive.state === 'failed',
)
const causeLabels: Record<string, string> = {
  'definition-changed': 'code or parameters changed',
  'env-mismatch': 'environment changed',
  'materialization-failed': 'latest materialization failed',
  'never-run': 'not run yet',
  'upstream-stale': 'an upstream cell changed',
}
const plainCauses = computed(() =>
  props.cell.verdict.transitive.causes
    .map((cause) => causeLabels[cause] ?? cause.replace(/[-_]/g, ' '))
    .join(', '),
)
const parameterEntries = computed(() => {
  const params = props.cell.manifest.params
  if (!params || typeof params !== 'object' || Array.isArray(params)) return []
  return Object.entries(params).map(([name, value]) => ({ name, value }))
})

watch(
  parameterEntries,
  (entries) => {
    paramDraft.value = Object.fromEntries(
      entries.map(({ name, value }) => [name, JSON.stringify(value)]),
    )
    if (!entries.some(({ name }) => name === sweepParam.value)) {
      sweepParam.value = entries[0]?.name ?? ''
    }
  },
  { immediate: true },
)

interface SweepLaunchResult {
  group: string
  variants: { branch: string; branch_id: string }[]
}

const launchSweep = async (): Promise<void> => {
  if (!sweepParam.value || sweepPending.value) return
  sweepPending.value = true
  sweepError.value = ''
  sweepStatus.value = ''
  try {
    const values: unknown = JSON.parse(sweepValues.value)
    if (!Array.isArray(values) || values.length === 0) {
      throw new Error('Sweep values must be a non-empty JSON array.')
    }
    const overrides: Record<string, JsonValue>[] = values.map((value) => ({
      [sweepParam.value]: value as JsonValue,
    }))
    const result = (await props.client.rpc('sweep', {
      slug: props.cell.slug,
      overrides,
      ...(props.branch ? { parent: props.branch } : {}),
      actor: 'user:ui',
      intent: `sweep ${props.cell.slug}.${sweepParam.value}`,
    })) as unknown as SweepLaunchResult
    for (const [index, variant] of result.variants.entries()) {
      sweepStatus.value = `Running variant ${index + 1} of ${result.variants.length}…`
      await props.client.rpc('run', {
        target: props.cell.slug,
        branch: variant.branch_id,
        force: false,
        actor: 'user:ui',
        intent: `run ${props.cell.slug} sweep ${result.group} variant ${index + 1}`,
      })
    }
    sweepStatus.value = `Sweep ${result.group} completed.`
  } catch (error) {
    sweepError.value =
      error instanceof SyntaxError
        ? 'Sweep values must be a non-empty JSON array.'
        : error instanceof Error
          ? error.message
          : String(error)
  } finally {
    sweepPending.value = false
  }
}

const saveParams = async (): Promise<void> => {
  paramsSaving.value = true
  paramsError.value = ''
  try {
    const params = Object.fromEntries(
      Object.entries(paramDraft.value).map(([name, value]) => [name, JSON.parse(value)]),
    )
    await props.client.editParams(props.cell.slug, params, props.cell.definition_hash)
  } catch (error) {
    paramsError.value = error instanceof Error ? error.message : String(error)
  } finally {
    paramsSaving.value = false
  }
}

const conflictValue = (error: FlowRpcError, name: string): string | null => {
  const data = error.data
  if (typeof data !== 'object' || data === null || Array.isArray(data)) return null
  const value = data[name]
  return typeof value === 'string' ? value : null
}

const saveCode = async (): Promise<void> => {
  if (!codeDirty.value || codeAwaitingAcceptance.value) return
  codeSaving.value = true
  codeError.value = ''
  editConflict.value = null
  try {
    await props.client.rpc('cells_edit', {
      slug: props.cell.slug,
      source: codeDraft.value,
      base_definition_hash: editBaseDefinitionHash.value,
      actor: 'user:ui',
      intent: `edit ${props.cell.slug}`,
    })
    codeAwaitingAcceptance.value = true
  } catch (error) {
    if (error instanceof FlowRpcError && error.code === -32009) {
      const currentSource = conflictValue(error, 'current_source')
      const currentDefinitionHash = conflictValue(error, 'current_definition_hash')
      if (currentSource !== null && currentDefinitionHash !== null) {
        editConflict.value = {
          message: error.message,
          currentSource,
          currentDefinitionHash,
        }
      } else {
        codeError.value = error.message
      }
    } else {
      codeError.value = error instanceof Error ? error.message : String(error)
    }
  } finally {
    codeSaving.value = false
  }
}

const reloadConflictingCode = (): void => {
  if (!editConflict.value) return
  codeDraft.value = editConflict.value.currentSource
  acceptedCode.value = editConflict.value.currentSource
  editBaseDefinitionHash.value = editConflict.value.currentDefinitionHash
  editConflict.value = null
  codeError.value = ''
  codeAwaitingAcceptance.value = false
}

const resetCode = (): void => {
  codeDraft.value = acceptedCode.value
  editConflict.value = null
  codeError.value = ''
}

const run = async (force: boolean): Promise<void> => {
  requestPending.value = true
  requestError.value = ''
  try {
    await props.client.rpc('run', {
      target: props.cell.slug,
      ...(props.branch ? { branch: props.branch } : {}),
      force,
      actor: 'user:ui',
      intent: `${force ? 'force run' : 'run'} ${props.cell.slug}`,
    })
  } catch (error) {
    requestError.value = error instanceof Error ? error.message : String(error)
  } finally {
    requestPending.value = false
  }
}

const cancelRun = async (): Promise<void> => {
  if (!props.cell.run_id) return
  cancelPending.value = true
  requestError.value = ''
  try {
    await props.client.rpc('cancel', { run_id: props.cell.run_id })
  } catch (error) {
    requestError.value = error instanceof Error ? error.message : String(error)
  } finally {
    cancelPending.value = false
  }
}

const expandPage = async (): Promise<void> => {
  if (!selectedOutput.value) return
  pageLoading.value = true
  pageError.value = ''
  try {
    page.value = await props.client.assetPage(`${props.cell.slug}.${selectedOutput.value.name}`)
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : String(error)
  } finally {
    pageLoading.value = false
  }
}

const promoteOutput = async (): Promise<void> => {
  const output = selectedOutput.value
  if (!output || !output.content_hash || promotionDisabled.value) return
  promotionPending.value = true
  promotionError.value = ''
  try {
    await props.client.rpc('promote', {
      slug: props.cell.slug,
      output: output.name,
      ...(props.branch ? { branch: props.branch } : {}),
      actor: 'user:ui',
      intent: `promote ${props.cell.slug}.${output.name}`,
    })
    promotionAwaiting.value = output.name
  } catch (error) {
    promotionError.value = error instanceof Error ? error.message : String(error)
  } finally {
    promotionPending.value = false
  }
}

watch(selected, () => {
  page.value = null
  pageError.value = ''
})

watch(
  () => props.uploadStates,
  (states) => {
    if (promotionAwaiting.value && states?.[promotionAwaiting.value]) {
      promotionAwaiting.value = null
    }
  },
  { deep: true },
)

watch([() => props.cell.source, () => props.cell.definition_hash], ([source, definitionHash]) => {
  if (codeDraft.value !== acceptedCode.value && codeDraft.value !== source) return
  codeDraft.value = source
  acceptedCode.value = source
  editBaseDefinitionHash.value = definitionHash
  codeAwaitingAcceptance.value = false
  editConflict.value = null
  codeError.value = ''
})

watch(
  () => props.cell.run_id,
  (runId, previousRunId) => {
    logSubscription?.close()
    logSubscription = null
    if (!runId) return
    requestPending.value = false
    if (runId !== previousRunId) consoleChunks.value = []
    hasConsole.value = true
    selected.value = 'console'
    logSubscription = props.client.subscribeRunLogs(runId, (message) => {
      consoleChunks.value.push(message.chunk.bytes)
    })
  },
  { immediate: true },
)

watch(
  failed,
  (isFailed) => {
    if (isFailed && props.cell.logs.length) selected.value = 'logs'
  },
  { immediate: true },
)

onBeforeUnmount(() => logSubscription?.close())
</script>
