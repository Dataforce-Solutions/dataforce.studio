<template>
  <div class="h-[calc(100vh-190px)] min-h-[32rem] flex gap-6 p-4">
    <aside
      data-live-railroad
      class="w-[430px] shrink-0 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 overflow-hidden flex flex-col"
    >
      <header
        class="flex items-center gap-3 px-5 py-4 border-b border-surface-200 dark:border-surface-700"
      >
        <span class="w-3 h-3 rounded-full shrink-0" :style="{ background: activeLaneColor }" />
        <div class="min-w-0 flex-1">
          <form
            v-if="renameOpen"
            class="flex gap-2"
            data-branch-rename
            @submit.prevent="renameBranch"
          >
            <input
              v-model="renameName"
              name="branch-name"
              class="min-w-0 flex-1 rounded border border-surface-300 bg-transparent px-2 py-1 text-sm dark:border-surface-600"
              required
            />
            <button type="submit" class="text-xs" :disabled="renamePending">
              {{ renamePending ? 'Saving…' : 'Save' }}
            </button>
            <button type="button" class="text-xs text-muted-color" @click="closeRename">
              Cancel
            </button>
          </form>
          <div v-else class="flex items-center gap-2">
            <p class="min-w-0 flex-1 font-medium truncate">{{ state.snapshot.branch }}</p>
            <button
              type="button"
              class="text-xs text-muted-color hover:text-color"
              aria-label="Rename branch"
              @click="openRename"
            >
              Rename
            </button>
          </div>
          <p class="text-xs text-muted-color">Railroad · step {{ state.snapshot.step }}</p>
        </div>
      </header>
      <p
        v-if="branchActionError"
        role="alert"
        data-branch-error
        class="border-b border-surface-200 px-5 py-2 text-xs text-red-600 dark:border-surface-700"
      >
        {{ branchActionError }}
      </p>
      <p
        v-else-if="switchPending"
        data-branch-switch-pending
        class="border-b border-surface-200 px-5 py-2 text-xs text-muted-color dark:border-surface-700"
      >
        Switching branch…
      </p>
      <RailroadTimeline
        class="flex-1 min-h-0"
        :rail-layout="railLayout"
        :current-branch-id="activeBranchId"
        :current-step="state.snapshot.step"
        :pulse="isRunning"
        @select="selectStop"
      />
    </aside>

    <main class="flex-1 min-w-0 overflow-auto">
      <section
        v-if="selectedStop"
        data-transaction-detail
        class="mb-4 rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4"
      >
        <div class="flex items-start gap-4">
          <div class="min-w-0 flex-1">
            <p class="text-xs text-muted-color">Selected stop · step {{ selectedStop.step }}</p>
            <h3 class="font-medium">{{ selectedStop.label }}</h3>
            <p v-if="selectedStop.affectedCells.length" class="mt-1 text-sm text-muted-color">
              Affected cells: {{ selectedStop.affectedCells.join(', ') }}
            </p>
          </div>
          <button
            type="button"
            class="text-xs text-muted-color hover:text-color"
            aria-label="Close transaction details"
            @click="selectedStopKey = null"
          >
            Close
          </button>
        </div>
        <ol v-if="selectedStop.transactions.length" class="mt-3 space-y-2">
          <li
            v-for="transaction in selectedStop.transactions"
            :key="`${transaction.branch}:${transaction.step}:${transaction.actor}:${transaction.intent}`"
            class="text-sm"
          >
            <span class="font-medium">{{ transaction.intent }}</span>
            <span class="text-muted-color"> · {{ transaction.actor }}</span>
            <span class="block text-xs text-muted-color">
              {{ operationSummary(transaction) }}
            </span>
          </li>
        </ol>
        <p v-else class="mt-3 text-sm text-muted-color">Branch created at this stop.</p>
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <button
            v-if="!forkOpen"
            type="button"
            data-fork-from-stop
            class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
            @click="openFork"
          >
            Fork from here
          </button>
          <button
            v-if="!preflightResult"
            type="button"
            data-rewind-preflight
            class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
            :disabled="preflightPending"
            @click="preflightRewind"
          >
            {{ preflightPending ? 'Checking impact…' : 'Rewind here…' }}
          </button>
        </div>
        <form
          v-if="forkOpen"
          data-fork-form
          class="mt-3 rounded border border-surface-200 p-3 dark:border-surface-700"
          @submit.prevent="forkFromStop"
        >
          <label class="text-sm">
            <span class="mb-1 block">New branch name</span>
            <input
              v-model="forkName"
              name="fork-name"
              class="w-full rounded border border-surface-300 bg-transparent px-2 py-1.5 dark:border-surface-600"
              required
            />
          </label>
          <div class="mt-2 flex gap-2">
            <button type="submit" class="text-sm" :disabled="forkPending">
              {{ forkPending ? 'Forking…' : 'Create branch' }}
            </button>
            <button type="button" class="text-sm text-muted-color" @click="closeFork">
              Cancel
            </button>
          </div>
          <p v-if="forkError" role="alert" class="mt-2 text-xs text-red-600">{{ forkError }}</p>
        </form>
        <section
          v-if="preflightResult"
          data-rewind-confirmation
          class="mt-3 rounded border border-orange-300 bg-orange-50 p-3 text-sm dark:border-orange-700 dark:bg-orange-950/30"
        >
          <p class="font-medium">Rewind impact</p>
          <p class="mt-1">
            {{ preflightResult.recompute.length }} cell{{
              preflightResult.recompute.length === 1 ? '' : 's'
            }}
            will need recomputation · estimated cost {{ estimatedRewindCost }}
          </p>
          <ul v-if="preflightResult.recompute.length" class="mt-2 list-disc pl-5">
            <li v-for="item in preflightResult.recompute" :key="item.cell">
              {{ item.cell }} · {{ formatCost(item.cost_seconds) }}
            </li>
          </ul>
          <p v-if="preflightResult.irrecoverable.length" class="mt-2 text-red-700">
            Irrecoverable: {{ preflightResult.irrecoverable.join(', ') }}
          </p>
          <div class="mt-3 flex gap-2">
            <button
              type="button"
              data-confirm-rewind
              class="rounded bg-orange-600 px-3 py-1.5 text-white"
              :disabled="rewindPending"
              @click="confirmRewind"
            >
              {{ rewindPending ? 'Rewinding…' : 'Confirm rewind' }}
            </button>
            <button type="button" class="text-muted-color" @click="cancelRewind">Cancel</button>
          </div>
          <p v-if="rewindError" role="alert" class="mt-2 text-xs text-red-600">
            {{ rewindError }}
          </p>
        </section>
      </section>

      <LiveBranchDiff
        v-if="compareOpen"
        :client="client"
        :branches="state.lanes"
        :active-branch-id="activeBranchId"
        @close="compareOpen = false"
      />

      <LiveSweepComparison
        v-for="sweep in state.snapshot.sweeps"
        :key="sweep.group"
        :sweep="sweep"
        :client="client"
      />

      <aside
        v-if="state.catchUpGroups.length"
        class="mb-4 rounded-lg border border-surface-200 dark:border-surface-700 p-4"
      >
        <h3 class="font-medium mb-2">Catch-up by intent</h3>
        <ol class="space-y-2">
          <li
            v-for="group in state.catchUpGroups"
            :key="group.actor + ':' + group.intent"
            data-catchup-group
            class="text-sm"
          >
            <span class="font-medium">{{ group.intent }}</span>
            <span class="text-muted-color">
              · {{ group.actor }} · {{ group.transactions.length }} transaction{{
                group.transactions.length === 1 ? '' : 's'
              }}
            </span>
          </li>
        </ol>
      </aside>

      <section data-canvas-chrome class="mb-4">
        <div v-if="!newCellOpen" class="flex flex-wrap gap-2">
          <button
            type="button"
            data-new-cell
            class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
            @click="newCellOpen = true"
          >
            New cell
          </button>
          <button
            v-if="state.lanes.length > 1"
            type="button"
            data-open-branch-diff
            class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
            @click="compareOpen = true"
          >
            Compare branches
          </button>
          <button
            type="button"
            data-open-env
            class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
            @click="envOpen = !envOpen"
          >
            Environment
          </button>
        </div>
        <form
          v-else
          data-new-cell-form
          class="rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
          @submit.prevent="createCell"
        >
          <div class="flex items-end gap-3">
            <label class="min-w-0 flex-1 text-sm">
              <span class="mb-1 block">Cell slug</span>
              <input
                v-model="newCellSlug"
                name="new-cell-slug"
                class="w-full rounded border border-surface-300 bg-transparent px-2 py-1.5 font-mono dark:border-surface-600"
                placeholder="train_model"
                required
              />
            </label>
            <button
              type="submit"
              class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
              :disabled="createPending || !newCellSlug.trim()"
            >
              {{ createPending ? 'Creating…' : 'Create cell' }}
            </button>
            <button
              type="button"
              class="px-2 py-1.5 text-sm text-muted-color"
              @click="closeNewCell"
            >
              Cancel
            </button>
          </div>
          <label class="mt-3 block text-sm">
            <span class="mb-1 block"
              >Starter source <span class="text-muted-color">(optional)</span></span
            >
            <textarea
              v-model="newCellSource"
              name="new-cell-source"
              class="block min-h-28 w-full resize-y rounded border border-surface-300 bg-transparent p-2 font-mono text-xs dark:border-surface-600"
              placeholder="Leave blank to use the generated starter."
              spellcheck="false"
            />
          </label>
          <p v-if="createError" role="alert" class="mt-2 text-xs text-red-600">{{ createError }}</p>
          <p
            v-else-if="pendingCreationSlug && !createPending"
            data-create-pending-acceptance
            class="mt-2 text-xs text-muted-color"
          >
            Created {{ pendingCreationSlug }}. Waiting for journal acceptance before adding its
            card.
          </p>
        </form>
      </section>

      <LiveEnvironmentPanel
        v-if="envOpen"
        :client="client"
        :transactions="state.transactions"
        @close="envOpen = false"
      />

      <ScratchConsole
        :asset-name="`branch ${state.snapshot.branch}`"
        :branch="activeBranchId"
        :client="client"
        class="mb-4"
      />

      <div
        data-live-canvas
        class="grid grid-cols-[repeat(auto-fit,minmax(min(32rem,100%),1fr))] items-start gap-4 pb-6"
      >
        <LiveCell
          v-for="cell in state.snapshot.cells"
          :key="cell.uid"
          :cell="cell"
          :client="client"
          :branch="state.snapshot.branch"
          :run-status="runStatusFor(cell)"
          :upload-states="uploadStatesFor(cell)"
        />
        <p v-if="!state.snapshot.cells.length" class="text-sm text-muted-color">
          No cells in this branch.
        </p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FlowSessionClient } from '../api/client'
import type { LiveJournalStop, LiveSessionState } from '../api/liveSession'
import type { JournalTransaction, LiveCell as LiveCellRecord, UploadQueueState } from '../api/types'
import RailroadTimeline from '../concepts/railroad/RailroadTimeline.vue'
import { buildLiveRailLayout } from '../concepts/railroad/railLayout'
import LiveBranchDiff from './LiveBranchDiff.vue'
import LiveCell from './LiveCell.vue'
import LiveEnvironmentPanel from './LiveEnvironmentPanel.vue'
import LiveSweepComparison from './LiveSweepComparison.vue'
import ScratchConsole from './ScratchConsole.vue'

const props = defineProps<{
  state: LiveSessionState
  client: FlowSessionClient
}>()

const selectedStopKey = ref<string | null>(null)
const compareOpen = ref(false)
const envOpen = ref(false)
const branchActionError = ref('')
const switchPending = ref(false)
const renameOpen = ref(false)
const renameName = ref('')
const renamePending = ref(false)
const forkOpen = ref(false)
const forkName = ref('')
const forkPending = ref(false)
const forkError = ref('')
const preflightPending = ref(false)
const rewindPending = ref(false)
const rewindError = ref('')
interface RewindPreflight {
  branch: string
  to_step: number
  recompute: { cell: string; cost_seconds: number | null }[]
  irrecoverable: string[]
}
const preflightResult = ref<RewindPreflight | null>(null)
const newCellOpen = ref(false)
const newCellSlug = ref('')
const newCellSource = ref('')
const createPending = ref(false)
const createError = ref('')
const pendingCreationSlug = ref<string | null>(null)
const railLayout = computed(() => buildLiveRailLayout(props.state.lanes, props.state.stops))
const activeBranchId = computed(
  () =>
    props.state.lanes.find(({ name }) => name === props.state.snapshot.branch)?.branch_id ??
    props.state.lanes[0]?.branch_id ??
    props.state.snapshot.branch,
)
const activeLaneColor = computed(
  () =>
    railLayout.value.lanes.find(({ branchId }) => branchId === activeBranchId.value)?.color ??
    'var(--p-primary-500)',
)
const isRunning = computed(() => props.state.snapshot.cells.some(({ run_id }) => run_id !== null))
const selectedStop = computed<LiveJournalStop | null>(() =>
  selectedStopKey.value
    ? (props.state.stops.find(({ key }) => key === selectedStopKey.value) ?? null)
    : null,
)
const estimatedRewindCost = computed(() => {
  const result = preflightResult.value
  if (!result || result.recompute.some(({ cost_seconds }) => cost_seconds === null))
    return 'unknown'
  const seconds = result.recompute.reduce((total, item) => total + (item.cost_seconds ?? 0), 0)
  return formatCost(seconds)
})

const selectStop = async (branchId: string, step: number, laneHead: boolean): Promise<void> => {
  if (laneHead && branchId !== activeBranchId.value) {
    await switchBranch(branchId)
    return
  }
  selectedStopKey.value =
    props.state.stops.find(({ branch, step: stopStep }) => branch === branchId && stopStep === step)
      ?.key ?? null
  closeFork()
  cancelRewind()
}

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error)

const switchBranch = async (branchId: string): Promise<void> => {
  if (switchPending.value) return
  switchPending.value = true
  branchActionError.value = ''
  selectedStopKey.value = null
  try {
    const name = props.state.lanes.find(({ branch_id }) => branch_id === branchId)?.name ?? branchId
    await props.client.rpc('switch', {
      branch: branchId,
      actor: 'user:ui',
      intent: `switch to ${name}`,
    })
  } catch (error) {
    branchActionError.value = errorMessage(error)
  } finally {
    switchPending.value = false
  }
}

const openRename = (): void => {
  renameName.value = props.state.snapshot.branch
  renameOpen.value = true
  branchActionError.value = ''
}

const closeRename = (): void => {
  renameOpen.value = false
  renameName.value = ''
}

const renameBranch = async (): Promise<void> => {
  const name = renameName.value.trim()
  if (!name || renamePending.value) return
  const oldName = props.state.snapshot.branch
  renamePending.value = true
  branchActionError.value = ''
  try {
    await props.client.rpc('rename', {
      branch: activeBranchId.value,
      name,
      actor: 'user:ui',
      intent: `rename ${oldName} to ${name}`,
    })
    closeRename()
  } catch (error) {
    branchActionError.value = errorMessage(error)
  } finally {
    renamePending.value = false
  }
}

const openFork = (): void => {
  forkOpen.value = true
  forkError.value = ''
}

const closeFork = (): void => {
  forkOpen.value = false
  forkName.value = ''
  forkError.value = ''
}

const forkFromStop = async (): Promise<void> => {
  const stop = selectedStop.value
  const name = forkName.value.trim()
  if (!stop || !name || forkPending.value) return
  forkPending.value = true
  forkError.value = ''
  try {
    await props.client.rpc('fork', {
      name,
      parent: stop.branch,
      step: stop.step,
      actor: 'user:ui',
      intent: `fork ${name} from ${branchName(stop.branch)}`,
    })
    closeFork()
  } catch (error) {
    forkError.value = errorMessage(error)
  } finally {
    forkPending.value = false
  }
}

const branchName = (branchId: string): string =>
  props.state.lanes.find(({ branch_id }) => branch_id === branchId)?.name ?? branchId

const formatCost = (seconds: number | null): string =>
  seconds === null ? 'unknown' : `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)} s`

const preflightRewind = async (): Promise<void> => {
  const stop = selectedStop.value
  if (!stop || preflightPending.value) return
  preflightPending.value = true
  rewindError.value = ''
  branchActionError.value = ''
  try {
    preflightResult.value = (await props.client.rpc('preflight', {
      branch: stop.branch,
      step: stop.step,
    })) as unknown as RewindPreflight
  } catch (error) {
    rewindError.value = errorMessage(error)
    branchActionError.value = rewindError.value
  } finally {
    preflightPending.value = false
  }
}

const cancelRewind = (): void => {
  preflightResult.value = null
  rewindError.value = ''
}

const confirmRewind = async (): Promise<void> => {
  const stop = selectedStop.value
  if (!stop || !preflightResult.value || rewindPending.value) return
  rewindPending.value = true
  rewindError.value = ''
  try {
    await props.client.rpc('rewind', {
      branch: stop.branch,
      step: stop.step,
      actor: 'user:ui',
      intent: `rewind ${branchName(stop.branch)} to step ${stop.step}`,
    })
    cancelRewind()
  } catch (error) {
    rewindError.value = errorMessage(error)
  } finally {
    rewindPending.value = false
  }
}

const operationSummary = (transaction: JournalTransaction): string => {
  const counts = new Map<string, number>()
  for (const operation of transaction.ops) {
    const label = operation.op.replace(/_/g, ' ')
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  return [...counts]
    .map(([label, count]) => (count === 1 ? label : `${label} × ${count}`))
    .join(', ')
}

const closeNewCell = (): void => {
  newCellOpen.value = false
  newCellSlug.value = ''
  newCellSource.value = ''
  createError.value = ''
  pendingCreationSlug.value = null
}

const createCell = async (): Promise<void> => {
  const slug = newCellSlug.value.trim()
  if (!slug || createPending.value) return
  createPending.value = true
  createError.value = ''
  pendingCreationSlug.value = slug
  try {
    await props.client.rpc('cells_new', {
      slug,
      ...(newCellSource.value.trim() ? { source: newCellSource.value } : {}),
      actor: 'user:ui',
      intent: `create ${slug}`,
    })
    if (props.state.snapshot.cells.some((cell) => cell.slug === slug)) closeNewCell()
  } catch (error) {
    pendingCreationSlug.value = null
    createError.value = error instanceof Error ? error.message : String(error)
  } finally {
    createPending.value = false
  }
}

const runStatusFor = (cell: LiveCellRecord): 'memo-hit' | 'failed' | 'cancelled' | null => {
  let status: 'memo-hit' | 'failed' | 'cancelled' | null = null
  for (const transaction of props.state.transactions) {
    if (transaction.branch !== activeBranchId.value) continue
    for (const operation of transaction.ops) {
      if (
        operation.op === 'cell_accepted' &&
        operation.uid === cell.uid &&
        operation.version_id === cell.version_id
      ) {
        status = null
      } else if (
        operation.op === 'memo_hit' &&
        operation.uid === cell.uid &&
        operation.version_id === cell.version_id
      ) {
        status = 'memo-hit'
      } else if (operation.op === 'run_recorded' && operation.version_id === cell.version_id) {
        status =
          operation.state === 'failed' || operation.state === 'cancelled' ? operation.state : null
      }
    }
  }
  return status
}

const uploadStatesFor = (cell: LiveCellRecord): Record<string, UploadQueueState> => {
  let materializationId: string | null = null
  for (const transaction of props.state.transactions) {
    if (transaction.branch !== activeBranchId.value) continue
    for (const operation of transaction.ops) {
      if (operation.op === 'run_recorded' && operation.version_id === cell.version_id) {
        materializationId = operation.mat_id
      } else if (
        operation.op === 'memo_hit' &&
        operation.uid === cell.uid &&
        operation.version_id === cell.version_id &&
        operation.mat_id !== null
      ) {
        materializationId = operation.mat_id
      }
    }
  }
  if (materializationId === null) return {}

  const states: Record<string, UploadQueueState> = {}
  for (const transaction of props.state.transactions) {
    for (const operation of transaction.ops) {
      if (operation.op === 'upload_state' && operation.mat_id === materializationId) {
        states[operation.output] = {
          state: operation.state,
          attempts: operation.attempts,
          error: operation.error,
        }
      }
    }
  }
  return states
}

watch(
  () => props.state.stops,
  () => {
    if (selectedStopKey.value && !selectedStop.value) selectedStopKey.value = null
  },
)

watch(
  () => props.state.snapshot.cells,
  (cells) => {
    if (pendingCreationSlug.value && cells.some(({ slug }) => slug === pendingCreationSlug.value)) {
      closeNewCell()
    }
  },
)
</script>
