<template>
  <span
    v-if="cause"
    class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs border"
    :class="tone"
    :title="explanation"
  >
    <span class="w-1.5 h-1.5 rounded-full" :class="dotTone" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { UnsyncedCause } from '../types'

/**
 * Unsynced badge, per Dagster's non-transitive rule.
 *
 * The distinction the label carries is the one that matters: an asset someone
 * *edited* reads differently from one that merely rematerialized because a
 * parent moved. Collapse the two and every branch diff is 90% noise.
 */
const props = defineProps<{ cause: UnsyncedCause | null }>()

const label = computed(() => {
  switch (props.cause) {
    case 'definition-changed':
      return 'changed'
    case 'deps-rewired':
      return 'rewired'
    case 'parent-rematerialized':
      return 'rematerialized'
    default:
      return ''
  }
})

const explanation = computed(() => {
  switch (props.cause) {
    case 'definition-changed':
      return 'This asset’s own source or params changed.'
    case 'deps-rewired':
      return 'This asset’s dependencies were added, removed, or repointed.'
    case 'parent-rematerialized':
      return 'A direct parent rematerialized with a different content hash. This asset’s code is unchanged.'
    default:
      return ''
  }
})

const tone = computed(() =>
  props.cause === 'parent-rematerialized'
    ? 'border-surface-300 dark:border-surface-600 text-muted-color'
    : 'border-amber-400 text-amber-700 dark:text-amber-400',
)

const dotTone = computed(() =>
  props.cause === 'parent-rematerialized' ? 'bg-surface-400' : 'bg-amber-500',
)
</script>
