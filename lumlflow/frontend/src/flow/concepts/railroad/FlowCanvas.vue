<template>
  <VueFlow
    :nodes="flowNodes"
    :edges="flowEdges"
    :nodes-draggable="false"
    :nodes-connectable="false"
    :min-zoom="0.08"
    :max-zoom="1.4"
    fit-view-on-init
    class="h-full"
    @node-click="onNodeClick"
    @node-mouse-enter="hovered = $event.node.id"
    @node-mouse-leave="hovered = null"
  >
    <template #node-asset="{ data }">
      <AssetFlowNode :data="data" />
    </template>
    <Background :gap="28" pattern-color="var(--p-surface-300)" />
    <Controls :show-interactive="false" position="bottom-right" />
  </VueFlow>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import AssetFlowNode from './AssetFlowNode.vue'
import { CARD_HEIGHT, CARD_WIDTH, type FlowLayout } from './flowLayout'
import { resolveSlice, unsyncedCause } from '../../engine'
import type { AssetId, BranchId, FlowSession } from '../../types'

const props = defineProps<{
  session: FlowSession
  branchId: BranchId
  layout: FlowLayout
  selectedAssetId: AssetId | null
  phases: Record<AssetId, string>
}>()

const emit = defineEmits<{ select: [AssetId]; expand: [AssetId] }>()

const hovered = ref<AssetId | null>(null)

const slice = computed(() => resolveSlice(props.session, props.branchId))

/**
 * Hovering a card lifts its whole lineage and dims everything else — reactlog's
 * family highlight. It answers "what does this read, and what breaks if I change
 * it" in place, which is why there is no separate dependency panel.
 */
const family = computed<Set<AssetId> | null>(() => {
  if (!hovered.value || !slice.value[hovered.value]) return null
  const found = new Set<AssetId>([hovered.value])

  const addAncestors = (assetId: AssetId): void => {
    for (const dep of slice.value[assetId]?.definition.deps ?? []) {
      if (slice.value[dep] && !found.has(dep)) {
        found.add(dep)
        addAncestors(dep)
      }
    }
  }
  addAncestors(hovered.value)

  let grew = true
  while (grew) {
    grew = false
    for (const [assetId, version] of Object.entries(slice.value)) {
      if (found.has(assetId)) continue
      if (version.definition.deps.some((dep) => found.has(dep))) {
        found.add(assetId)
        grew = true
      }
    }
  }
  return found
})

const flowNodes = computed(() =>
  Object.values(props.layout.nodes)
    .filter((node) => slice.value[node.assetId])
    .map((node) => ({
      id: node.assetId,
      type: 'asset',
      position: { x: node.x, y: node.y },
      style: { width: `${CARD_WIDTH}px`, height: `${CARD_HEIGHT}px` },
      data: {
        session: props.session,
        version: slice.value[node.assetId],
        cause: unsyncedCause(props.session, props.branchId, node.assetId),
        selected: node.assetId === props.selectedAssetId,
        dimmed: family.value ? !family.value.has(node.assetId) : false,
        phase: props.phases[node.assetId] ?? null,
        onExpand: () => emit('expand', node.assetId),
      },
    })),
)

const flowEdges = computed(() =>
  Object.entries(slice.value).flatMap(([assetId, version]) =>
    version.definition.deps
      .filter((depId) => slice.value[depId] && props.layout.nodes[depId])
      .map((depId) => {
        const lit = Boolean(family.value?.has(assetId) && family.value?.has(depId))
        return {
          id: `${depId}->${assetId}`,
          source: depId,
          target: assetId,
          type: 'smoothstep',
          animated: props.phases[assetId] === 'invalidating',
          style: {
            strokeWidth: lit ? 2 : 1.5,
            opacity: family.value ? (lit ? 1 : 0.12) : 0.55,
          },
        }
      }),
  ),
)

const onNodeClick = (event: { node: { id: string } }): void => {
  emit('select', event.node.id)
}
</script>

<style>
.vue-flow__node-asset {
  cursor: pointer;
}
</style>
