import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import CatchupConcept from '@/flow/concepts/CatchupConcept.vue'
import CompareConcept from '@/flow/concepts/CompareConcept.vue'
import RailroadConcept from '@/flow/concepts/RailroadConcept.vue'
import { unsyncedCause } from '@/flow/engine'
import { churnSession, fixtures } from '@/flow/fixtures'
import { useWorkspace } from '@/flow/composables/useWorkspace'

const IGNORED_WARNINGS = [/Vue Flow parent container needs a width and a height/]

const unexpected = (spy: { mock: { calls: unknown[][] } }): string[] =>
  spy.mock.calls
    .map((call) => call.map(String).join(' '))
    .filter((message) => !IGNORED_WARNINGS.some((pattern) => pattern.test(message)))

const concepts = [
  { name: 'railroad', component: RailroadConcept },
  { name: 'compare', component: CompareConcept },
  { name: 'catchup', component: CatchupConcept },
]

describe('flow concept prototypes', () => {
  for (const fixture of fixtures) {
    for (const concept of concepts) {
      it(`${concept.name} mounts against the ${fixture.id} fixture`, async () => {
        const { fixtureId } = useWorkspace()
        fixtureId.value = fixture.id
        await nextTick()

        const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
        const warnings = vi.spyOn(console, 'warn').mockImplementation(() => {})

        const wrapper = mount(concept.component)
        await nextTick()

        expect(wrapper.html().length).toBeGreaterThan(0)
        expect(errors).not.toHaveBeenCalled()
        // jsdom gives no element a size, so Vue Flow cannot measure its
        // container. That is an environment limit, not a defect.
        expect(unexpected(warnings)).toEqual([])

        wrapper.unmount()
        errors.mockRestore()
        warnings.mockRestore()
      })
    }
  }
})

/**
 * Regression test for the substrate defect that made the changed-vs-rematerialized
 * badge silently dead: staleness was read from a stored materialization state that
 * no fixture emits, and stored per version when it is a property of (branch, asset).
 */
describe('unsyncedCause', () => {
  const causesFor = (branchId: string): Record<string, string> => {
    const result: Record<string, string> = {}
    for (const assetId of Object.keys(churnSession.branches[branchId].selection)) {
      const cause = unsyncedCause(churnSession, branchId, assetId)
      if (cause) result[assetId] = cause
    }
    return result
  }

  it('reports nothing on the branch everything was authored in', () => {
    expect(causesFor('main')).toEqual({})
  })

  it('separates the edited asset from the ones that merely rematerialized', () => {
    expect(causesFor('feat-buckets')).toEqual({
      a_features: 'definition-changed',
      a_split: 'parent-rematerialized',
    })
  })

  it('catches a structural rewire, which an input-version heuristic cannot see', () => {
    expect(causesFor('model-logreg')).toMatchObject({ a_eval: 'deps-rewired' })
  })

  it('surfaces the divergent upstream pin on the sweep branches', () => {
    const causes = causesFor('sweep-600-005')
    expect(causes.a_raw).toBe('definition-changed')
    expect(causes.a_clean).toBe('parent-rematerialized')
  })
})
