<template>
  <button
    class="group w-full flex flex-col gap-1 rounded px-1.5 py-1 text-left min-w-0 hover:bg-surface-100 dark:hover:bg-surface-800"
    :aria-label="`Open the branch graph (viewing ${branch.name})`"
    @click="emit('open')"
  >
    <span class="flex items-center gap-2 min-w-0 w-full">
      <BranchTag :name="branch.name" :checked-out="branch.checkedOut" :archived="branch.archived" />
      <MetaBadge v-if="branch.settled" variant="settled" />
      <span v-else class="text-xs text-muted-color">working</span>
      <ChevronRight
        v-tooltip.top="'All branches and their graph'"
        :size="15"
        class="ml-auto shrink-0 text-muted-color transition-transform group-hover:translate-x-0.5"
      />
    </span>
    <span class="text-xs text-muted-color">{{ familyLine }}</span>
    <span v-if="viewingOnly" class="text-xs text-muted-color">
      viewing — a pure read; files stay on
      <code class="font-mono text-[11px]">{{ worktreeBranch }}</code>
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import type { BranchInfo } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'
import MetaBadge from '../../ui/MetaBadge.vue'

/**
 * The viewed branch's identity and family position. Viewing is a pure store
 * read; only checking out rebinds files — the caption keeps the verbs apart.
 */
const props = defineProps<{ branch: BranchInfo; worktreeBranch: string }>()

const emit = defineEmits<{ open: [] }>()

const familyLine = computed(() => {
  const { parent, forkedAtStep, headStep } = props.branch
  if (parent === null || forkedAtStep === null) return `root branch · ${headStep} steps`
  return `forked from ${parent} · ${headStep - forkedAtStep} steps ago`
})

const viewingOnly = computed(() => props.branch.name !== props.worktreeBranch)
</script>
