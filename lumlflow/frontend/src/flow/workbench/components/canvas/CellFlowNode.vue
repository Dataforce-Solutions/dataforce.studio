<template>
  <Handle type="target" :position="Position.Left" class="opacity-0" />
  <div
    class="rounded-lg"
    :class="data.tinted ? 'ring-1 ring-amber-400/60 dark:ring-amber-500/40' : ''"
  >
    <CellCard
      :cell="data.cell"
      density="canvas"
      :selected="data.selected"
      :branch="data.branch"
      :preflight="data.preflight"
      @expand="data.events.expand()"
      @run="data.events.run($event)"
      @stop="data.events.stop()"
      @rename="data.events.rename()"
      @delete="data.events.remove()"
      @duplicate="data.events.duplicate()"
      @navigate="data.events.navigate($event)"
      @send-to-agent="data.events.sendToAgent($event)"
      @resolve-conflict="data.events.resolveConflict($event)"
      @edit="data.events.edit($event)"
      @edit-params="data.events.editParams($event)"
    />
  </div>
  <Handle type="source" :position="Position.Right" class="opacity-0" />
</template>

<script lang="ts">
import type { FlowCell, ParamValue, Preflight } from '../../model/types'

/** Card events escape the vue-flow node slot through data-carried callbacks. */
export interface CellNodeEvents {
  expand: () => void
  run: (payload: { force: boolean }) => void
  stop: () => void
  rename: () => void
  remove: () => void
  duplicate: () => void
  navigate: (payload: { view: 'canvas' | 'notebook'; slug: string }) => void
  sendToAgent: (payload: string) => void
  resolveConflict: (choice: 'overwrite' | 'fork') => void
  edit: (payload: { source: string }) => void
  editParams: (params: Record<string, ParamValue>) => void
}

export interface CellNodeData {
  cell: FlowCell
  branch: string
  selected: boolean
  /** Transitive-staleness filter is ON and this cell is transitively stale. */
  tinted: boolean
  preflight?: Preflight
  events: CellNodeEvents
}
</script>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import CellCard from '../card/CellCard.vue'

defineProps<{ data: CellNodeData }>()
</script>
