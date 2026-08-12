<template>
  <div class="flex flex-col gap-2">
    <p class="text-xs text-muted-color">
      same code, different inputs — collapsed; never a fan of identical-code nodes
    </p>
    <div class="overflow-x-auto">
      <div
        class="grid items-center gap-x-5 gap-y-0"
        :style="{
          gridTemplateColumns: `max-content repeat(${branchOrder.length}, minmax(7rem, max-content))`,
        }"
      >
        <span />
        <span v-for="branch in branchOrder" :key="branch" class="pb-1.5">
          <BranchTag :name="branch" />
        </span>

        <template v-for="row in rows" :key="row.slug + row.output">
          <span
            class="border-t border-surface-200 py-2 pr-2 font-mono text-[13px] dark:border-surface-700"
          >
            {{ row.slug }}<span class="text-muted-color">.{{ row.output }}</span>
          </span>
          <span
            v-for="branch in branchOrder"
            :key="branch"
            class="border-t border-surface-200 py-2 dark:border-surface-700"
          >
            <span
              v-if="row.byBranch[branch]"
              class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs tabular-nums"
              :class="chipClass(row.byBranch[branch].state)"
            >
              {{ row.byBranch[branch].label }}
            </span>
            <span v-else class="text-xs text-muted-color">—</span>
          </span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MaterializationRow } from '../../fixtures/compare'
import BranchTag from '../../ui/BranchTag.vue'

const props = defineProps<{ rows: MaterializationRow[] }>()

const branchOrder = computed(() => {
  const branches: string[] = []
  for (const row of props.rows)
    for (const branch of Object.keys(row.byBranch))
      if (!branches.includes(branch)) branches.push(branch)
  return branches
})

const CHIP_CLASSES: Record<string, string> = {
  same: 'border-surface-200 bg-surface-50 text-surface-700 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-300',
  better:
    'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300',
  worse:
    'border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300',
  missing: 'border-dashed border-surface-300 text-muted-color dark:border-surface-600',
}

function chipClass(state: string): string {
  return CHIP_CLASSES[state] ?? CHIP_CLASSES.same
}
</script>
