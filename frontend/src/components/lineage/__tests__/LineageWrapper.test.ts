import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LineageWrapper from '../LineageWrapper.vue'

const store = vi.hoisted(() => ({
  isLoading: false,
  hasEdges: false,
  truncated: false,
}))

vi.mock('@/stores/lineage', () => ({ useLineageStore: () => store }))

function mountWrapper() {
  return shallowMount(LineageWrapper, {
    global: {
      stubs: {
        LineageHeading: true,
        LineageToolbar: true,
        LineageStateControls: true,
        LineageActions: true,
        LineageArea: true,
        ProgressSpinner: true,
      },
    },
  })
}

describe('LineageWrapper', () => {
  beforeEach(() => {
    store.isLoading = false
    store.hasEdges = false
    store.truncated = false
  })

  it('shows the empty graph guidance', () => {
    expect(mountWrapper().text()).toContain(
      'No lineage recorded yet — link an artifact to get started',
    )
  })

  it('shows the graph limit notice when traversal is truncated', () => {
    store.hasEdges = true
    store.truncated = true

    expect(mountWrapper().text()).toContain(
      'Graph is limited to 200 artifacts — reduce depth to see complete levels',
    )
  })
})
