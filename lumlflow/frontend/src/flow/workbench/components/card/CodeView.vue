<template>
  <div class="flex flex-col gap-3">
    <div v-if="paramNames.length" class="flex flex-col gap-1.5">
      <p class="text-[11px] uppercase tracking-wide text-muted-color">
        params — declared data, editable without touching source
      </p>
      <div class="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 max-w-md">
        <template v-for="name in paramNames" :key="name">
          <label class="font-mono text-xs text-muted-color" :for="`${fieldId}-${name}`">
            {{ name }}
          </label>
          <InputText
            :id="`${fieldId}-${name}`"
            v-model="draftParams[name]"
            size="small"
            class="font-mono text-xs!"
          />
        </template>
      </div>
      <div class="flex items-center gap-2.5 flex-wrap">
        <Button size="small" outlined label="apply" :disabled="!paramsDirty" @click="applyParams" />
        <p class="text-[11px] text-muted-color">
          a params-only version; marks this cell stale (definition changed)
        </p>
      </div>
    </div>

    <div class="flex flex-col gap-1.5">
      <div class="flex items-center justify-between gap-2">
        <p class="text-[11px] uppercase tracking-wide text-muted-color">source</p>
        <div class="flex items-center gap-1">
          <template v-if="editing">
            <Button size="small" text severity="secondary" label="cancel" @click="cancelEdit" />
            <Button size="small" label="save" @click="saveEdit" />
          </template>
          <Button v-else size="small" text severity="secondary" label="edit" @click="startEdit">
            <template #icon><Pencil :size="12" /></template>
          </Button>
        </div>
      </div>

      <Textarea
        v-if="editing"
        v-model="draftSource"
        :rows="sourceRows"
        class="w-full font-mono text-xs! leading-relaxed"
      />
      <pre v-else :class="sourceClass">{{ cell.source.trimEnd() }}</pre>

      <p
        v-if="cell.pendingProjection"
        class="flex items-center gap-1.5 text-[11px] text-sky-700 dark:text-sky-300"
      >
        <Info :size="12" class="shrink-0" />
        saved · not yet written to files (worktree lock held)
      </p>
      <p class="text-[11px] text-muted-color">
        edits land as a new version through the daemon — files are never rewritten under a working
        agent
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { Button, InputText, Textarea } from 'primevue'
import { Info, Pencil } from 'lucide-vue-next'
import type { FlowCell, ParamValue } from '../../model/types'

/**
 * The code tab: read-only source with a mock edit toggle (real editing is
 * Monaco later; the contract is the same — save emits, the daemon lands a
 * version) and the params grid above it, because params are declared data and
 * never require touching source.
 */
const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
}>()

const emit = defineEmits<{
  edit: [payload: { source: string }]
  'edit-params': [params: Record<string, ParamValue>]
}>()

const fieldId = useId()

const sourceClass = computed(() => [
  'font-mono text-xs leading-relaxed rounded-md border border-surface-200 dark:border-surface-700',
  'bg-surface-50 dark:bg-surface-800 p-3 overflow-auto',
  props.density === 'canvas' ? 'max-h-72' : 'max-h-96',
])

// --- params ---------------------------------------------------------------

const paramNames = computed(() => Object.keys(props.cell.params))

function displayOf(value: ParamValue): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function parseParam(text: string): ParamValue {
  try {
    return JSON.parse(text) as ParamValue
  } catch {
    return text
  }
}

const initialParams = computed<Record<string, string>>(() =>
  Object.fromEntries(
    Object.entries(props.cell.params).map(([key, value]) => [key, displayOf(value)]),
  ),
)

const draftParams = ref<Record<string, string>>({})

watch(
  initialParams,
  (initial) => {
    draftParams.value = { ...initial }
  },
  { immediate: true },
)

const paramsDirty = computed(() =>
  paramNames.value.some((name) => draftParams.value[name] !== initialParams.value[name]),
)

function applyParams(): void {
  const params: Record<string, ParamValue> = Object.fromEntries(
    paramNames.value.map((name) => [name, parseParam(draftParams.value[name] ?? '')]),
  )
  emit('edit-params', params)
}

// --- source ---------------------------------------------------------------

const editing = ref(false)
const draftSource = ref('')

const sourceRows = computed(() => Math.min(props.cell.source.split('\n').length + 1, 20))

function startEdit(): void {
  draftSource.value = props.cell.source
  editing.value = true
}

function saveEdit(): void {
  emit('edit', { source: draftSource.value })
  editing.value = false
}

function cancelEdit(): void {
  editing.value = false
}
</script>
