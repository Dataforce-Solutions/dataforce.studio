<template>
  <div class="relative h-full overflow-hidden bg-surface-50 dark:bg-surface-900/40">
    <div
      class="absolute top-2 left-2 z-10 flex flex-wrap items-center gap-1.5 text-xs pointer-events-none"
    >
      <span class="px-1.5 py-0.5 rounded bg-surface-0/80 dark:bg-surface-800/80 text-muted-color">
        {{ visibleCount }} of {{ layout.order.length }} assets
      </span>
      <button
        v-if="filterRootId"
        class="pointer-events-auto px-1.5 py-0.5 rounded border border-primary-500 text-primary-600 dark:text-primary-400 bg-surface-0/90 dark:bg-surface-800/90"
        @click="emit('filter', null)"
      >
        family of {{ filterRootName }} · clear
      </button>
      <span
        v-else
        class="px-1.5 py-0.5 rounded bg-surface-0/80 dark:bg-surface-800/80 text-muted-color"
      >
        hover = family tree · double-click = filter to family
      </span>
      <span
        class="px-1.5 py-0.5 rounded bg-surface-0/80 dark:bg-surface-800/80 text-muted-color"
        title="Dagster's rule, non-transitively: only a direct parent moving counts."
      >
        <span class="text-amber-700 dark:text-amber-400">changed</span> = own code moved ·
        rematerialized = only its inputs moved
      </span>
    </div>

    <div ref="viewport" class="absolute inset-0 overflow-auto">
      <div
        class="relative origin-top-left transition-transform duration-500 ease-out"
        :style="{
          width: `${layout.width}px`,
          height: `${layout.height}px`,
          transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`,
        }"
      >
        <svg class="absolute inset-0 pointer-events-none" :width="layout.width" :height="layout.height">
          <path
            v-for="edge in edges"
            :key="edge.key"
            :d="edge.d"
            fill="none"
            path-length="1"
            :class="[
              'rr-edge',
              edge.phase === 'invalidating' ? 'rr-edge-tear' : '',
              edge.phase === 'rebuilding' ? 'rr-edge-build' : '',
            ]"
            :stroke="edge.stroke"
            :stroke-width="edge.emphasis ? 2 : 1.2"
            :stroke-dasharray="edge.ghost ? '3 3' : undefined"
            :opacity="edge.opacity"
          />
        </svg>

        <div
          v-for="node in nodes"
          :key="node.assetId"
          class="absolute rounded border px-2 py-1 cursor-pointer select-none transition-[opacity,box-shadow,border-color] duration-300"
          :class="node.classes"
          :style="{
            left: `${node.x}px`,
            top: `${node.y}px`,
            width: `${NODE_WIDTH}px`,
            minHeight: `${NODE_HEIGHT}px`,
            opacity: node.opacity,
          }"
          @mouseenter="hovered = node.assetId"
          @mouseleave="hovered = null"
          @click="emit('select', node.assetId)"
          @dblclick="emit('filter', node.assetId)"
        >
          <div class="flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="node.dotClass" />
            <span class="text-[11px] font-medium truncate" :title="node.name">{{ node.name }}</span>
            <span
              v-for="agent in node.agents"
              :key="agent.agentId"
              class="ml-auto w-3.5 h-3.5 rounded-full shrink-0 border border-surface-0 dark:border-surface-900"
              :style="{ background: agent.color }"
              :title="`${agent.label} is working here`"
            />
          </div>
          <div class="flex items-center gap-1 text-[10px] text-muted-color">
            <span>{{ node.kind }}</span>
            <span v-if="node.costLabel">· {{ node.costLabel }}</span>
            <span v-if="node.author" class="ml-auto truncate">{{ node.author }}</span>
          </div>
          <div v-if="node.cause || node.pulseLabel || node.marked" class="mt-0.5 flex flex-wrap gap-1">
            <StatusBadges v-if="node.cause" :cause="node.cause" />
            <span
              v-if="node.marked"
              class="px-1 py-px rounded text-[10px] border border-primary-500 text-primary-600 dark:text-primary-400"
            >
              changed here
            </span>
            <span
              v-if="node.pulseLabel"
              class="px-1 py-px rounded text-[10px] bg-surface-200 dark:bg-surface-700 truncate max-w-full"
              :title="node.pulseLabel"
            >
              {{ node.pulseLabel }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StatusBadges from '../../components/StatusBadges.vue'
import { formatCost, resolveSlice, versionsOf } from '../../engine'
import { NODE_HEIGHT, NODE_WIDTH, familyOf, type CanvasLayout } from './layout'
import { unsyncedCauses } from './staleness'
import type { Pulse } from './usePulses'
import type { Agent, AssetId, BranchId, FlowSession, UnsyncedCause } from '../../types'

/**
 * One variant at a time, on a layout that never re-solves.
 *
 * Everything the canvas can say about an asset — state, unsynced cause, cost,
 * who is on it — is precomputed into one array, because the alternative (calling
 * engine helpers from the template) re-runs `resolveSlice` once per node per
 * render and falls over on the 150-asset fixture.
 */
const props = defineProps<{
  /** Step-filtered session: what exists right now. */
  session: FlowSession
  /** Whole session: the layout is derived from this so it never moves. */
  fullSession: FlowSession
  branchId: BranchId
  layout: CanvasLayout
  pulses: Record<AssetId, Pulse>
  selectedAssetId: AssetId | null
  filterRootId: AssetId | null
  /** Assets the selected checkpoint touched — the brushing direction railroad → canvas. */
  markedAssetIds: AssetId[]
}>()

const emit = defineEmits<{ select: [assetId: AssetId]; filter: [assetId: AssetId | null] }>()

const hovered = ref<AssetId | null>(null)
const viewport = ref<HTMLElement | null>(null)
const viewportSize = ref({ width: 800, height: 520 })

let observer: ResizeObserver | null = null
onMounted(() => {
  if (!viewport.value) return
  observer = new ResizeObserver((entries) => {
    const box = entries[0].contentRect
    viewportSize.value = { width: box.width, height: box.height }
  })
  observer.observe(viewport.value)
})
onBeforeUnmount(() => observer?.disconnect())

const slice = computed(() => resolveSlice(props.session, props.branchId))
const causes = computed(() => unsyncedCauses(props.session, props.branchId))
const marked = computed(() => new Set(props.markedAssetIds))

const highlightRoot = computed(() => hovered.value ?? props.filterRootId)
const family = computed(() =>
  highlightRoot.value && props.fullSession.assets[highlightRoot.value]
    ? familyOf(props.fullSession, highlightRoot.value)
    : null,
)

const filterFamily = computed(() =>
  props.filterRootId && props.fullSession.assets[props.filterRootId]
    ? familyOf(props.fullSession, props.filterRootId).all
    : null,
)

const filterRootName = computed(() => {
  if (!props.filterRootId) return ''
  const versions = versionsOf(props.fullSession, props.filterRootId)
  return versions[versions.length - 1]?.definition.name ?? props.filterRootId
})

const agentsByAsset = computed(() => {
  const result: Record<AssetId, Agent[]> = {}
  for (const agent of Object.values(props.session.agents)) {
    if (!agent.activeAssetId || agent.activeBranchId !== props.branchId) continue
    result[agent.activeAssetId] = result[agent.activeAssetId] ?? []
    result[agent.activeAssetId].push(agent)
  }
  return result
})

interface NodeView {
  assetId: AssetId
  x: number
  y: number
  name: string
  kind: string
  author: string
  costLabel: string
  cause: UnsyncedCause | null
  pulseLabel: string
  marked: boolean
  agents: Agent[]
  classes: string[]
  dotClass: string
  opacity: number
}

const nodes = computed<NodeView[]>(() => {
  const out: NodeView[] = []
  for (const assetId of props.layout.order) {
    const position = props.layout.nodes[assetId]
    const versions = props.session.assets[assetId]
    if (!versions?.length) continue // not yet created at this step
    if (filterFamily.value && !filterFamily.value.has(assetId)) continue

    const inSlice = Boolean(slice.value[assetId])
    const version = slice.value[assetId] ?? versions[versions.length - 1]
    const materialization = props.session.materializations[version.versionId]
    const pulse = props.pulses[assetId]
    const state = pulse ? pulseState(pulse) : (materialization?.state ?? 'never')
    const dimmed = family.value ? !family.value.all.has(assetId) : false

    out.push({
      assetId,
      x: position.x,
      y: position.y,
      name: version.definition.name,
      kind: version.definition.kind,
      author: version.authoredBy,
      costLabel: materialization ? formatCost(materialization.costSeconds) : '',
      cause: inSlice ? (causes.value[assetId] ?? null) : null,
      pulseLabel: pulse?.label ?? '',
      marked: marked.value.has(assetId),
      agents: agentsByAsset.value[assetId] ?? [],
      classes: nodeClasses(state, inSlice, assetId === props.selectedAssetId),
      dotClass: dotClass(state),
      opacity: dimmed ? 0.22 : inSlice ? 1 : 0.5,
    })
  }
  return out
})

const visibleCount = computed(() => nodes.value.length)

function pulseState(pulse: Pulse): string {
  switch (pulse.kind) {
    case 'invalidating':
      return 'invalidating'
    case 'failed':
      return 'failed'
    case 'writing':
      return 'writing'
    default:
      return 'running'
  }
}

function nodeClasses(state: string, inSlice: boolean, selected: boolean): string[] {
  const classes: string[] = ['bg-surface-0', 'dark:bg-surface-800']
  if (!inSlice) classes.push('border-dashed')
  switch (state) {
    case 'failed':
      classes.push('border-red-500', 'shadow-[0_0_0_2px_rgba(239,68,68,0.25)]')
      break
    case 'writing':
      classes.push('border-indigo-500', 'rr-node-writing')
      break
    case 'running':
      classes.push('border-amber-500', 'rr-node-running')
      break
    case 'invalidating':
      classes.push('border-surface-400', 'rr-node-invalidating')
      break
    case 'unsynced':
      classes.push('border-amber-400')
      break
    case 'never':
      classes.push('border-surface-300', 'dark:border-surface-600', 'border-dashed')
      break
    default:
      classes.push('border-surface-300', 'dark:border-surface-600')
  }
  if (selected) classes.push('ring-2', 'ring-primary-500')
  return classes
}

function dotClass(state: string): string {
  switch (state) {
    case 'failed':
      return 'bg-red-500'
    case 'writing':
      return 'bg-indigo-500'
    case 'running':
      return 'bg-amber-500'
    case 'invalidating':
      return 'bg-surface-400'
    case 'never':
      return 'bg-surface-300'
    default:
      return 'bg-emerald-500'
  }
}

interface EdgeView {
  key: string
  d: string
  stroke: string
  opacity: number
  emphasis: boolean
  ghost: boolean
  phase: 'idle' | 'invalidating' | 'rebuilding'
}

const edges = computed<EdgeView[]>(() => {
  const out: EdgeView[] = []
  const visible = new Set(nodes.value.map((node) => node.assetId))
  const branchColor = props.session.branches[props.branchId]?.color ?? '#94a3b8'

  for (const assetId of visible) {
    const inSlice = Boolean(slice.value[assetId])
    const versions = props.session.assets[assetId]
    const version = slice.value[assetId] ?? versions[versions.length - 1]
    const target = props.layout.nodes[assetId]
    const pulse = props.pulses[assetId]

    for (const dep of version.definition.deps) {
      if (!visible.has(dep)) continue
      const source = props.layout.nodes[dep]
      if (!source) continue
      const x1 = source.x + NODE_WIDTH
      const y1 = source.y + NODE_HEIGHT / 2
      const x2 = target.x
      const y2 = target.y + NODE_HEIGHT / 2
      const inFamily = !family.value || (family.value.all.has(assetId) && family.value.all.has(dep))

      out.push({
        key: `${dep}->${assetId}`,
        d: `M ${x1} ${y1} C ${x1 + 48} ${y1}, ${x2 - 48} ${y2}, ${x2} ${y2}`,
        stroke: inFamily && family.value ? branchColor : '#94a3b8',
        opacity: inFamily ? (inSlice ? 0.75 : 0.4) : 0.1,
        emphasis: Boolean(family.value) && inFamily,
        ghost: !inSlice,
        phase:
          pulse?.kind === 'invalidating'
            ? 'invalidating'
            : pulse?.kind === 'materializing'
              ? 'rebuilding'
              : 'idle',
      })
    }
  }
  return out
})

/** Filtering is a camera move, not a re-layout: coordinates are untouched. */
const camera = computed(() => {
  if (!filterFamily.value || !nodes.value.length) return { x: 0, y: 0, scale: 1 }
  const xs = nodes.value.map((node) => node.x)
  const ys = nodes.value.map((node) => node.y)
  const minX = Math.min(...xs) - 24
  const minY = Math.min(...ys) - 24
  const width = Math.max(...xs) + NODE_WIDTH + 24 - minX
  const height = Math.max(...ys) + NODE_HEIGHT + 24 - minY
  const scale = Math.min(
    1.4,
    Math.max(0.5, Math.min(viewportSize.value.width / width, viewportSize.value.height / height)),
  )
  return { x: -minX * scale, y: -minY * scale, scale }
})
</script>

<style scoped>
.rr-edge {
  transition: opacity 300ms ease;
}

/* reactlog's tear-down: the edge visibly comes apart before anything recomputes. */
.rr-edge-tear {
  stroke-dasharray: 0.02 0.03;
  animation: rr-tear 460ms linear;
}

.rr-edge-build {
  stroke-dasharray: 1;
  animation: rr-build 520ms ease-out;
}

@keyframes rr-tear {
  from {
    stroke-dashoffset: 0;
    opacity: 0.8;
  }
  to {
    stroke-dashoffset: 0.4;
    opacity: 0.2;
  }
}

@keyframes rr-build {
  from {
    stroke-dashoffset: 1;
  }
  to {
    stroke-dashoffset: 0;
  }
}

.rr-node-writing {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}

.rr-node-running {
  animation: rr-throb 700ms ease-in-out infinite;
}

.rr-node-invalidating {
  animation: rr-fade 460ms ease-in-out;
}

@keyframes rr-throb {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.35);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.2);
  }
}

@keyframes rr-fade {
  0% {
    filter: none;
  }
  60% {
    filter: grayscale(1) opacity(0.45);
  }
  100% {
    filter: none;
  }
}
</style>
