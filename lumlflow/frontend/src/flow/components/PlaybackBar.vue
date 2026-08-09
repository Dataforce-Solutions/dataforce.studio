<template>
  <div
    class="flex items-center gap-3 px-3 py-2 rounded border border-surface-300 dark:border-surface-600 text-sm"
  >
    <button class="px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600" @click="playback.toggle()">
      {{ playback.playing.value ? 'pause' : 'play' }}
    </button>
    <button class="px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600" @click="playback.reset()">
      reset
    </button>

    <input
      type="range"
      min="0"
      :max="playback.lastStep"
      :value="playback.step.value"
      class="flex-1"
      @input="playback.seek(Number(($event.target as HTMLInputElement).value))"
    />

    <span class="font-mono text-xs whitespace-nowrap">
      step {{ playback.step.value }} / {{ playback.lastStep }}
    </span>

    <select
      :value="playback.speed.value"
      class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-1 py-0.5 text-xs"
      @change="playback.setSpeed(Number(($event.target as HTMLSelectElement).value))"
    >
      <option :value="0.5">0.5x</option>
      <option :value="1">1x</option>
      <option :value="2">2x</option>
      <option :value="4">4x</option>
    </select>

    <span
      v-if="burst"
      class="px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 text-xs whitespace-nowrap"
      title="Several transactions landed on this step. Rendering one per tick will miss them."
    >
      burst · {{ burst }} transactions
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PlaybackControls } from '../composables/usePlayback'

const props = defineProps<{ playback: PlaybackControls }>()

/** More than one transaction on the current step — the case that overwhelms. */
const burst = computed(() => {
  const count = props.playback.session.value.transactions.filter(
    (tx) => tx.step === props.playback.step.value,
  ).length
  return count > 1 ? count : 0
})
</script>
