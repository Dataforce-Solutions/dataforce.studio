<template>
  <aside
    class="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 px-4 py-3"
  >
    <span
      class="w-7 h-7 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300 flex items-center justify-center shrink-0 mt-0.5"
    >
      <Bot :size="15" />
    </span>
    <div class="flex flex-col gap-0.5 flex-1 min-w-0">
      <p class="text-sm font-medium">the agent session ended</p>
      <p class="text-xs text-muted-color" v-html="outstandingHtml" />
    </div>
    <SendToAgentButton
      :cell="cell"
      :branch="branch ?? 'main'"
      :gesture="failedRun ? 'fix' : 'explain'"
      label="hand off"
      @send-to-agent="emit('send-to-agent', $event)"
    />
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bot } from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { FlowCell } from '../../model/types'
import SendToAgentButton from '../handoff/SendToAgentButton.vue'
import { inlineCodeHtml } from './inlineCode'

/**
 * A state, not a toast: anchored under the last cell the agent touched when its
 * session ended with work outstanding. Says what is outstanding — never why the
 * session ended, because that is not recorded.
 */
const props = defineProps<{
  cell: FlowCell
  branch?: string
  failedRun?: boolean
  unsyncedAssets?: number
}>()

const emit = defineEmits<{ 'send-to-agent': [payload: string] }>()

const outstandingHtml = computed(() => {
  const parts: string[] = []
  if (props.failedRun) parts.push(`a failed run on \`${props.cell.slug}\``)
  if (props.unsyncedAssets) parts.push(formatCount(props.unsyncedAssets, 'unsynced asset'))
  if (parts.length === 0) return inlineCodeHtml('nothing left outstanding')
  return inlineCodeHtml(`outstanding: ${parts.join(' · ')}`)
})
</script>
