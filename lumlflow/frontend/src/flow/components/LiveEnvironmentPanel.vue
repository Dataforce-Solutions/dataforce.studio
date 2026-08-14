<template>
  <section
    data-env-panel
    class="mb-4 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
  >
    <div class="flex items-start gap-3">
      <div class="min-w-0 flex-1">
        <h3 class="font-medium">Environment</h3>
        <p class="text-xs text-muted-color">Packages installed in this flow's uv environment.</p>
      </div>
      <button type="button" class="text-xs text-muted-color" @click="emit('close')">Close</button>
    </div>

    <div
      v-if="status?.restart_required"
      data-env-restart-banner
      class="mt-3 rounded border border-orange-300 bg-orange-50 p-3 text-sm text-orange-900 dark:border-orange-700 dark:bg-orange-950/30 dark:text-orange-200"
    >
      <p class="font-medium">Restart kernel to apply environment changes</p>
      <p v-if="status.restart_packages.length" class="mt-1 text-xs">
        Loaded packages changed: {{ status.restart_packages.join(', ') }}
      </p>
      <button
        type="button"
        data-restart-kernel
        class="mt-2 rounded border border-orange-400 px-2 py-1 text-xs"
        :disabled="pendingAction !== null"
        @click="restartKernel"
      >
        {{ pendingAction === 'restart' ? 'Restarting…' : 'Restart kernel' }}
      </button>
    </div>
    <p
      v-if="status?.branch_lock_mismatch"
      data-env-mismatch-banner
      class="mt-3 rounded border border-amber-300 px-3 py-2 text-sm text-amber-800 dark:border-amber-700 dark:text-amber-200"
    >
      This branch uses a different environment lock. Background work is deferred.
    </p>

    <p v-if="loading" role="status" class="mt-3 text-sm text-muted-color">Loading environment…</p>
    <p v-else-if="error" data-env-error role="alert" class="mt-3 text-sm text-red-600">
      {{ error }}
    </p>

    <ul
      v-if="status && packageEntries.length"
      class="mt-3 divide-y divide-surface-200 dark:divide-surface-700"
    >
      <li
        v-for="entry in packageEntries"
        :key="entry.name"
        data-env-package
        class="flex items-center gap-3 py-2 text-sm"
      >
        <span class="min-w-0 flex-1 font-mono">{{ entry.name }}</span>
        <span class="text-muted-color">{{ entry.version }}</span>
        <button
          type="button"
          data-remove-package
          class="text-xs text-red-600"
          :aria-label="`Remove ${entry.name}`"
          :disabled="pendingAction !== null"
          @click="changePackage('env_remove', entry.name)"
        >
          {{ pendingAction === `env_remove:${entry.name}` ? 'Removing…' : 'Remove' }}
        </button>
      </li>
    </ul>
    <p v-else-if="status && !packageEntries.length" class="mt-3 text-sm text-muted-color">
      Environment is empty.
    </p>

    <form class="mt-3 flex items-end gap-2" data-env-add-form @submit.prevent="addPackage">
      <label class="min-w-0 flex-1 text-sm">
        <span class="mb-1 block">Add package</span>
        <input
          v-model="packageDraft"
          name="env-package"
          class="w-full rounded border border-surface-300 bg-transparent px-2 py-1.5 font-mono dark:border-surface-600"
          placeholder="package or package==version"
          required
        />
      </label>
      <button
        type="submit"
        class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
        :disabled="pendingAction !== null || !packageDraft.trim()"
      >
        {{ pendingAction?.startsWith('env_add:') ? 'Adding…' : 'Add' }}
      </button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { FlowSessionClient } from '../api/client'
import type { JournalTransaction } from '../api/types'

interface EnvironmentStatus {
  lock_hash: string | null
  live_lock_hash: string | null
  branch_lock_mismatch: boolean
  background_deferred: boolean
  restart_required: boolean
  restart_packages: string[]
  packages: Record<string, string>
}

const props = defineProps<{
  client: FlowSessionClient
  transactions: JournalTransaction[]
}>()
const emit = defineEmits<{ close: [] }>()

const status = ref<EnvironmentStatus | null>(null)
const loading = ref(false)
const error = ref('')
const packageDraft = ref('')
const pendingAction = ref<string | null>(null)
const packageEntries = computed(() =>
  Object.entries(status.value?.packages ?? {})
    .map(([name, version]) => ({ name, version }))
    .sort((left, right) => left.name.localeCompare(right.name)),
)
const latestEnvStep = computed(() => {
  let step = 0
  for (const transaction of props.transactions) {
    if (transaction.ops.some(({ op }) => op === 'env_changed')) step = transaction.step
  }
  return step
})

const errorMessage = (value: unknown): string =>
  value instanceof Error ? value.message : String(value)

const loadStatus = async (): Promise<void> => {
  loading.value = status.value === null
  error.value = ''
  try {
    status.value = (await props.client.rpc('env_status')) as unknown as EnvironmentStatus
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    loading.value = false
  }
}

const changePackage = async (
  method: 'env_add' | 'env_remove',
  packageName: string,
): Promise<void> => {
  if (pendingAction.value !== null) return
  pendingAction.value = `${method}:${packageName}`
  error.value = ''
  try {
    await props.client.rpc(method, {
      package: packageName,
      actor: 'user:ui',
      intent: `${method === 'env_add' ? 'add' : 'remove'} environment package ${packageName}`,
    })
    packageDraft.value = ''
    await loadStatus()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    pendingAction.value = null
  }
}

const addPackage = async (): Promise<void> => {
  const packageName = packageDraft.value.trim()
  if (packageName) await changePackage('env_add', packageName)
}

const restartKernel = async (): Promise<void> => {
  if (pendingAction.value !== null) return
  pendingAction.value = 'restart'
  error.value = ''
  try {
    await props.client.rpc('kernel_restart', {
      actor: 'user:ui',
      intent: 'restart kernel',
    })
    await loadStatus()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    pendingAction.value = null
  }
}

watch(latestEnvStep, (step, previousStep) => {
  if (step > previousStep) void loadStatus()
})
onMounted(() => void loadStatus())
</script>
