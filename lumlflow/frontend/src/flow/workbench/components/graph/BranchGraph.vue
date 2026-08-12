<template>
  <div class="flex flex-col gap-2 min-w-0">
    <div v-if="selectable" class="flex items-center gap-3 px-1">
      <Button
        :label="compareLabel"
        size="small"
        :disabled="!compareReady"
        @click="emit('compare', [...selected])"
      >
        <template #icon>
          <Columns3 :size="13" />
        </template>
      </Button>
      <p class="text-xs text-muted-color">select 2–5 branches to compare</p>
    </div>

    <div class="flex min-w-0">
      <svg :width="RAIL_W" :height="railHeight" class="shrink-0" aria-hidden="true">
        <g v-for="lane in lanes" :key="lane.name" :opacity="lane.archived ? 0.45 : 1">
          <path
            v-if="lane.forkPath"
            :d="lane.forkPath"
            fill="none"
            :stroke="lane.color"
            stroke-width="1.5"
            stroke-linecap="round"
          />
          <line
            :x1="lane.x1"
            :y1="lane.y"
            :x2="lane.x2"
            :y2="lane.y"
            :stroke="lane.color"
            stroke-width="1.5"
            stroke-linecap="round"
          />
          <circle
            v-if="lane.checkedOut"
            :cx="lane.x2"
            :cy="lane.y"
            r="7.5"
            fill="none"
            :stroke="lane.color"
            stroke-width="1.5"
            opacity="0.45"
          />
          <circle :cx="lane.x2" :cy="lane.y" r="4.5" :fill="lane.color" />
        </g>
      </svg>

      <ul class="flex-1 min-w-0 flex flex-col">
        <li
          v-for="branch in visible"
          :key="branch.name"
          class="flex items-center gap-3 min-w-0 rounded px-2 hover:bg-surface-50 dark:hover:bg-surface-800/60"
          :style="{ height: `${ROW_H}px` }"
          :class="branch.archived ? 'opacity-60' : ''"
        >
          <Checkbox v-if="selectable" v-model="selected" :value="branch.name" />

          <div class="min-w-0 flex-1 flex flex-col gap-0.5">
            <div class="flex items-center gap-2 min-w-0">
              <BranchTag
                :name="branch.name"
                :checked-out="branch.checkedOut"
                :archived="branch.archived"
              />
              <MetaBadge v-if="branch.settled" variant="settled" />
              <span
                v-if="branch.headlineMetric"
                class="font-mono text-[11px] text-muted-color shrink-0"
              >
                {{ branch.headlineMetric.name }} {{ formatMetric(branch.headlineMetric.value) }}
              </span>
              <ActorChip v-if="branch.agent" :actor="branch.agent" muted />
            </div>
            <div class="flex items-center gap-2 text-xs text-muted-color min-w-0">
              <span class="truncate">{{ branch.lastIntent }}</span>
              <span
                v-if="branch.sweepGroup"
                class="shrink-0 rounded bg-surface-100 dark:bg-surface-800 px-1 py-px text-[10px]"
              >
                sweep · {{ branch.sweepGroup }}
              </span>
            </div>
          </div>

          <div v-if="!selectable" class="flex items-center gap-0.5 shrink-0">
            <Button
              v-tooltip.top="'Pure store read — no lock, no kernel'"
              label="View"
              size="small"
              text
              severity="secondary"
              @click="emit('view', branch.name)"
            >
              <template #icon>
                <Eye :size="13" />
              </template>
            </Button>

            <template v-if="!branch.checkedOut">
              <span v-if="worktreeLocked" v-tooltip.top="LOCKED_TOOLTIP" class="inline-flex">
                <Button label="Check out" size="small" text severity="secondary" disabled>
                  <template #icon>
                    <FolderInput :size="13" />
                  </template>
                </Button>
              </span>
              <Button
                v-else
                v-tooltip.top="'Rebind the worktree files to this branch'"
                label="Check out"
                size="small"
                text
                severity="secondary"
                @click="emit('checkout', branch.name)"
              >
                <template #icon>
                  <FolderInput :size="13" />
                </template>
              </Button>
              <button
                v-if="worktreeLocked"
                v-tooltip.top="'Check out anyway — the agent loses its file view'"
                class="text-[11px] text-muted-color underline underline-offset-2 hover:text-surface-700 dark:hover:text-surface-200"
                @click="emit('checkout', branch.name)"
              >
                force
              </button>
            </template>

            <Button
              v-if="!branch.archived"
              v-tooltip.top="'Archive this branch'"
              size="small"
              text
              severity="secondary"
              aria-label="Archive"
              @click="emit('archive', branch.name)"
            >
              <template #icon>
                <Archive :size="13" />
              </template>
            </Button>
          </div>
        </li>
      </ul>
    </div>

    <button
      v-if="archivedCount > 0"
      class="self-start flex items-center gap-1 px-2 text-xs text-muted-color hover:text-surface-700 dark:hover:text-surface-200"
      @click="showArchived = !showArchived"
    >
      <ChevronRight
        :size="13"
        class="transition-transform"
        :class="showArchived ? 'rotate-90' : ''"
      />
      {{ showArchived ? 'hide archived' : `${archivedCount} archived` }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, Checkbox } from 'primevue'
import { Archive, ChevronRight, Columns3, Eye, FolderInput } from 'lucide-vue-next'
import { formatMetric } from '../../model/format'
import type { BranchInfo } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import BranchTag from '../../ui/BranchTag.vue'
import { branchColor } from '../../ui/kinds'
import MetaBadge from '../../ui/MetaBadge.vue'

/**
 * The fork tree: one lane per branch, x is the journal step, a curve from the
 * parent lane at the fork step. View and check out are separate verbs on
 * purpose — reading a branch is a pure store read, checking out rebinds the
 * single v1 worktree and waits on the agent's lock.
 */
const props = defineProps<{
  branches: BranchInfo[]
  selectable?: boolean
  worktreeLocked?: boolean
}>()

const emit = defineEmits<{
  view: [name: string]
  checkout: [name: string]
  archive: [name: string]
  compare: [names: string[]]
}>()

const ROW_H = 56
const RAIL_W = 190
const PAD_X = 14
const CURVE = 10

const LOCKED_TOOLTIP =
  'the agent is working in the files — you can look anywhere, but checking out waits'

const showArchived = ref(false)
const selected = ref<string[]>([])

/** Parent-first depth-first order so a child lane always sits below its parent. */
const ordered = computed<BranchInfo[]>(() => {
  const children = new Map<string | null, BranchInfo[]>()
  for (const branch of props.branches) {
    const list = children.get(branch.parent) ?? []
    list.push(branch)
    children.set(branch.parent, list)
  }
  for (const list of children.values()) {
    list.sort(
      (a, b) => (a.forkedAtStep ?? 0) - (b.forkedAtStep ?? 0) || a.name.localeCompare(b.name),
    )
  }
  const result: BranchInfo[] = []
  const visit = (parent: string | null): void => {
    for (const branch of children.get(parent) ?? []) {
      result.push(branch)
      visit(branch.name)
    }
  }
  visit(null)
  for (const branch of props.branches) if (!result.includes(branch)) result.push(branch)
  return result
})

const visible = computed(() =>
  ordered.value.filter((branch) => !branch.archived || showArchived.value),
)

const archivedCount = computed(() => props.branches.filter((branch) => branch.archived).length)

const railHeight = computed(() => visible.value.length * ROW_H)

// Scale over every branch (not just visible) so toggling archived never rescales.
const maxStep = computed(() => Math.max(1, ...props.branches.map((branch) => branch.headStep)))

function stepX(step: number): number {
  return PAD_X + (step / maxStep.value) * (RAIL_W - 2 * PAD_X)
}

interface Lane {
  name: string
  color: string
  x1: number
  x2: number
  y: number
  forkPath: string | null
  archived: boolean
  checkedOut: boolean
}

const lanes = computed<Lane[]>(() => {
  const indexByName = new Map(visible.value.map((branch, index) => [branch.name, index]))
  return visible.value.map((branch, index) => {
    const y = index * ROW_H + ROW_H / 2
    const forkX = branch.forkedAtStep !== null ? stepX(branch.forkedAtStep) : PAD_X
    const parentIndex = branch.parent !== null ? indexByName.get(branch.parent) : undefined
    let forkPath: string | null = null
    let x1 = forkX
    if (parentIndex !== undefined && branch.forkedAtStep !== null) {
      const parentY = parentIndex * ROW_H + ROW_H / 2
      const midY = (parentY + y) / 2
      forkPath = `M ${forkX} ${parentY} C ${forkX} ${midY} ${forkX} ${y} ${forkX + CURVE} ${y}`
      x1 = forkX + CURVE
    }
    return {
      name: branch.name,
      color: branchColor(branch.name),
      x1,
      x2: Math.max(x1, stepX(branch.headStep)),
      y,
      forkPath,
      archived: branch.archived === true,
      checkedOut: branch.checkedOut === true,
    }
  })
})

const compareReady = computed(() => selected.value.length >= 2 && selected.value.length <= 5)

const compareLabel = computed(() =>
  selected.value.length >= 2 ? `Compare ${selected.value.length} branches` : 'Compare branches',
)
</script>
