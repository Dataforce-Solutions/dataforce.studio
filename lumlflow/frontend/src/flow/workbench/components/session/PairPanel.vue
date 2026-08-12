<template>
  <div
    class="flex flex-col gap-3 rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4"
  >
    <template v-if="paired">
      <div class="flex flex-wrap items-center gap-2 text-sm min-w-0">
        <ActorChip :actor="{ kind: 'agent', label: paired.label }" />
        <span class="text-muted-color">·</span>
        <span>{{ paired.state === 'working' ? 'working on' : 'idle on' }}</span>
        <BranchTag :name="paired.branch" />
      </div>
      <p v-if="paired.state === 'working' && paired.task" class="text-sm text-muted-color">
        {{ paired.task }}
      </p>
      <p v-else-if="paired.state === 'idle'" class="text-sm text-muted-color">
        idle{{ paired.idleFor ? ` · ${paired.idleFor} since last transaction` : '' }}
      </p>
    </template>

    <template v-else>
      <h4 class="text-sm font-medium">Pair an agent</h4>
      <CopyField value="lumlflow agent exec -- claude" />
      <p class="text-xs text-muted-color">
        already running one? register it with
        <code class="font-mono text-[11px]">lumlflow agent begin --label claude-1</code>
      </p>
      <div
        class="flex flex-col gap-1 text-xs text-muted-color border-t border-surface-200 dark:border-surface-700 pt-2.5"
      >
        <p>pairing is detected from the journal — nothing to confirm here</p>
        <p>unpaired is a working state: a human editing cells is a supported actor</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { PairedAgent } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import BranchTag from '../../ui/BranchTag.vue'
import CopyField from '../../ui/CopyField.vue'

// One-directional pairing: the UI hands over the command, then detects the
// agent_begin transaction. There is nothing for the user to confirm here.
defineProps<{ paired?: PairedAgent }>()
</script>
