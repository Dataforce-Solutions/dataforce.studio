import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LineageStateControls from '../LineageStateControls.vue'

const store = vi.hoisted(() => ({
  hasEdits: true,
  unconnectedArtifactsCount: 2,
  history: [{}],
  save: vi.fn(),
  goBack: vi.fn(),
}))
const toastAdd = vi.hoisted(() => vi.fn())

vi.mock('@/stores/lineage', () => ({ useLineageStore: () => store }))
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: toastAdd }) }
})

const ButtonStub = defineComponent({
  name: 'Button',
  props: { label: String, disabled: Boolean, loading: Boolean },
  emits: ['click'],
  template:
    '<button :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}<slot name="icon" /></button>',
})

describe('LineageStateControls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.hasEdits = true
    store.unconnectedArtifactsCount = 2
    store.history = [{}]
  })

  function mountControls() {
    return shallowMount(LineageStateControls, {
      global: {
        stubs: { Button: ButtonStub },
        directives: { tooltip: () => undefined },
      },
    })
  }

  it('disables saving and explains when artifacts are unconnected', () => {
    const wrapper = mountControls()

    expect(wrapper.find('button').attributes()).toHaveProperty('disabled')
    expect(wrapper.text()).toContain('2 artifacts are not connected — connect or remove them')
  })

  it('keeps saving disabled when the loaded graph has no edits', () => {
    store.hasEdits = false
    store.unconnectedArtifactsCount = 0
    store.history = []

    expect(mountControls().find('button').attributes()).toHaveProperty('disabled')
  })

  it.each([
    [409, 'Lineage connection already exists'],
    [403, 'Forbidden'],
  ])('shows the server detail when saving fails with %i', async (status, detail) => {
    store.unconnectedArtifactsCount = 0
    store.save.mockRejectedValueOnce({ response: { status, data: { detail } } })
    const wrapper = mountControls()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', detail }))
    expect(store.history).toEqual([{}])
    expect(store.hasEdits).toBe(true)
  })
})
