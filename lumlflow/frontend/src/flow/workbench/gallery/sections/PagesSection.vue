<template>
  <div class="flex max-w-4xl flex-col gap-4">
    <div class="grid gap-4 sm:grid-cols-2">
      <div
        v-for="page in pages"
        :key="page.to"
        class="flex flex-col gap-2 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
      >
        <div class="flex items-center justify-between gap-3">
          <p class="text-sm font-medium">{{ page.title }}</p>
          <RouterLink
            :to="page.to"
            class="inline-flex items-center gap-1.5 rounded border border-surface-300 px-2.5 py-1 text-xs transition-colors hover:border-primary-400 hover:text-primary-600 dark:border-surface-600 dark:hover:border-primary-500 dark:hover:text-primary-400"
          >
            open
            <ArrowRight :size="12" />
          </RouterLink>
        </div>
        <p class="text-xs text-muted-color">{{ page.blurb }}</p>

        <div v-if="page.stateChips" class="mt-1 flex flex-wrap gap-1.5">
          <RouterLink
            v-for="state in workbenchStates"
            :key="state"
            v-tooltip.top="state === 'running' ? 'default' : undefined"
            :to="`/flow/work?state=${state}`"
            class="rounded border border-surface-200 px-1.5 py-0.5 font-mono text-[11px] text-muted-color transition-colors hover:border-primary-400 hover:text-primary-600 dark:border-surface-700 dark:hover:border-primary-500 dark:hover:text-primary-400"
          >
            ?state={{ state }}<template v-if="state === 'running'"> · default</template>
          </RouterLink>
        </div>

        <p v-if="page.note" class="text-xs italic text-muted-color">{{ page.note }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { ArrowRight } from 'lucide-vue-next'

interface PageCard {
  title: string
  to: string
  blurb: string
  stateChips?: boolean
  note?: string
}

const pages: PageCard[] = [
  {
    title: 'Flows',
    to: '/flow/flows',
    blurb: 'The picker — flows the daemon knows, plus the open-a-folder and init doors.',
  },
  {
    title: 'Workbench · canvas',
    to: '/flow/work',
    blurb:
      'One screen, two views: the active branch, its inventory, and the cell cards on the graph, outputs first.',
    stateChips: true,
  },
  {
    title: 'Workbench · notebook',
    to: '/flow/work?view=notebook',
    blurb: 'The same branch slice and the same cards, one column, code accented.',
  },
  {
    title: 'Compare',
    to: '/flow/compare',
    blurb:
      'Side-by-side results, divergence points, collapsed same-code rows, artifacts, and the two closing verbs.',
  },
  {
    title: 'Reference · railroad',
    to: '/flow/railroad',
    blurb: 'The earlier fixture-backed concept prototype, untouched.',
    note: 'the approved concept this workbench supersedes — kept as reference',
  },
]

const workbenchStates = [
  'running',
  'idle',
  'unpaired',
  'empty',
  'kernel-not-started',
  'daemon-down',
  'locked',
]
</script>
