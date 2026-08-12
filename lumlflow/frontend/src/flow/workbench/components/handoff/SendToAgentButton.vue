<template>
  <Button
    v-tooltip.top="label ? undefined : 'send to agent — builds the context payload'"
    text
    :rounded="!label"
    :severity="severity ?? 'secondary'"
    size="small"
    :label="label"
    aria-label="send to agent"
    @click="popover?.toggle($event)"
  >
    <template #icon><Send :size="14" /></template>
  </Button>

  <Popover ref="popover">
    <div class="w-96 flex flex-col gap-3">
      <p class="text-xs text-muted-color">
        {{ gestureLine }}
      </p>
      <pre
        class="font-mono text-[11px] leading-relaxed rounded-md border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 p-3 max-h-48 overflow-auto whitespace-pre"
        >{{ payload }}</pre
      >
      <CopyField :value="cliLine" />
      <div class="flex items-center justify-between gap-3">
        <p class="text-[11px] text-muted-color flex-1">
          the same payload is available to the agent over MCP
        </p>
        <Button size="small" label="hand off" @click="handOff" />
      </div>
    </div>
  </Popover>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Button, Popover } from 'primevue'
import { Send } from 'lucide-vue-next'
import type { FlowCell } from '../../model/types'
import CopyField from '../../ui/CopyField.vue'
import { buildHandoffPayload, type HandoffGesture } from './sendToAgent'

/**
 * The address the user never retypes: every card, error, and diff can hand the
 * agent a payload carrying slug, branch, step, and the error when present.
 */
const props = defineProps<{
  cell: FlowCell
  gesture?: HandoffGesture
  branch?: string
  /** With a label the trigger is a labeled button ("Fix this"); without, an icon. */
  label?: string
  severity?: string
}>()

const emit = defineEmits<{ 'send-to-agent': [payload: string] }>()

const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')

const gesture = computed<HandoffGesture>(() => props.gesture ?? 'explain')
const branch = computed(() => props.branch ?? 'main')

const payload = computed(() => buildHandoffPayload(props.cell, branch.value, gesture.value))

const cliLine = computed(
  () => `lumlflow agent prompt ${gesture.value} ${props.cell.slug} --branch ${branch.value}`,
)

const GESTURE_LINES: Record<HandoffGesture, string> = {
  fix: 'asks the agent to fix this cell — the payload carries the error and traceback',
  explain: 'asks the agent to explain this cell as it stands on this branch',
  improve: 'asks the agent to improve this cell — context first, no diagnosis implied',
}

const gestureLine = computed(() => GESTURE_LINES[gesture.value])

function handOff(): void {
  emit('send-to-agent', payload.value)
  popover.value?.hide()
}
</script>
