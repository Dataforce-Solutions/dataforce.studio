<template>
  <div class="flex flex-col gap-1 px-1.5 min-w-0">
    <template v-if="paired && paired.state === 'working'">
      <div class="flex items-center gap-2 min-w-0">
        <ActorChip :actor="{ kind: 'agent', label: paired.label }" />
        <BranchTag v-if="paired.branch !== viewedBranch" :name="paired.branch" />
      </div>
      <p v-if="paired.task" class="text-sm min-w-0">{{ paired.task }}</p>
    </template>

    <template v-else-if="paired">
      <div class="flex items-center gap-2 min-w-0">
        <ActorChip :actor="{ kind: 'agent', label: paired.label }" muted />
        <span class="text-sm text-muted-color">
          idle{{ paired.idleFor ? ` · ${paired.idleFor} since last transaction` : '' }}
        </span>
      </div>
    </template>

    <p v-else class="text-sm text-muted-color">
      not paired ·
      <span
        v-tooltip.top="'The pair panel has the command — pairing is detected from the journal'"
        class="underline underline-offset-2 decoration-surface-300 dark:decoration-surface-600 cursor-help"
      >
        pair an agent
      </span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { PairedAgent } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import BranchTag from '../../ui/BranchTag.vue'

// Rendered from the latest transaction's intent — never a fabricated status.
defineProps<{ paired?: PairedAgent; viewedBranch: string }>()
</script>
