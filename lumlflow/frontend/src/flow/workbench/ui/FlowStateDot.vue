<template>
  <span v-tooltip.bottom="tooltip" class="inline-flex items-center gap-2 text-sm">
    <span class="relative flex w-2.5 h-2.5">
      <span
        v-if="state === 'running'"
        class="absolute inline-flex w-full h-full rounded-full opacity-60 animate-ping"
        :class="dotClass"
      />
      <span class="relative inline-flex w-2.5 h-2.5 rounded-full" :class="dotClass" />
    </span>
    <span v-if="!dotOnly" :class="state === 'daemon-down' ? 'text-red-600 dark:text-red-400' : ''">
      {{ label }}
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FlowState } from '../model/types'

/** The five-state flow indicator — running/stopped alone would not be honest. */
const props = defineProps<{ state: FlowState; dotOnly?: boolean }>()

const CONFIG: Record<FlowState, { label: string; tooltip: string; dot: string }> = {
  running: { label: 'running', tooltip: 'A run is in flight', dot: 'bg-emerald-500' },
  idle: { label: 'idle', tooltip: 'Paired, nothing running', dot: 'bg-sky-500' },
  unpaired: {
    label: 'unpaired',
    tooltip: 'No agent registered — everything still works',
    dot: 'bg-surface-400',
  },
  'kernel-not-started': {
    label: 'kernel not started',
    tooltip: 'Browsing works from previews; expanding a value will start the kernel',
    dot: 'bg-surface-400',
  },
  'daemon-down': {
    label: 'daemon down',
    tooltip: 'Nothing live — showing last-known state',
    dot: 'bg-red-500',
  },
}

const label = computed(() => CONFIG[props.state].label)
const tooltip = computed(() => CONFIG[props.state].tooltip)
const dotClass = computed(() => CONFIG[props.state].dot)
</script>
