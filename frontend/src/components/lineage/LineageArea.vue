<template>
  <VueFlow
    :nodes="lineageStore.initialNodes"
    :edges="lineageStore.initialEdges"
    class="area"
    :default-viewport="{ zoom: 1 }"
    :min-zoom="0.2"
    :max-zoom="4"
    :delete-key-code="['Backspace', 'Delete']"
    :nodes-deletable="false"
    @node-click="onNodeClick"
  >
    <template #node-lineage="props">
      <LineageNode
        :artifactType="props.data.type"
        :title="props.data.title"
        :collectionName="props.data.collectionName"
        :variant="props.data.variant"
        :is-deleted="props.data.isDeleted"
        :deployments="props.data.deployments || []"
        :tracks="props.data.tracks || []"
        @replace="replaceNode(props.id)"
        @unlink="unlinkNode(props.id)"
      />
    </template>
    <template #edge-custom="edgeProps">
      <CustomArrowEdge v-bind="edgeProps" />
    </template>
    <Background pattern-color="var(--dots-color)" />
  </VueFlow>
</template>

<script setup lang="ts">
import { Background } from '@vue-flow/background'
import { VueFlow, useVueFlow, type NodeMouseEvent } from '@vue-flow/core'
import { useLineageStore } from '@/stores/lineage'
import { unlinkArtifactConfirmOptions } from '@/lib/primevue/data/confirm'
import { useConfirm } from 'primevue'
import { nextTick, watch } from 'vue'
import type { LineageNodeData } from './lineage.interface'
import LineageNode from './LineageNode.vue'
import CustomArrowEdge from '../ui/vue-flow/CustomArrowEdge.vue'

const confirm = useConfirm()

const lineageStore = useLineageStore()
const { fitView } = useVueFlow()

function replaceNode(id: string) {
  lineageStore.setReplaceableArtifactId(id)
}

function unlinkNode(id: string) {
  const accept = () => {
    lineageStore.unlinkArtifact(id)
  }
  confirm.require(unlinkArtifactConfirmOptions(accept))
}

function onNodeClick({ node }: NodeMouseEvent): void {
  const data = node.data as LineageNodeData
  if (data.isDeleted) return
  lineageStore.setDetailedArtifact(data)
}

watch(
  () => lineageStore.initialNodes,
  async (nodes) => {
    if (nodes.length === 0) return
    await nextTick()
    await fitView({ padding: 0.2 })
  },
  { immediate: true, flush: 'post' },
)
</script>

<style scoped>
.area {
  height: 100%;
  width: 100%;
  --dots-color: #cdcddb;
}
[data-theme='dark'] .area {
  --dots-color: rgba(69, 69, 74, 0.7);
}
:deep(.vue-flow__node-lineage) {
  padding: 0;
}
:deep(.vue-flow__node-lineage:has(.model.main)) {
  background-color: var(--p-button-outlined-secondary-active-background);
}
:deep(.vue-flow__node-lineage:has(.experiment.main)) {
  background-color: var(--p-button-outlined-info-hover-background);
}
:deep(.vue-flow__node-lineage:has(.dataset.main)) {
  background-color: var(--p-button-text-warn-hover-background);
}
:deep(.vue-flow__node-lineage:has(.disabled)) {
  opacity: 0.6;
  border-style: dashed;
}
:deep(.vue-flow__node-lineage:has(.disabled):hover) {
  border-color: var(--p-content-border-color);
}
:deep(.vue-flow__node-lineage.selected:has(.disabled)) {
  border-color: var(--p-content-border-color);
}
</style>
