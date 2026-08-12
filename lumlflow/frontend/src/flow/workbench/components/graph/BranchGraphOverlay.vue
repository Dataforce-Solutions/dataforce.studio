<template>
  <Dialog
    v-model:visible="visible"
    modal
    header="Branches"
    dismissable-mask
    :style="{ width: 'min(58rem, 94vw)' }"
  >
    <BranchGraph
      :branches="branches"
      :selectable="selectable"
      :worktree-locked="worktreeLocked"
      @view="emit('view', $event)"
      @checkout="emit('checkout', $event)"
      @archive="emit('archive', $event)"
      @compare="emit('compare', $event)"
    />
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog } from 'primevue'
import type { BranchInfo } from '../../model/types'
import BranchGraph from './BranchGraph.vue'

// Overlay, not a permanent panel: branch topology is consulted at decision
// points, disclosed from the branch identifier.
defineProps<{
  branches: BranchInfo[]
  selectable?: boolean
  worktreeLocked?: boolean
}>()

const emit = defineEmits<{
  view: [name: string]
  checkout: [name: string]
  archive: [name: string]
  compare: [names: string[]]
}>()

const visible = defineModel<boolean>('visible', { required: true })
</script>
