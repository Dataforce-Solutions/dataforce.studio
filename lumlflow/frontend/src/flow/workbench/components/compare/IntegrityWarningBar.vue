<template>
  <div
    class="flex gap-2.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-500/30 dark:bg-amber-500/10"
  >
    <TriangleAlert :size="15" class="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
    <div class="flex min-w-0 flex-col gap-1.5">
      <p class="text-sm text-amber-800 dark:text-amber-200">
        <span class="font-medium">{{ kindLabel }}</span>
        <span> — </span>
        <span v-html="messageHtml" />
      </p>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span class="text-xs text-amber-700/80 dark:text-amber-300/80">affects</span>
        <BranchTag v-for="branch in warning.affectedBranches" :key="branch" :name="branch" />
      </div>
      <p class="text-xs text-muted-color">
        A side-by-side of two numbers that were not computed comparably is worse than no comparison.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TriangleAlert } from 'lucide-vue-next'
import type { CompareWarning } from '../../fixtures/compare'
import BranchTag from '../../ui/BranchTag.vue'

const props = defineProps<{ warning: CompareWarning }>()

const KIND_LABELS: Record<CompareWarning['kind'], string> = {
  'divergent-pin': 'divergent pin',
  'dataset-mismatch': 'dataset mismatch',
  'scoring-mismatch': 'scoring mismatch',
  'nondeterministic-input': 'nondeterministic input',
}

const kindLabel = computed(() => KIND_LABELS[props.warning.kind])

/** Render `slug` spans in the message as code without a markdown pass. */
const messageHtml = computed(() =>
  props.warning.message
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-[12px]">$1</code>'),
)
</script>
