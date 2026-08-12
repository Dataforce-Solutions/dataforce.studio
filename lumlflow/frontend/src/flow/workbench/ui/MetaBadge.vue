<template>
  <span
    v-tooltip.top="tooltip"
    class="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded border"
    :class="classes"
  >
    <component :is="icon" :size="11" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  BadgeCheck,
  DatabaseZap,
  Globe,
  History,
  Pin,
  type LucideIcon,
} from 'lucide-vue-next'

/**
 * The small factual badges that ride next to a status chip. Each one states a
 * recorded fact the user would otherwise have to guess:
 * - cached      — memo hit; a hit is not a 0-second run
 * - older-env   — computed under a lock hash that differs from the live env
 * - settled     — branch fully materialized and consistent (a highlight, not a gate)
 * - external    — reads outside the store; unmemoizable
 * - pinned      — input frozen at fork time
 */
export type MetaBadgeVariant = 'cached' | 'older-env' | 'settled' | 'external' | 'pinned'

const props = defineProps<{ variant: MetaBadgeVariant }>()

const CONFIG: Record<
  MetaBadgeVariant,
  { label: string; tooltip: string; icon: LucideIcon; classes: string }
> = {
  cached: {
    label: 'cached',
    tooltip: 'Served from the memo cache — nothing recomputed',
    icon: DatabaseZap,
    classes:
      'border-sky-200 text-sky-700 bg-sky-50 dark:border-sky-500/30 dark:text-sky-300 dark:bg-sky-500/10',
  },
  'older-env': {
    label: 'older env',
    tooltip: 'Computed under an older environment lock than the live venv',
    icon: History,
    classes:
      'border-amber-200 text-amber-700 bg-amber-50 dark:border-amber-500/30 dark:text-amber-300 dark:bg-amber-500/10',
  },
  settled: {
    label: 'settled',
    tooltip: 'Branch fully materialized and consistent at this point',
    icon: BadgeCheck,
    classes:
      'border-emerald-200 text-emerald-700 bg-emerald-50 dark:border-emerald-500/30 dark:text-emerald-300 dark:bg-emerald-500/10',
  },
  external: {
    label: 'external',
    tooltip: 'Reads outside the store — unmemoizable; the store cannot know when it changes',
    icon: Globe,
    classes:
      'border-surface-300 text-surface-600 bg-surface-50 dark:border-surface-600 dark:text-surface-300 dark:bg-surface-800',
  },
  pinned: {
    label: 'pinned',
    tooltip: 'Frozen at fork time — updates are explicit accept-upstream ops',
    icon: Pin,
    classes:
      'border-surface-300 text-surface-600 bg-surface-50 dark:border-surface-600 dark:text-surface-300 dark:bg-surface-800',
  },
}

const label = computed(() => CONFIG[props.variant].label)
const tooltip = computed(() => CONFIG[props.variant].tooltip)
const icon = computed(() => CONFIG[props.variant].icon)
const classes = computed(() => CONFIG[props.variant].classes)
</script>
