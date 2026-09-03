import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LineageActions from '../LineageActions.vue'

const store = vi.hoisted(() => ({
  depth: 2,
  hasNodes: true,
  isLoading: false,
  resetPositions: vi.fn(),
}))

vi.mock('@/stores/lineage', () => ({ useLineageStore: () => store }))

const SelectStub = defineComponent({
  name: 'Select',
  props: ['modelValue', 'options', 'disabled'],
  emits: ['update:modelValue'],
  template: '<select />',
})

const ButtonStub = defineComponent({
  name: 'Button',
  props: { disabled: Boolean },
  emits: ['click'],
  template:
    '<button :disabled="disabled" @click="$emit(\'click\')"><slot /><slot name="icon" /></button>',
})

function mountActions() {
  return shallowMount(LineageActions, {
    global: { stubs: { Select: SelectStub, Button: ButtonStub } },
  })
}

describe('LineageActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.depth = 2
    store.hasNodes = true
    store.isLoading = false
  })

  it('allows resetting a loaded graph even when there are no edits', async () => {
    const wrapper = mountActions()
    const reset = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Reset positions'))

    expect(reset?.attributes('disabled')).toBeUndefined()
    await reset?.trigger('click')
    expect(store.resetPositions).toHaveBeenCalledOnce()
  })

  it('offers depths 1 through 5 and emits the requested value', async () => {
    const wrapper = mountActions()
    const select = wrapper.findComponent(SelectStub)

    expect(select.props('options')).toEqual([1, 2, 3, 4, 5])
    select.vm.$emit('update:modelValue', 4)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('depthChange')).toEqual([[4]])
  })
})
