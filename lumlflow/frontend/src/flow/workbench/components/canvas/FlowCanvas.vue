<template>
  <VueFlow
    :nodes="nodes"
    :edges="edges"
    :nodes-draggable="false"
    :nodes-connectable="false"
    :min-zoom="0.12"
    :max-zoom="1.25"
    fit-view-on-init
    class="h-full"
    @node-click="onNodeClick"
    @pane-ready="onPaneReady"
  >
    <template #node-cell="{ data }">
      <CellFlowNode :data="data" />
    </template>
    <Background :gap="26" pattern-color="var(--p-surface-300)" />
    <Controls :show-interactive="false" position="bottom-right" />
  </VueFlow>
</template>

<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { VueFlow, type Edge, type Node, type VueFlowStore } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import { sliceEdges } from '../../model/registry'
import type { FlowCell, ParamValue, Preflight } from '../../model/types'
import CellFlowNode, { type CellNodeData } from './CellFlowNode.vue'
import { layoutSlice, NODE_WIDTH } from './canvasLayout'

/**
 * The canvas view: the branch slice as a left-to-right DAG whose edges are the
 * declared consumes wiring — the graph on screen is the graph the scheduler
 * runs. Nodes host the same CellCard the notebook uses, at canvas density.
 */
const props = defineProps<{
  cells: FlowCell[]
  branch: string
  selectedSlug: string | null
  tintedSlugs: Set<string>
  preflights: Record<string, Preflight | undefined>
}>()

const emit = defineEmits<{
  select: [slug: string]
  expand: [slug: string]
  run: [slug: string, payload: { force: boolean }]
  stop: [slug: string]
  rename: [slug: string]
  delete: [slug: string]
  duplicate: [slug: string]
  navigate: [payload: { view: 'canvas' | 'notebook'; slug: string }]
  'send-to-agent': [slug: string, payload: string]
  'resolve-conflict': [slug: string, choice: 'overwrite' | 'fork']
  edit: [slug: string, payload: { source: string }]
  'edit-params': [slug: string, params: Record<string, ParamValue>]
}>()

const positions = computed(() => layoutSlice(props.cells))

const nodes = computed<Node<CellNodeData>[]>(() =>
  props.cells.map((cell) => ({
    id: cell.slug,
    type: 'cell',
    position: positions.value[cell.slug] ?? { x: 0, y: 0 },
    style: { width: `${NODE_WIDTH}px` },
    data: {
      cell,
      branch: props.branch,
      selected: cell.slug === props.selectedSlug,
      tinted: props.tintedSlugs.has(cell.slug),
      preflight: props.preflights[cell.slug],
      events: {
        expand: () => emit('expand', cell.slug),
        run: (payload) => emit('run', cell.slug, payload),
        stop: () => emit('stop', cell.slug),
        rename: () => emit('rename', cell.slug),
        remove: () => emit('delete', cell.slug),
        duplicate: () => emit('duplicate', cell.slug),
        navigate: (payload) => emit('navigate', payload),
        sendToAgent: (payload) => emit('send-to-agent', cell.slug, payload),
        resolveConflict: (choice) => emit('resolve-conflict', cell.slug, choice),
        edit: (payload) => emit('edit', cell.slug, payload),
        editParams: (params) => emit('edit-params', cell.slug, params),
      },
    },
  })),
)

const edges = computed<Edge[]>(() => {
  const bySlug = new Map(props.cells.map((cell) => [cell.slug, cell]))
  return sliceEdges(props.cells).map(({ from, to }) => ({
    id: `${from}->${to}`,
    source: from,
    target: to,
    type: 'smoothstep',
    animated: bySlug.get(to)?.status === 'running',
    style: { strokeWidth: 1.5, opacity: 0.55 },
  }))
})

// --- focus the selected node -----------------------------------------------

const instance = shallowRef<VueFlowStore | null>(null)

function focusSelected(animate: boolean): void {
  const slug = props.selectedSlug
  const store = instance.value
  if (!slug || !store || !props.cells.some((cell) => cell.slug === slug)) return
  void store
    .fitView({ nodes: [slug], padding: 0.4, maxZoom: 0.9, duration: animate ? 400 : 0 })
    .catch(() => undefined)
}

function onPaneReady(store: VueFlowStore): void {
  instance.value = store
  focusSelected(false)
}

watch(
  () => props.selectedSlug,
  () => focusSelected(true),
)

function onNodeClick(event: { node: { id: string } }): void {
  emit('select', event.node.id)
}
</script>

<style>
.vue-flow__node-cell {
  cursor: pointer;
}
</style>
