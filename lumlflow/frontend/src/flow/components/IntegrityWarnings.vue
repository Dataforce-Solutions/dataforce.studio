<template>
  <div v-if="warnings.length" class="space-y-1.5 mb-3">
    <div
      v-for="(warning, index) in warnings"
      :key="index"
      class="flex items-start gap-2 px-3 py-2 rounded border text-sm"
      :class="
        warning.kind === 'divergent-pin'
          ? 'border-red-400 bg-red-50 dark:bg-red-950/30 text-red-800 dark:text-red-300'
          : 'border-amber-400 bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300'
      "
    >
      <span class="mt-0.5">⚠</span>
      <div>
        <p class="font-medium">{{ title(warning.kind) }}</p>
        <p>{{ warning.message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IntegrityWarning } from '../types'

/**
 * Reasons a comparison may not be apples to apples.
 *
 * The divergent-pin case is the flagship: content addressing lets us detect
 * exactly that two variants read different versions of a shared upstream, where
 * every competing tool can only guess. Without this warning, pin-at-fork quietly
 * destroys the trustworthiness of every metric shown next to it.
 */
defineProps<{ warnings: IntegrityWarning[] }>()

const title = (kind: IntegrityWarning['kind']): string => {
  switch (kind) {
    case 'divergent-pin':
      return 'Divergent upstream pins'
    case 'dataset-mismatch':
      return 'Dataset inconsistency detected'
    case 'scoring-mismatch':
      return 'Scoring inconsistency detected'
    case 'nondeterministic-input':
      return 'Non-deterministic asset'
  }
}
</script>
