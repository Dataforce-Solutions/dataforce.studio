/**
 * The transient phases reactlog draws and a settled fixture cannot contain.
 *
 * `MaterializationState` has `invalidating`, but a finished session only ever
 * stores the resting state. So when playback lands on a step we synthesise the
 * phase sequence the kernel would have emitted: the touched asset starts
 * writing/running, its descendants tear down (`invalidating`), then rebuild
 * (`running`), then everything settles back to the stored state. Motion is spent
 * here and nowhere else — layout never moves, so a moving pixel always means an
 * event.
 */

import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { downstreamOf } from '../../engine'
import type { AssetId, BranchId, FlowSession, Transaction } from '../../types'

export type PulseKind = 'writing' | 'materializing' | 'invalidating' | 'failed' | 'renamed'

export interface Pulse {
  kind: PulseKind
  label?: string
}

const TEAR_DOWN_MS = 460
const SETTLE_MS = 1100

function pulsesForTransactions(
  session: FlowSession,
  branchId: BranchId,
  transactions: Transaction[],
): Record<AssetId, Pulse> {
  const pulses: Record<AssetId, Pulse> = {}
  const touched: AssetId[] = []

  for (const tx of transactions) {
    for (const op of tx.ops) {
      switch (op.op) {
        case 'create-asset':
        case 'edit-asset':
          pulses[op.assetId] = { kind: 'writing', label: tx.intent }
          touched.push(op.assetId)
          break
        case 'rename-asset':
          pulses[op.assetId] = { kind: 'renamed', label: `${op.from} → ${op.to}` }
          touched.push(op.assetId)
          break
        case 'rewire-asset':
          pulses[op.assetId] = { kind: 'writing', label: 'dependencies rewired' }
          touched.push(op.assetId)
          break
        case 'materialize':
          pulses[op.assetId] =
            op.result.state === 'failed'
              ? { kind: 'failed', label: 'materialization failed' }
              : { kind: 'materializing' }
          touched.push(op.assetId)
          break
        default:
          break
      }
    }
  }

  for (const assetId of touched) {
    for (const child of downstreamOf(session, branchId, assetId)) {
      if (!pulses[child]) pulses[child] = { kind: 'invalidating' }
    }
  }

  return pulses
}

export interface PulseState {
  pulses: Ref<Record<AssetId, Pulse>>
  /** Assets touched by the transactions on the current step, pulse or not. */
  touched: Ref<Set<AssetId>>
}

export function usePulses(
  session: Ref<FlowSession>,
  branchId: Ref<BranchId>,
  step: Ref<number>,
): PulseState {
  const pulses = ref<Record<AssetId, Pulse>>({})
  const touched = ref<Set<AssetId>>(new Set())
  let timers: ReturnType<typeof setTimeout>[] = []

  const clearTimers = (): void => {
    timers.forEach(clearTimeout)
    timers = []
  }

  watch(
    step,
    (value) => {
      clearTimers()
      const transactions = session.value.transactions.filter((tx) => tx.step === value)
      if (!transactions.length) {
        pulses.value = {}
        touched.value = new Set()
        return
      }

      const next = pulsesForTransactions(session.value, branchId.value, transactions)
      pulses.value = next
      touched.value = new Set(Object.keys(next))

      // Tear-down is a distinct phase from rebuild: descendants flip from
      // invalidating to materializing rather than going straight to settled.
      timers.push(
        setTimeout(() => {
          const rebuilt: Record<AssetId, Pulse> = {}
          for (const [assetId, pulse] of Object.entries(pulses.value)) {
            rebuilt[assetId] = pulse.kind === 'invalidating' ? { kind: 'materializing' } : pulse
          }
          pulses.value = rebuilt
        }, TEAR_DOWN_MS),
      )
      timers.push(
        setTimeout(() => {
          pulses.value = {}
        }, SETTLE_MS),
      )
    },
    { immediate: true },
  )

  onScopeDispose(clearTimers)

  return { pulses, touched }
}
