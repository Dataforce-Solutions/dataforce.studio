import type { HistorySnapshot, LineageCanvasNode } from '@/components/lineage/lineage.interface'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { api } from '@/lib/api'
import { useArtifactsStore } from '@/stores/artifacts'
import {
  useVueFlow,
  type Edge,
  type EdgeChange,
  type NodeChange,
  type XYPosition,
} from '@vue-flow/core'
import { defineStore } from 'pinia'
import { computed, nextTick, onScopeDispose, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import { buildLineageBatch } from './diff'
import { layoutLineageNodes } from './layout'
import {
  artifactCanvasNodeId,
  artifactNodeData,
  mapGraphToCanvas,
  type LineageFocalArtifact,
} from './mapping'
import { countUnconnectedArtifacts, isValidLineageConnection } from './validation'

const STATE_CHANGE_DEBOUNCE_MS = 200

function cloneState(state: HistorySnapshot): HistorySnapshot {
  return JSON.parse(JSON.stringify(state)) as HistorySnapshot
}

export const useLineageStore = defineStore('lineage', () => {
  const { nodes, edges, addEdges, onConnect, onNodesChange, onEdgesChange, setNodes, setEdges } =
    useVueFlow()
  const route = useRoute()
  const artifactsStore = useArtifactsStore()

  const currentArtifactId = computed(() => String(route.params.artifactId))
  const creatorVisible = ref(false)
  const detailedArtifact = ref<Artifact | null>(null)
  const initialNodes = shallowRef<LineageCanvasNode[]>([])
  const initialEdges = shallowRef<Edge[]>([])
  const loadedState = shallowRef<HistorySnapshot>({ nodes: [], edges: [] })
  const replaceableArtifactId = ref<string | null>(null)
  const history = shallowRef<HistorySnapshot[]>([])
  const depth = ref(2)
  const truncated = ref(false)
  const isLoading = ref(false)

  let stableState: HistorySnapshot = { nodes: [], edges: [] }
  let historyWindowOpen = false
  let historyTimer: ReturnType<typeof setTimeout> | null = null
  let isRestoring = false
  let latestLoad = 0

  function snapshot(): HistorySnapshot {
    return cloneState({
      nodes: nodes.value as unknown as LineageCanvasNode[],
      edges: edges.value,
    })
  }

  function closeHistoryWindow(): void {
    if (historyTimer) clearTimeout(historyTimer)
    historyTimer = null
    if (!historyWindowOpen) return
    stableState = snapshot()
    historyWindowOpen = false
  }

  function recordFlowChange(): void {
    if (isRestoring) return
    if (!historyWindowOpen) {
      history.value = [...history.value, cloneState(stableState)]
      historyWindowOpen = true
    }
    if (historyTimer) clearTimeout(historyTimer)
    historyTimer = setTimeout(closeHistoryWindow, STATE_CHANGE_DEBOUNCE_MS)
  }

  function replaceCanvasWithEdit(state: HistorySnapshot): void {
    closeHistoryWindow()
    const previous = snapshot()
    const nextState = cloneState(state)
    isRestoring = true
    setNodes(nextState.nodes)
    setEdges(nextState.edges)
    history.value = [...history.value, previous]
    stableState = snapshot()
    isRestoring = false
  }

  function replaceCanvasWithoutHistory(state: HistorySnapshot): void {
    closeHistoryWindow()
    const nextState = cloneState(state)
    isRestoring = true
    setNodes(nextState.nodes)
    setEdges(nextState.edges)
    initialNodes.value = cloneState(nextState).nodes
    initialEdges.value = cloneState(nextState).edges
    loadedState.value = cloneState(nextState)
    history.value = []
    stableState = snapshot()
    isRestoring = false
  }

  function currentFocalArtifact(): LineageFocalArtifact {
    const artifact = artifactsStore.currentArtifact
    if (!artifact) throw new Error('Current artifact does not exist')

    const detailed = artifact as Artifact & {
      collection?: { id: string; name: string }
    }
    return {
      ...artifact,
      collection: detailed.collection ?? {
        id: artifact.collection_id,
        name: artifact.collection_name,
      },
    }
  }

  function requestInfo(): { organizationId: string; orbitId: string; artifactId: string } {
    if (typeof route.params.organizationId !== 'string') {
      throw new Error('Current organization not found')
    }
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    if (typeof route.params.artifactId !== 'string') throw new Error('Artifact was not found')
    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
      artifactId: route.params.artifactId,
    }
  }

  async function load(): Promise<void> {
    if (!Number.isInteger(depth.value) || depth.value < 1 || depth.value > 5) {
      throw new RangeError('Lineage depth must be between 1 and 5')
    }

    const loadId = ++latestLoad
    const { organizationId, orbitId, artifactId } = requestInfo()
    const focalArtifact = currentFocalArtifact()
    isLoading.value = true
    try {
      const graph = await api.lineage.getGraph(organizationId, orbitId, artifactId, depth.value)
      if (loadId !== latestLoad) return
      replaceCanvasWithoutHistory(mapGraphToCanvas(graph, focalArtifact))
      truncated.value = graph.truncated
      depth.value = graph.depth
    } finally {
      if (loadId === latestLoad) isLoading.value = false
    }
  }

  function setDepth(value: number): void {
    if (!Number.isInteger(value) || value < 1 || value > 5) {
      throw new RangeError('Lineage depth must be between 1 and 5')
    }
    depth.value = value
  }

  function goBack(): void {
    closeHistoryWindow()
    const state = history.value[history.value.length - 1]
    if (!state) return

    history.value = history.value.slice(0, -1)
    isRestoring = true
    const previous = cloneState(state)
    setNodes(previous.nodes)
    setEdges(previous.edges)
    stableState = snapshot()
    void nextTick(() => {
      isRestoring = false
    })
  }

  const usedArtifactsIds = computed(() => {
    const ids = (nodes.value as unknown as LineageCanvasNode[])
      .map((node) => node.data.artifactId)
      .filter((id): id is string => id !== null)
    return [...new Set(ids)]
  })

  const unconnectedArtifactsCount = computed(() =>
    countUnconnectedArtifacts(nodes.value as unknown as LineageCanvasNode[], edges.value),
  )

  const hasEdits = computed(() => history.value.length > 0)

  function setCreatorVisible(value: boolean): void {
    creatorVisible.value = value
  }

  function setDetailedArtifact(artifact: Artifact | null): void {
    detailedArtifact.value = artifact
  }

  function addArtifact(artifact: Artifact, position: XYPosition = { x: 20, y: 20 }): void {
    if (usedArtifactsIds.value.includes(artifact.id)) return
    const state = snapshot()
    state.nodes.push({
      id: artifactCanvasNodeId(artifact.id),
      type: 'lineage',
      position,
      data: artifactNodeData(artifact, {
        id: artifact.collection_id,
        name: artifact.collection_name,
      }),
    })
    replaceCanvasWithEdit(state)
  }

  function replaceArtifact(artifact: Artifact): void {
    const oldId = replaceableArtifactId.value
    if (!oldId || usedArtifactsIds.value.includes(artifact.id)) return
    const state = snapshot()
    const nodeToReplace = state.nodes.find((node) => node.id === oldId)
    if (!nodeToReplace || nodeToReplace.data.variant === 'main') return

    const newId = artifactCanvasNodeId(artifact.id)
    state.nodes = state.nodes.map((node) =>
      node.id === oldId
        ? {
            ...node,
            id: newId,
            connectable: true,
            data: artifactNodeData(artifact, {
              id: artifact.collection_id,
              name: artifact.collection_name,
            }),
          }
        : node,
    )
    state.edges = state.edges.map((edge) => ({
      ...edge,
      source: edge.source === oldId ? newId : edge.source,
      target: edge.target === oldId ? newId : edge.target,
    }))
    replaceCanvasWithEdit(state)
  }

  function unlinkArtifact(artifactId: string): void {
    const state = snapshot()
    const node = state.nodes.find((candidate) => candidate.id === artifactId)
    if (!node || node.data.variant === 'main') return
    replaceCanvasWithEdit({
      nodes: state.nodes.filter((candidate) => candidate.id !== artifactId),
      edges: state.edges.filter((edge) => edge.source !== artifactId && edge.target !== artifactId),
    })
  }

  function setReplaceableArtifactId(artifactId: string | null): void {
    replaceableArtifactId.value = artifactId
  }

  function resetPositions(): void {
    const state = snapshot()
    if (state.nodes.length === 0) return
    const focalNode = state.nodes.find((node) => node.data.variant === 'main') ?? state.nodes[0]
    replaceCanvasWithEdit({
      nodes: layoutLineageNodes(state.nodes, state.edges, focalNode.id),
      edges: state.edges,
    })
  }

  async function save(): Promise<void> {
    closeHistoryWindow()
    if (history.value.length === 0 || unconnectedArtifactsCount.value > 0) return

    const { organizationId, orbitId } = requestInfo()
    const changes = buildLineageBatch(loadedState.value, snapshot())
    await api.lineage.applyChanges(organizationId, orbitId, changes)
    await load()
  }

  onConnect((connection) => {
    if (
      !isValidLineageConnection(
        connection,
        nodes.value as unknown as LineageCanvasNode[],
        edges.value,
      )
    ) {
      return
    }
    addEdges({ ...connection, type: 'custom' })
  })

  onNodesChange((changes: NodeChange[]) => {
    if (changes.some((change) => ['add', 'remove', 'position'].includes(change.type))) {
      recordFlowChange()
    }
  })

  onEdgesChange((changes: EdgeChange[]) => {
    if (changes.some((change) => change.type === 'add' || change.type === 'remove')) {
      recordFlowChange()
    }
  })

  onScopeDispose(() => {
    if (historyTimer) clearTimeout(historyTimer)
  })

  return {
    creatorVisible,
    setCreatorVisible,
    detailedArtifact,
    setDetailedArtifact,
    addArtifact,
    initialNodes,
    initialEdges,
    unlinkArtifact,
    usedArtifactsIds,
    replaceableArtifactId,
    setReplaceableArtifactId,
    replaceArtifact,
    history,
    hasEdits,
    unconnectedArtifactsCount,
    depth,
    setDepth,
    truncated,
    isLoading,
    currentArtifactId,
    load,
    goBack,
    resetPositions,
    save,
  }
})
