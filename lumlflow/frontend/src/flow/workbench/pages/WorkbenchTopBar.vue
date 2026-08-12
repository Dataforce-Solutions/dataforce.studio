<template>
  <header
    class="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-surface-200 bg-surface-0 px-4 py-2.5 dark:border-surface-700 dark:bg-surface-900"
  >
    <div class="flex items-center gap-2.5 min-w-0">
      <h2 class="font-mono text-base font-semibold">{{ session.flowName }}</h2>
      <FlowStateDot :state="session.state" />
    </div>

    <div class="flex items-center gap-1.5 min-w-0">
      <template v-if="viewingOther">
        <Eye
          v-tooltip.bottom="'Viewing is a pure store read — no lock, no kernel'"
          :size="13"
          class="shrink-0 text-muted-color"
        />
        <span class="text-xs text-muted-color">viewing</span>
      </template>
      <BranchTag :name="viewedBranch" :checked-out="!viewingOther" />
      <span v-if="viewingOther" class="text-xs text-muted-color whitespace-nowrap">
        · files stay on <code class="font-mono text-[11px]">{{ session.worktreeBranch }}</code>
      </span>
    </div>

    <div v-if="session.paired" class="flex items-center gap-2 min-w-0">
      <ActorChip :actor="{ kind: 'agent', label: session.paired.label }" muted />
      <span class="truncate text-xs text-muted-color max-w-72">{{ pairedLine }}</span>
    </div>

    <CatchUpMarker
      v-if="session.changesBehind"
      :count="session.changesBehind"
      @open="emit('open-catchup')"
    />

    <div class="ml-auto flex items-center gap-2">
      <SelectButton
        v-model="view"
        :options="VIEW_OPTIONS"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        aria-label="view"
      />

      <template v-if="branchPreflight">
        <PreflightPopover
          v-if="!opsDisabled"
          :preflight="branchPreflight"
          :target="viewedBranch"
          label="Rerun branch"
          @run="emit('rerun-branch', $event)"
        />
        <Button v-else text size="small" label="Rerun branch" disabled>
          <template #icon><Play :size="14" /></template>
        </Button>

        <Button
          label="Stop session"
          size="small"
          severity="danger"
          outlined
          :disabled="opsDisabled"
          @click="stopPopover?.toggle($event)"
        >
          <template #icon><OctagonX :size="13" /></template>
        </Button>
        <Popover ref="stopPopover">
          <div class="flex w-80 flex-col gap-2.5">
            <p class="text-sm font-medium">Stop this session?</p>
            <p class="text-xs text-muted-color">
              cancels the in-flight run and drains the queue — the part the daemon owns
            </p>
            <p class="text-xs text-muted-color">
              stopping the <span class="font-medium">agent</span> happens in its own terminal
              (Ctrl+C) — or hand it this:
            </p>
            <CopyField :value="stopPayload" />
            <div class="flex justify-end gap-2">
              <Button
                size="small"
                text
                severity="secondary"
                label="keep running"
                @click="stopPopover?.hide()"
              />
              <Button size="small" severity="danger" label="stop session" @click="confirmStop" />
            </div>
          </div>
        </Popover>
      </template>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Button, Popover, SelectButton } from 'primevue'
import { Eye, OctagonX, Play } from 'lucide-vue-next'
import PreflightPopover from '../components/card/PreflightPopover.vue'
import CatchUpMarker from '../components/session/CatchUpMarker.vue'
import type { Preflight, WorkbenchSession } from '../model/types'
import ActorChip from '../ui/ActorChip.vue'
import BranchTag from '../ui/BranchTag.vue'
import CopyField from '../ui/CopyField.vue'
import FlowStateDot from '../ui/FlowStateDot.vue'

/**
 * The workbench's top strip: identity and state on the left, the two
 * session-wide ops on the right. Stop-session carries its honest scope — the
 * daemon owns the run queue, the agent's process is not ours to kill.
 */
const props = defineProps<{
  session: WorkbenchSession
  viewedBranch: string
  /** Batch preflight for rerun-to-leaves; null hides both session ops (empty slice). */
  branchPreflight: Preflight | null
  opsDisabled?: boolean
}>()

const emit = defineEmits<{
  'rerun-branch': [payload: { force: boolean }]
  'stop-session': []
  'open-catchup': []
}>()

const view = defineModel<'canvas' | 'notebook'>('view', { required: true })

const VIEW_OPTIONS = [
  { label: 'canvas', value: 'canvas' },
  { label: 'notebook', value: 'notebook' },
]

const stopPopover = useTemplateRef<InstanceType<typeof Popover>>('stopPopover')

const viewingOther = computed(() => props.viewedBranch !== props.session.worktreeBranch)

const pairedLine = computed(() => {
  const paired = props.session.paired
  if (!paired) return ''
  if (paired.state === 'working') return paired.task ?? 'working'
  return `idle${paired.idleFor ? ` · ${paired.idleFor} since last transaction` : ''}`
})

const stopPayload = computed(
  () => `lumlflow agent prompt stop --branch ${props.session.worktreeBranch}`,
)

function confirmStop(): void {
  emit('stop-session')
  stopPopover.value?.hide()
}
</script>
