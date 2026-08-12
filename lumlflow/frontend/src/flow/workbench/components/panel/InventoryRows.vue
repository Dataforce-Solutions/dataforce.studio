<script lang="ts">
import type { AssetKind, CellStatus, StaleInfo } from '../../model/types'

/** One lens row: always addressed by the producing cell's slug. */
export interface InventoryRow {
  key: string
  slug: string
  kind: AssetKind
  title: string
  mono?: boolean
  /** Right-aligned fact, e.g. 'val_auc 0.856'. */
  detail?: string
  status?: CellStatus
  stale?: StaleInfo
  /** volatility: external — the store cannot know when its bytes change. */
  external?: boolean
}
</script>

<script setup lang="ts">
import KindBadge from '../../ui/KindBadge.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import SectionLabel from '../../ui/SectionLabel.vue'
import StatusChip from '../../ui/StatusChip.vue'

defineProps<{
  label: string
  rows: InventoryRow[]
  caption?: string
  emptyText?: string
}>()

const emit = defineEmits<{ select: [slug: string] }>()
</script>

<template>
  <section class="flex flex-col gap-1.5 min-w-0">
    <SectionLabel :label="label" :count="rows.length" />
    <p v-if="caption" class="text-[11px] text-muted-color">{{ caption }}</p>
    <ul v-if="rows.length" class="flex flex-col">
      <li v-for="row in rows" :key="row.key">
        <button
          class="w-full flex items-center gap-2 rounded px-1.5 py-1 text-left min-w-0 hover:bg-surface-100 dark:hover:bg-surface-800"
          @click="emit('select', row.slug)"
        >
          <KindBadge :kind="row.kind" icon-only :icon-size="13" />
          <span class="text-[13px] truncate" :class="row.mono ? 'font-mono' : ''">
            {{ row.title }}
          </span>
          <MetaBadge v-if="row.external" variant="external" />
          <span class="ml-auto" />
          <span v-if="row.detail" class="shrink-0 font-mono text-[11px] text-muted-color">
            {{ row.detail }}
          </span>
          <StatusChip v-if="row.status" :status="row.status" :stale="row.stale" compact />
        </button>
      </li>
    </ul>
    <p v-else class="text-xs text-muted-color px-1.5">{{ emptyText ?? 'none on this branch' }}</p>
  </section>
</template>
