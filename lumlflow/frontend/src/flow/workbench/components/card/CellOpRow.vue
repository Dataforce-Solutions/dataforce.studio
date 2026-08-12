<template>
  <div class="flex items-center gap-0.5 shrink-0">
    <PreflightPopover
      v-if="!cell.isNote && cell.status !== 'running'"
      :preflight="effectivePreflight"
      :target="cell.slug"
      @run="emit('run', $event)"
    />
    <Button
      v-if="!cell.isNote && cell.status === 'running'"
      v-tooltip.top="stopTooltip"
      text
      rounded
      severity="danger"
      size="small"
      :aria-label="stopTooltip"
      @click="emit('stop')"
    >
      <template #icon><Square :size="14" /></template>
    </Button>

    <Button
      v-tooltip.top="'expand — the full value in a drawer; may start the kernel'"
      text
      rounded
      severity="secondary"
      size="small"
      aria-label="expand"
      @click="emit('expand')"
    >
      <template #icon><Maximize2 :size="14" /></template>
    </Button>

    <Button
      v-tooltip.top="navLabel"
      text
      rounded
      severity="secondary"
      size="small"
      :aria-label="navLabel"
      @click="emit('navigate', navTarget)"
    >
      <template #icon>
        <NotebookText v-if="density === 'canvas'" :size="14" />
        <Workflow v-else :size="14" />
      </template>
    </Button>

    <SendToAgentButton
      :cell="cell"
      :branch="branch"
      gesture="explain"
      @send-to-agent="emit('send-to-agent', $event)"
    />

    <span ref="moreAnchor" class="inline-flex">
      <Button
        v-tooltip.top="'more'"
        text
        rounded
        severity="secondary"
        size="small"
        aria-label="more"
        @click="menu?.toggle($event)"
      >
        <template #icon><EllipsisVertical :size="14" /></template>
      </Button>
    </span>
    <Menu ref="menu" :model="menuItems" popup />

    <Popover ref="confirmPopover">
      <div class="w-72 flex flex-col gap-2.5">
        <p class="text-sm">
          delete <code class="font-mono">{{ cell.slug }}</code> from this branch?
        </p>
        <p class="text-xs text-muted-color">
          removes <code class="font-mono text-[11px]">{{ cell.slug }}</code> from THIS branch's
          selection; other branches keep it; consumers here will show a flagged reference
        </p>
        <div class="flex justify-end gap-2">
          <Button
            size="small"
            text
            severity="secondary"
            label="keep"
            @click="confirmPopover?.hide()"
          />
          <Button
            size="small"
            severity="danger"
            label="delete from this branch"
            @click="confirmDelete"
          />
        </div>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { Button, Menu, Popover } from 'primevue'
import type { MenuItem } from 'primevue/menuitem'
import { EllipsisVertical, Maximize2, NotebookText, Square, Workflow } from 'lucide-vue-next'
import { formatCost, formatCount } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type { FlowCell, Preflight } from '../../model/types'
import SendToAgentButton from '../handoff/SendToAgentButton.vue'
import PreflightPopover from './PreflightPopover.vue'

/**
 * The op row: every verb the card offers, each mapped to a daemon op and each
 * honest about scope — the preflight before any run, awaiter-aware stop
 * wording, a per-branch delete confirm, duplicate buried behind fork.
 */
const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
  awaiters?: number
  preflight?: Preflight
  branch?: string
}>()

const emit = defineEmits<{
  run: [payload: { force: boolean }]
  stop: []
  expand: []
  navigate: [payload: { view: 'canvas' | 'notebook'; slug: string }]
  'send-to-agent': [payload: string]
  rename: []
  delete: []
  duplicate: []
}>()

const menu = useTemplateRef<InstanceType<typeof Menu>>('menu')
const confirmPopover = useTemplateRef<InstanceType<typeof Popover>>('confirmPopover')
const moreAnchor = useTemplateRef<HTMLElement>('moreAnchor')

const awaiters = computed(() => props.awaiters ?? 0)

const effectivePreflight = computed<Preflight>(() => {
  if (props.preflight) return props.preflight
  const seconds = props.cell.timing?.costSeconds ?? 1
  return { cached: [], recompute: [{ slug: props.cell.slug, seconds }], totalSeconds: seconds }
})

// Preemption fires only when no awaiter still wants the result; when other
// branches await the run, stop only requeues this branch.
const stopTooltip = computed(() => {
  if (awaiters.value === 0) return 'stop the run'
  const verb = awaiters.value === 1 ? 'awaits' : 'await'
  return `leave the run, requeue this branch — ${formatCount(awaiters.value, 'other branch')} still ${verb} it`
})

const navLabel = computed(() => (props.density === 'canvas' ? 'open in notebook' : 'see in canvas'))

const navTarget = computed<{ view: 'canvas' | 'notebook'; slug: string }>(() => ({
  view: props.density === 'canvas' ? 'notebook' : 'canvas',
  slug: props.cell.slug,
}))

const eager = ref(props.cell.eager ?? false)

const downloadLabel = computed(() => {
  const primary = primaryOutput(props.cell)
  if (primary?.neverPersisted) {
    const seconds = props.preflight?.totalSeconds ?? props.cell.timing?.costSeconds ?? 10
    return `materialize and download · ~${formatCost(seconds)}`
  }
  return 'download'
})

const hasInlineAsset = computed(() =>
  props.cell.outputs.some((output) => output.declared === 'asset'),
)

const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [{ label: 'rename', command: () => emit('rename') }]
  if (!props.cell.isNote) {
    items.push({
      label: eager.value ? 'eager materialization · on' : 'eager materialization · off',
      command: () => {
        eager.value = !eager.value
      },
    })
    items.push({ label: downloadLabel.value, command: () => undefined })
    if (hasInlineAsset.value) items.push({ label: 'promote to LUML', command: () => undefined })
  }
  items.push({
    label: 'duplicate — mints a new identity with no consumers · prefer forking',
    command: () => emit('duplicate'),
  })
  items.push({ separator: true })
  items.push({
    label: 'delete from this branch…',
    command: (event) => {
      confirmPopover.value?.show(event.originalEvent, moreAnchor.value)
    },
  })
  return items
})

function confirmDelete(): void {
  emit('delete')
  confirmPopover.value?.hide()
}
</script>
