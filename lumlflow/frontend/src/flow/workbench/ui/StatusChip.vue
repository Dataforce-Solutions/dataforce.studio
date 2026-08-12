<template>
  <span class="inline-flex items-center gap-1.5 min-w-0">
    <Tag :severity="severity" :pt="tagPt" :class="subdued ? 'opacity-60' : ''">
      <span class="inline-flex items-center gap-1">
        <span
          v-if="status === 'running'"
          class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"
        />
        {{ label }}
      </span>
    </Tag>
    <span v-if="cause" class="text-xs text-muted-color truncate" v-html="causeHtml" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { CellStatus, StaleInfo } from '../model/types'

/**
 * The status vocabulary chip. `unmaterialized` is deliberately its own quiet
 * state (never a flavor of stale), and stale always names its cause in words.
 */
const props = defineProps<{
  status: CellStatus
  stale?: StaleInfo
  /** Hide the cause text (dense contexts: inventory rows, graph nodes). */
  compact?: boolean
}>()

const tagPt = { root: { class: 'text-xs font-normal px-2 py-0.5' } }

const label = computed(() => {
  if (props.status === 'stale' && props.stale?.transitive) return 'stale · downstream'
  return props.status
})

const severity = computed(() => {
  switch (props.status) {
    case 'materialized':
      return 'success'
    case 'running':
      return 'info'
    case 'stale':
      return 'warn'
    case 'failed':
      return 'danger'
    default:
      return 'secondary'
  }
})

const subdued = computed(
  () => props.status === 'unmaterialized' || (props.status === 'stale' && props.stale?.transitive),
)

const cause = computed(() => (!props.compact && props.status === 'stale' ? props.stale?.cause : ''))

/** Render `slug` spans in causes as code without pulling in a markdown pass. */
const causeHtml = computed(() =>
  (cause.value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-[11px]">$1</code>'),
)
</script>
