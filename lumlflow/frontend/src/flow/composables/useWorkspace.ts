import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { fixtureById, fixtures, type FixtureEntry } from '../fixtures'
import type { FlowSession } from '../types'

/**
 * Fixture selection, shared across all three concepts so switching between them
 * keeps the same data — otherwise the comparison is between different sessions
 * rather than between different designs.
 *
 * Playback is deliberately *not* shared: each concept owns its own
 * `usePlayback(session)` so it can control pacing and step granularity itself.
 */

const fixtureId = ref(fixtures[0].id)

export interface Workspace {
  fixtureId: Ref<string>
  fixtures: FixtureEntry[]
  session: ComputedRef<FlowSession>
}

export function useWorkspace(): Workspace {
  return {
    fixtureId,
    fixtures,
    session: computed(() => fixtureById(fixtureId.value)),
  }
}
