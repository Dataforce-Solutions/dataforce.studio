<template>
  <div
    class="flex items-end gap-1 border-b border-surface-200 dark:border-surface-700 overflow-x-auto"
    role="tablist"
  >
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      role="tab"
      :aria-selected="tab.id === selected"
      class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs whitespace-nowrap border-b-2 -mb-px transition-colors cursor-pointer"
      :class="
        tab.id === selected
          ? 'border-primary-500 text-color font-medium'
          : 'border-transparent text-muted-color hover:text-color'
      "
      @click="emit('select', tab.id)"
    >
      <component :is="iconFor(tab)" :size="12" class="shrink-0" />
      <span class="font-mono">{{ tab.label }}</span>
      <span v-if="tab.live" class="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
    </button>
  </div>
</template>

<script lang="ts">
import type { AssetKind } from '../../model/types'

export interface CellTab {
  id: string
  label: string
  /** Output tabs carry their asset kind for the icon. */
  kind?: AssetKind
  /** Implicit tabs: code, logs, and the live console while running. */
  icon?: 'code' | 'logs' | 'console'
  live?: boolean
}
</script>

<script setup lang="ts">
import { Code2, ScrollText, SquareTerminal, type LucideIcon } from 'lucide-vue-next'
import { KIND_ICONS } from '../../ui/kinds'

defineProps<{ tabs: CellTab[]; selected: string }>()

const emit = defineEmits<{ select: [id: string] }>()

const IMPLICIT_ICONS: Record<'code' | 'logs' | 'console', LucideIcon> = {
  code: Code2,
  logs: ScrollText,
  console: SquareTerminal,
}

function iconFor(tab: CellTab): LucideIcon {
  if (tab.kind) return KIND_ICONS[tab.kind] ?? KIND_ICONS.unknown
  return IMPLICIT_ICONS[tab.icon ?? 'code']
}
</script>
