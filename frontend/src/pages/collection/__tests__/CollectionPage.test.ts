import { flushPromises, shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CollectionPage from '../CollectionPage.vue'

const harness = vi.hoisted(() => ({
  route: null as { params: Record<string, string> } | null,
  routerPush: vi.fn(),
  setCurrentCollection: vi.fn().mockResolvedValue(undefined),
  resetCurrentCollection: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  const { reactive } = await import('vue')
  harness.route = {
    params: reactive({
      organizationId: 'org',
      id: 'orbit',
      collectionId: 'models',
    }),
  }
  return {
    ...actual,
    useRoute: () => harness.route,
    useRouter: () => ({ push: harness.routerPush }),
  }
})
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({
    currentCollection: null,
    setCurrentCollection: harness.setCurrentCollection,
    resetCurrentCollection: harness.resetCurrentCollection,
  }),
}))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    currentOrbitDetails: { id: 'orbit' },
    getOrbitDetails: vi.fn(),
    setCurrentOrbitDetails: vi.fn(),
  }),
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: { id: 'org' } }),
}))
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: harness.toastAdd }) }
})

describe('CollectionPage', () => {
  let wrapper: ReturnType<typeof shallowMount> | null = null

  beforeEach(() => {
    harness.setCurrentCollection.mockReset().mockResolvedValue(undefined)
    harness.resetCurrentCollection.mockReset()
    harness.toastAdd.mockReset()
    if (harness.route) harness.route.params.collectionId = 'models'
  })

  afterEach(() => wrapper?.unmount())

  it('reloads collection data when the collection URL parameter changes', async () => {
    wrapper = shallowMount(CollectionPage, {
      global: {
        stubs: {
          UiPageLoader: true,
          Ui404: true,
          CollectionBreadcrumb: true,
          RouterView: true,
        },
      },
    })
    await flushPromises()
    expect(harness.setCurrentCollection).toHaveBeenLastCalledWith('models')

    if (!harness.route) throw new Error('Route was not initialized')
    harness.route.params.collectionId = 'datasets'
    await nextTick()
    await flushPromises()

    expect(harness.setCurrentCollection).toHaveBeenLastCalledWith('datasets')
    expect(harness.setCurrentCollection).toHaveBeenCalledTimes(2)
  })
})
