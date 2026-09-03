import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ConfirmationOptions } from 'primevue/confirmationoptions'
import LineageView from '../LineageView.vue'

const harness = vi.hoisted(() => {
  const lineage = {
    detailedArtifact: null,
    hasEdits: false,
    depth: 2,
    load: vi.fn().mockResolvedValue(undefined),
    discardChanges: vi.fn(),
    setDetailedArtifact: vi.fn(),
    setDepth: vi.fn(),
  }
  return {
    lineage,
    artifacts: null as { currentArtifact: { id: string } | null } | null,
    route: null as { params: { artifactId: string } } | null,
    leaveGuard: null as (() => Promise<boolean>) | null,
    updateGuard: null as (() => Promise<boolean>) | null,
    confirmRequire: vi.fn(),
    toastAdd: vi.fn(),
  }
})

vi.mock('@/stores/lineage', () => ({ useLineageStore: () => harness.lineage }))
vi.mock('@/stores/artifacts', async () => {
  const { reactive } = await import('vue')
  harness.artifacts = reactive({ currentArtifact: { id: 'artifact' } })
  return { useArtifactsStore: () => harness.artifacts }
})
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  const { reactive } = await import('vue')
  harness.route = { params: reactive({ artifactId: 'artifact' }) }
  return {
    ...actual,
    useRoute: () => harness.route,
    onBeforeRouteLeave: (guard: () => Promise<boolean>) => {
      harness.leaveGuard = guard
    },
    onBeforeRouteUpdate: (guard: () => Promise<boolean>) => {
      harness.updateGuard = guard
    },
  }
})
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return {
    ...actual,
    useConfirm: () => ({ require: harness.confirmRequire }),
    useToast: () => ({ add: harness.toastAdd }),
  }
})

const LineageWrapperStub = defineComponent({
  name: 'LineageWrapper',
  emits: ['depthChange'],
  template: '<div />',
})

function mountView() {
  return shallowMount(LineageView, {
    global: {
      stubs: {
        LineageWrapper: LineageWrapperStub,
        LinkCreator: true,
        ReplaceArtifactModal: true,
        LineageArtifactDetails: true,
        Teleport: true,
      },
    },
  })
}

function latestConfirmation(): ConfirmationOptions {
  const options = harness.confirmRequire.mock.calls.at(-1)?.[0] as ConfirmationOptions | undefined
  if (!options) throw new Error('Confirmation was not requested')
  return options
}

describe('LineageView', () => {
  let wrapper: ReturnType<typeof mountView> | null = null

  beforeEach(() => {
    if (!harness.route || !harness.artifacts) throw new Error('Harness was not initialized')
    harness.route.params.artifactId = 'artifact'
    harness.artifacts.currentArtifact = { id: 'artifact' }
    harness.lineage.detailedArtifact = null
    harness.lineage.hasEdits = false
    harness.lineage.depth = 2
    harness.lineage.load.mockReset().mockResolvedValue(undefined)
    harness.lineage.discardChanges.mockReset().mockImplementation(() => {
      harness.lineage.hasEdits = false
    })
    harness.lineage.setDetailedArtifact.mockReset()
    harness.lineage.setDepth.mockReset().mockImplementation((depth: number) => {
      harness.lineage.depth = depth
    })
    harness.confirmRequire.mockReset()
    harness.toastAdd.mockReset()
    harness.leaveGuard = null
    harness.updateGuard = null
  })

  afterEach(() => wrapper?.unmount())

  it('loads on open once the route and current artifact match', async () => {
    wrapper = mountView()
    await flushPromises()

    expect(harness.lineage.load).toHaveBeenCalledOnce()
    expect(harness.leaveGuard).not.toBeNull()
    expect(harness.updateGuard).not.toBeNull()
  })

  it('reloads after the route and current focal artifact change', async () => {
    wrapper = mountView()
    await flushPromises()
    harness.lineage.load.mockClear()
    if (!harness.route || !harness.artifacts) throw new Error('Harness was not initialized')

    harness.route.params.artifactId = 'next-artifact'
    await flushPromises()
    expect(harness.lineage.load).not.toHaveBeenCalled()

    harness.artifacts.currentArtifact = { id: 'next-artifact' }
    await flushPromises()

    expect(harness.lineage.setDetailedArtifact).toHaveBeenCalledWith(null)
    expect(harness.lineage.load).toHaveBeenCalledOnce()
  })

  it('blocks navigation until unsaved changes are explicitly discarded', async () => {
    wrapper = mountView()
    await flushPromises()
    harness.lineage.hasEdits = true

    const rejectedNavigation = harness.leaveGuard?.()
    latestConfirmation().reject?.()
    await expect(rejectedNavigation).resolves.toBe(false)
    expect(harness.lineage.discardChanges).not.toHaveBeenCalled()

    const acceptedNavigation = harness.updateGuard?.()
    latestConfirmation().accept?.()
    await expect(acceptedNavigation).resolves.toBe(true)
    expect(harness.lineage.discardChanges).toHaveBeenCalledOnce()
  })

  it('confirms a depth change, discards edits, and reloads at the new depth', async () => {
    wrapper = mountView()
    await flushPromises()
    harness.lineage.load.mockClear()
    harness.lineage.hasEdits = true

    wrapper.findComponent(LineageWrapperStub).vm.$emit('depthChange', 3)
    await wrapper.vm.$nextTick()
    latestConfirmation().accept?.()
    await flushPromises()

    expect(harness.lineage.discardChanges).toHaveBeenCalledOnce()
    expect(harness.lineage.setDepth).toHaveBeenCalledWith(3)
    expect(harness.lineage.load).toHaveBeenCalledOnce()
  })

  it('keeps the current depth and edits when a depth change is declined', async () => {
    wrapper = mountView()
    await flushPromises()
    harness.lineage.load.mockClear()
    harness.lineage.hasEdits = true

    wrapper.findComponent(LineageWrapperStub).vm.$emit('depthChange', 3)
    await wrapper.vm.$nextTick()
    latestConfirmation().reject?.()
    await flushPromises()

    expect(harness.lineage.discardChanges).not.toHaveBeenCalled()
    expect(harness.lineage.setDepth).not.toHaveBeenCalled()
    expect(harness.lineage.load).not.toHaveBeenCalled()
    expect(harness.lineage.hasEdits).toBe(true)
  })

  it('shows the server detail when loading fails', async () => {
    harness.lineage.load.mockRejectedValue({ response: { data: { detail: 'Forbidden' } } })
    wrapper = mountView()
    await flushPromises()

    expect(harness.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Forbidden' }),
    )
  })
})
