<template>
  <ol class="flex flex-col min-w-0" :class="compact ? 'gap-1' : 'gap-2.5'">
    <li v-for="entry in entries" :key="entry.step" class="min-w-0">
      <div
        v-if="entry.kind === 'offline'"
        class="flex items-start gap-2 rounded border border-dashed border-surface-300 dark:border-surface-600 px-2.5 py-1.5 text-xs text-muted-color"
      >
        <WifiOff :size="13" class="shrink-0 mt-0.5" />
        <span class="min-w-0">
          <span class="text-surface-700 dark:text-surface-200"
            >edits while the daemon was down</span
          >
          — the fine-grained sequence is not recorded
        </span>
        <span class="ml-auto shrink-0 font-mono text-[11px]">{{ entry.time }}</span>
      </div>

      <div v-else-if="compact" class="flex items-center gap-1.5 text-xs min-w-0 px-0.5">
        <component :is="glyphOf(entry.kind)" :size="12" class="shrink-0 text-muted-color" />
        <span class="truncate">{{ entry.intent }}</span>
        <span v-if="entry.failedAttempts" class="shrink-0 text-muted-color">
          · {{ formatCount(entry.failedAttempts, 'failed attempt') }}
        </span>
        <span class="ml-auto shrink-0 font-mono text-[11px] text-muted-color">{{
          entry.time
        }}</span>
      </div>

      <div v-else class="flex items-start gap-2.5 min-w-0">
        <component :is="glyphOf(entry.kind)" :size="14" class="shrink-0 mt-1 text-muted-color" />
        <div class="flex flex-col gap-0.5 min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 min-w-0">
            <span class="font-mono text-[11px] text-muted-color shrink-0">{{ entry.time }}</span>
            <ActorChip :actor="entry.actor" muted />
            <span class="text-sm font-medium truncate">{{ entry.intent }}</span>
            <MetaBadge v-if="entry.settled" variant="settled" />
          </div>
          <p class="text-xs text-muted-color min-w-0">
            <span v-html="monoHtml(entry.summary)" />
            <span v-if="entry.failedAttempts">
              · {{ formatCount(entry.failedAttempts, 'failed attempt') }}
            </span>
          </p>
        </div>
      </div>
    </li>
  </ol>
</template>

<script setup lang="ts">
import {
  Bot,
  BotOff,
  CloudUpload,
  GitFork,
  GitMerge,
  Package,
  Pencil,
  Play,
  TextCursorInput,
  Trash2,
  WifiOff,
  type LucideIcon,
} from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { JournalEntry, JournalKind } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import MetaBadge from '../../ui/MetaBadge.vue'

/**
 * Read-only activity feed over the journal. The `offline` kind is deliberately
 * coarse and visibly distinct: presenting it as a normal burst would claim a
 * fine-grained sequence the daemon never recorded.
 */
defineProps<{ entries: JournalEntry[]; compact?: boolean }>()

const GLYPHS: Record<JournalKind, LucideIcon> = {
  edit: Pencil,
  run: Play,
  fork: GitFork,
  adopt: GitMerge,
  rename: TextCursorInput,
  delete: Trash2,
  promote: CloudUpload,
  'agent-begin': Bot,
  'agent-end': BotOff,
  offline: WifiOff,
  env: Package,
}

function glyphOf(kind: JournalKind): LucideIcon {
  return GLYPHS[kind]
}

/** Render backticked `slugs` as mono without a markdown pass (StatusChip's causeHtml pattern). */
function monoHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-[11px]">$1</code>')
}
</script>
