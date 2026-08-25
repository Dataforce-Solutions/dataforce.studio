import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { reactive } from 'vue'
import DeploymentsFormSatelliteSettings from './DeploymentsFormSatelliteSettings.vue'

const MONITORED = {
  id: 'sat-monitored',
  name: 'Monitored satellite',
  capabilities: { deploy: { supported_variants: ['pyfunc'] }, monitoring: { version: 1 } },
}
const PLAIN = {
  id: 'sat-plain',
  name: 'Plain satellite',
  capabilities: { deploy: { supported_variants: ['pyfunc'] } },
}

const satellitesStore = reactive({
  satellitesList: [MONITORED, PLAIN],
  getSatellites: vi.fn(),
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => satellitesStore,
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

const SELECTED_MODEL = {
  manifest: { variant: 'pyfunc', producer_tags: [] },
} as never

function mountForm(props: Record<string, unknown> = {}) {
  return mount(DeploymentsFormSatelliteSettings, {
    props: {
      selectedModel: SELECTED_MODEL,
      satelliteId: null,
      fields: [],
      monitoringEnabled: false,
      ...props,
    },
    global: {
      stubs: {
        Select: { template: '<div />' },
        FormField: { template: '<div><slot /></div>' },
        InputText: { template: '<input />' },
        InputNumber: { template: '<input />' },
        ToggleButton: { template: '<button />' },
        ToggleSwitch: {
          template:
            '<button data-testid="toggle" @click="$emit(\'update:modelValue\', !modelValue)" />',
          props: ['modelValue'],
        },
      },
    },
  })
}

describe('DeploymentsFormSatelliteSettings — monitoring', () => {
  it('hides the monitoring block until a satellite is picked', () => {
    const wrapper = mountForm()

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(false)
  })

  it('offers the toggle once the picked satellite advertises monitoring', () => {
    const wrapper = mountForm({ satelliteId: MONITORED.id })

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(true)
  })

  it('never offers the toggle for a satellite without the capability', () => {
    const wrapper = mountForm({ satelliteId: PLAIN.id })

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(false)
  })

  it('emits the new value so the create payload can carry monitoring_mode', async () => {
    const wrapper = mountForm({ satelliteId: MONITORED.id })

    await wrapper.find('[data-testid="create-monitoring-toggle"]').trigger('click')

    expect(wrapper.emitted('update:monitoringEnabled')).toEqual([[true]])
  })

  it('switching to a non-monitoring satellite drops the toggle instead of smuggling it on', async () => {
    const wrapper = mountForm({ satelliteId: MONITORED.id, monitoringEnabled: true })

    await wrapper.setProps({ satelliteId: PLAIN.id })

    expect(wrapper.emitted('update:monitoringEnabled')?.at(-1)).toEqual([false])
  })

  it('an edit opened with monitoring on under a capability-less satellite still shows it, with the warning', () => {
    const wrapper = mountForm({ monitoringEnabled: true, satelliteId: PLAIN.id })

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('does not report the monitoring capability')
  })

  it('stays quiet when the chosen satellite supports monitoring', () => {
    const wrapper = mountForm({ monitoringEnabled: true, satelliteId: MONITORED.id })

    expect(wrapper.text()).not.toContain('does not report the monitoring capability')
  })
})
