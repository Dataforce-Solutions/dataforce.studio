import { computed, onScopeDispose, ref, type ComputedRef, type Ref } from 'vue'
import type { AssetVersion, FlowSession, Transaction } from '../types'

/**
 * The session as it stood at a given step.
 *
 * Playback is a filter over the finished fixture rather than a replay of ops —
 * a prototype does not need op application, and filtering keeps every derived
 * view in engine.ts working unchanged at any point in time.
 */
export function sessionAtStep(session: FlowSession, step: number): FlowSession {
  const assets: Record<string, AssetVersion[]> = {}
  for (const [assetId, versions] of Object.entries(session.assets)) {
    const visible = versions.filter((version) => version.createdAtStep <= step)
    if (visible.length) assets[assetId] = visible
  }

  const branches: FlowSession['branches'] = {}
  for (const [branchId, branch] of Object.entries(session.branches)) {
    if (branch.forkedAtStep > step) continue
    const selection: Record<string, string> = {}
    for (const [assetId, versionId] of Object.entries(branch.selection)) {
      const available = assets[assetId]
      if (!available) continue
      // Fall back to the newest version that existed at this step.
      selection[assetId] = available.some((version) => version.versionId === versionId)
        ? versionId
        : available[available.length - 1].versionId
    }
    branches[branchId] = { ...branch, selection }
  }

  return {
    ...session,
    assets,
    branches,
    transactions: session.transactions.filter((tx) => tx.step <= step),
  }
}

export interface PlaybackControls {
  step: Ref<number>
  lastStep: number
  playing: Ref<boolean>
  speed: Ref<number>
  session: ComputedRef<FlowSession>
  /** Transactions that landed since the viewer last marked themselves caught up. */
  unseen: ComputedRef<Transaction[]>
  play: () => void
  pause: () => void
  toggle: () => void
  reset: () => void
  seek: (step: number) => void
  setSpeed: (speed: number) => void
  markSeen: () => void
}

/**
 * Drives live playback of an event log.
 *
 * Steps advance on a timer, but several transactions can share a step — that is
 * how the burst is encoded, and a concept that renders one transaction per tick
 * will not see it.
 */
export function usePlayback(session: FlowSession, options: { autoplay?: boolean } = {}): PlaybackControls {
  const steps = session.transactions.map((tx) => tx.step)
  const lastStep = steps.length ? Math.max(...steps) : 0
  const step = ref(options.autoplay ? 0 : lastStep)
  const playing = ref(Boolean(options.autoplay))
  const speed = ref(1)
  const seenStep = ref(options.autoplay ? 0 : lastStep)

  let timer: ReturnType<typeof setInterval> | null = null

  const stop = (): void => {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  const tick = (): void => {
    if (step.value >= lastStep) {
      playing.value = false
      stop()
      return
    }
    step.value += 1
  }

  const start = (): void => {
    stop()
    timer = setInterval(tick, 700 / speed.value)
  }

  const play = (): void => {
    if (step.value >= lastStep) step.value = 0
    playing.value = true
    start()
  }

  const pause = (): void => {
    playing.value = false
    stop()
  }

  const toggle = (): void => (playing.value ? pause() : play())

  const reset = (): void => {
    pause()
    step.value = 0
    seenStep.value = 0
  }

  const seek = (next: number): void => {
    pause()
    step.value = Math.max(0, Math.min(lastStep, next))
  }

  const setSpeed = (next: number): void => {
    speed.value = next
    if (playing.value) start()
  }

  const markSeen = (): void => {
    seenStep.value = step.value
  }

  onScopeDispose(stop)

  return {
    step,
    lastStep,
    playing,
    speed,
    session: computed(() => sessionAtStep(session, step.value)),
    unseen: computed(() =>
      session.transactions.filter((tx) => tx.step > seenStep.value && tx.step <= step.value),
    ),
    play,
    pause,
    toggle,
    reset,
    seek,
    setSpeed,
    markSeen,
  }
}
