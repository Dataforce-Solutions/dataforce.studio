import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DashboardHeader from './DashboardHeader.vue'
import { makeHeader } from '@/test/fixtures'

describe('DashboardHeader', () => {
  it('shows when the worker last closed a window, not only the last prediction', () => {
    // The snapshot sections render their window whatever its age, so this line is the
    // only thing on the page that dates them.
    const wrapper = mount(DashboardHeader, {
      props: {
        header: makeHeader({
          last_prediction_at: '2026-07-07T12:00:00Z',
          last_monitored_at: '2026-07-05T09:00:00Z',
        }),
      },
    })

    expect(wrapper.text()).toContain('last prediction')
    expect(wrapper.text()).toContain('last monitored')
  })

  it('omits the monitored line when the worker has never materialized a window', () => {
    const wrapper = mount(DashboardHeader, {
      props: { header: makeHeader({ last_monitored_at: null }) },
    })

    expect(wrapper.text()).not.toContain('last monitored')
  })
})
