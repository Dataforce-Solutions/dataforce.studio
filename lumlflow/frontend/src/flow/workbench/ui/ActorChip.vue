<template>
  <span class="inline-flex items-center gap-1.5 text-sm" :class="muted ? 'text-muted-color' : ''">
    <span
      class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
      :class="
        actor.kind === 'agent'
          ? 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300'
          : 'bg-surface-200 text-surface-700 dark:bg-surface-700 dark:text-surface-200'
      "
    >
      <Bot v-if="actor.kind === 'agent'" :size="12" />
      <UserRound v-else :size="12" />
    </span>
    <span class="truncate">{{ actor.label }}</span>
    <span
      v-if="uncertain"
      v-tooltip.top="'Mixed editing window — attribution uncertain'"
      class="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
    >
      <TriangleAlert :size="12" />
      uncertain
    </span>
  </span>
</template>

<script setup lang="ts">
import { Bot, TriangleAlert, UserRound } from 'lucide-vue-next'
import type { ActorRef } from '../model/types'

defineProps<{
  actor: ActorRef
  /** Render the mixed-editing-window flag instead of a confident wrong name. */
  uncertain?: boolean
  muted?: boolean
}>()
</script>
