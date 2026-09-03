import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { LineageNodeData } from '../lineage.interface'
import LineageArea from '../LineageArea.vue'

const harness = vi.hoisted(() => ({
  store: null as null | {
    initialNodes: unknown[]
    initialEdges: unknown[]
    setDetailedArtifact: ReturnType<typeof vi.fn>
    setReplaceableArtifactId: ReturnType<typeof vi.fn>
    unlinkArtifact: ReturnType<typeof vi.fn>
  },
}))
const fitView = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))

vi.mock('@/stores/lineage', async () => {
  const { reactive } = await import('vue')
  harness.store = reactive({
    initialNodes: [] as unknown[],
    initialEdges: [] as unknown[],
    setDetailedArtifact: vi.fn(),
    setReplaceableArtifactId: vi.fn(),
    unlinkArtifact: vi.fn(),
  })
  return { useLineageStore: () => harness.store }
})
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useConfirm: () => ({ require: vi.fn() }) }
})
vi.mock('@vue-flow/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@vue-flow/core')>()
  return { ...actual, useVueFlow: () => ({ fitView }) }
})

const VueFlowStub = defineComponent({
  name: 'VueFlow',
  props: {
    deleteKeyCode: { type: Array, default: () => [] },
    nodesDeletable: { type: Boolean, default: true },
  },
  emits: ['nodeClick'],
  template: '<div />',
})

function nodeData(isDeleted = false): LineageNodeData {
  return {
    nodeId: 'node',
    artifactId: isDeleted ? null : 'artifact',
    collectionId: isDeleted ? null : 'collection',
    collectionName: 'Collection',
    isDeleted,
    type: ArtifactTypeEnum.model,
    title: 'Model',
    variant: isDeleted ? 'disabled' : 'default',
    data: null,
  }
}

function mountArea() {
  return shallowMount(LineageArea, {
    global: {
      stubs: {
        VueFlow: VueFlowStub,
        Background: true,
        LineageNode: true,
        CustomArrowEdge: true,
      },
    },
  })
}

describe('LineageArea', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (!harness.store) throw new Error('Store harness was not initialized')
    harness.store.initialNodes = []
    harness.store.initialEdges = []
  })

  it('lets both delete keys remove edges but never nodes', () => {
    const flow = mountArea().findComponent(VueFlowStub)

    expect(flow.props('deleteKeyCode')).toEqual(['Backspace', 'Delete'])
    expect(flow.props('nodesDeletable')).toBe(false)
  })

  it('opens details for live nodes and ignores deleted nodes', async () => {
    const flow = mountArea().findComponent(VueFlowStub)
    const live = nodeData()
    if (!harness.store) throw new Error('Store harness was not initialized')

    flow.vm.$emit('nodeClick', { node: { data: live }, event: new MouseEvent('click') })
    await flow.vm.$nextTick()
    expect(harness.store.setDetailedArtifact).toHaveBeenCalledWith(live)

    harness.store.setDetailedArtifact.mockClear()
    flow.vm.$emit('nodeClick', {
      node: { data: nodeData(true) },
      event: new MouseEvent('click'),
    })
    await flow.vm.$nextTick()
    expect(harness.store.setDetailedArtifact).not.toHaveBeenCalled()
  })

  it('recenters the canvas when a newly loaded graph replaces the nodes', async () => {
    mountArea()
    if (!harness.store) throw new Error('Store harness was not initialized')

    harness.store.initialNodes = [{ id: 'new-focal-node' }]
    await flushPromises()

    expect(fitView).toHaveBeenCalledWith({ padding: 0.2 })
  })
})
