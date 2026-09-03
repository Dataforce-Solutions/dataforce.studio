import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import type { LineageGraph } from '@/lib/api/lineage/interfaces'

const apiMocks = vi.hoisted(() => ({
  getGraph: vi.fn(),
  applyChanges: vi.fn(),
}))

const route = vi.hoisted(() => ({
  params: {
    organizationId: 'org',
    id: 'orbit',
    collectionId: 'models',
    artifactId: 'model',
  },
}))

const artifacts = vi.hoisted(() => ({ currentArtifact: null as Artifact | null }))

const flowHarness = vi.hoisted(() => ({
  current: null as null | {
    nodes: { value: unknown[] }
    edges: { value: unknown[] }
    connectHandlers: ((connection: { source: string; target: string }) => void)[]
    nodeChangeHandlers: ((changes: { type: string }[]) => void)[]
    edgeChangeHandlers: ((changes: { type: string }[]) => void)[]
  },
}))

vi.mock('@/lib/api', () => ({ api: { lineage: apiMocks } }))
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/stores/artifacts', () => ({ useArtifactsStore: () => artifacts }))
vi.mock('@vue-flow/core', async () => {
  const { ref } = await import('vue')
  const nodes = ref<unknown[]>([])
  const edges = ref<unknown[]>([])
  const connectHandlers: ((connection: { source: string; target: string }) => void)[] = []
  const nodeChangeHandlers: ((changes: { type: string }[]) => void)[] = []
  const edgeChangeHandlers: ((changes: { type: string }[]) => void)[] = []
  flowHarness.current = {
    nodes,
    edges,
    connectHandlers,
    nodeChangeHandlers,
    edgeChangeHandlers,
  }

  return {
    useVueFlow: () => ({
      nodes,
      edges,
      setNodes: (value: unknown[]) => {
        nodes.value = value
      },
      setEdges: (value: unknown[]) => {
        edges.value = value
      },
      addEdges: (value: Record<string, unknown>) => {
        edges.value = [...edges.value, { id: `draft-${edges.value.length}`, ...value }]
        edgeChangeHandlers.forEach((handler) => handler([{ type: 'add' }]))
      },
      onConnect: (handler: (connection: { source: string; target: string }) => void) => {
        connectHandlers.push(handler)
      },
      onNodesChange: (handler: (changes: { type: string }[]) => void) => {
        nodeChangeHandlers.push(handler)
      },
      onEdgesChange: (handler: (changes: { type: string }[]) => void) => {
        edgeChangeHandlers.push(handler)
      },
    }),
  }
})

import { useLineageStore } from '..'

function artifact(id: string, collectionId = 'models', collectionName = 'Models'): Artifact {
  return {
    id,
    name: id,
    collection_id: collectionId,
    collection_name: collectionName,
    type: ArtifactTypeEnum.model,
    status: ArtifactStatusEnum.uploaded,
    deployments: [],
    tracks: [],
  } as unknown as Artifact
}

function emptyGraph(truncated = false, depth = 2): LineageGraph {
  return {
    nodes: [],
    edges: [],
    focal_artifact_id: 'model',
    depth,
    truncated,
  }
}

function connectedGraph(): LineageGraph {
  return {
    focal_artifact_id: 'model',
    depth: 2,
    truncated: false,
    nodes: [
      {
        id: 'node-model',
        artifact_id: 'model',
        type: ArtifactTypeEnum.model,
        name: 'model',
        collection_name: 'Models',
        x: 0,
        y: 0,
        is_deleted: false,
        data: artifact('model'),
      },
      {
        id: 'node-output',
        artifact_id: 'output',
        type: ArtifactTypeEnum.model,
        name: 'output',
        collection_name: 'Models',
        x: 300,
        y: 50,
        is_deleted: false,
        data: artifact('output'),
      },
    ],
    edges: [
      {
        id: 'edge-output',
        source: 'node-model',
        target: 'node-output',
        created_by_user: 'Ada',
        created_via: 'ui',
        created_at: '2026-01-01T00:00:00Z',
      },
    ],
  }
}

function flow() {
  if (!flowHarness.current) throw new Error('Flow harness was not initialized')
  return flowHarness.current
}

describe('lineage store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.getGraph.mockReset()
    apiMocks.applyChanges.mockReset()
    artifacts.currentArtifact = {
      ...artifact('model'),
      collection: { id: 'models', name: 'Models' },
    } as Artifact
    flow().nodes.value = []
    flow().edges.value = []
    flow().connectHandlers.length = 0
    flow().nodeChangeHandlers.length = 0
    flow().edgeChangeHandlers.length = 0
  })

  it('loads the graph at the selected depth and clears edit history', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph(true, 3))
    const store = useLineageStore()
    store.setDepth(3)

    await store.load()
    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'))
    expect(store.history).toHaveLength(1)

    await store.load()

    expect(apiMocks.getGraph).toHaveBeenCalledWith('org', 'orbit', 'model', 3)
    expect(apiMocks.getGraph).toHaveBeenCalledTimes(2)
    expect(store.initialNodes.map((node) => node.id)).toEqual(['artifact:model'])
    expect(store.truncated).toBe(true)
    expect(store.history).toEqual([])
  })

  it('rejects depths outside the API range', () => {
    const store = useLineageStore()

    expect(() => store.setDepth(0)).toThrow(RangeError)
    expect(() => store.setDepth(6)).toThrow(RangeError)
  })

  it('keeps edits and canvas state when a batch save fails', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    apiMocks.applyChanges.mockRejectedValue(new Error('conflict'))
    const store = useLineageStore()
    await store.load()

    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'), { x: -260, y: 0 })
    expect(store.unconnectedArtifactsCount).toBe(1)
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'artifact:model' })
    expect(store.usedArtifactsIds).toEqual(['model', 'dataset'])
    expect(store.unconnectedArtifactsCount).toBe(0)

    await expect(store.save()).rejects.toThrow('conflict')
    expect(store.history).toHaveLength(2)
    expect(flow().nodes.value).toHaveLength(2)
    expect(flow().edges.value).toHaveLength(1)
  })

  it('saves one diff batch and reloads the graph on success', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    apiMocks.applyChanges.mockResolvedValue({ created: [], deleted: [] })
    const store = useLineageStore()
    await store.load()

    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'), { x: -260, y: 0 })
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'artifact:model' })
    await store.save()

    expect(apiMocks.applyChanges).toHaveBeenCalledWith(
      'org',
      'orbit',
      expect.objectContaining({
        create: [
          {
            source: { artifact_id: 'dataset' },
            target: { artifact_id: 'model' },
          },
        ],
        delete: [],
      }),
    )
    expect(apiMocks.getGraph).toHaveBeenCalledTimes(2)
    expect(store.history).toEqual([])
  })

  it('records moving, reset positions, unlink, and undo as edits', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    const output = flow().nodes.value.find(
      (node) => (node as { id: string }).id === 'node-output',
    ) as { position: { x: number; y: number } }
    output.position = { x: 400, y: 80 }
    flow().nodeChangeHandlers[0]([{ type: 'position' }])
    expect(store.history).toHaveLength(1)

    store.resetPositions()
    expect(store.history).toHaveLength(2)
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 320, y: 0 })

    store.goBack()
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 400, y: 80 })

    store.unlinkArtifact('node-output')
    expect(flow().nodes.value).toHaveLength(1)
    expect(flow().edges.value).toEqual([])
    expect(store.history).toHaveLength(2)
  })

  it('treats movement as an edit and undo restores the loaded position', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    const output = flow().nodes.value.find(
      (node) => (node as { id: string }).id === 'node-output',
    ) as { position: { x: number; y: number } }
    output.position = { x: 400, y: 80 }
    flow().nodeChangeHandlers[0]([{ type: 'position' }])

    expect(store.history).toHaveLength(1)

    store.goBack()

    expect(store.history).toEqual([])
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 300, y: 50 })
  })

  it('resets saved positions with no prior edit and undo restores them', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    store.resetPositions()

    expect(store.history).toHaveLength(1)
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 320, y: 0 })

    store.goBack()
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 300, y: 50 })
  })
})
