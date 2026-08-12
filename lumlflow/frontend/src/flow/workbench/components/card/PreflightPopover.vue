<template>
  <Button
    v-tooltip.top="'run — computes the minimal stale closure'"
    text
    :rounded="!label"
    :severity="label ? undefined : 'secondary'"
    size="small"
    :label="label"
    aria-label="run"
    @click="popover?.toggle($event)"
  >
    <template #icon><Play :size="14" /></template>
  </Button>

  <Popover ref="popover">
    <div class="w-80 flex flex-col gap-3">
      <div>
        <p class="text-sm">
          run <code class="font-mono">{{ target }}</code>
        </p>
        <p class="text-xs text-muted-color mt-0.5">runs the minimal stale upstream closure</p>
      </div>

      <div v-if="preflight.cached.length" class="flex flex-col gap-1">
        <p class="text-[11px] uppercase tracking-wide text-muted-color">cached — not recomputed</p>
        <div class="flex flex-wrap gap-1.5">
          <code
            v-for="slug in preflight.cached"
            :key="slug"
            class="font-mono text-[11px] px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-800 text-muted-color"
          >
            {{ slug }}
          </code>
        </div>
      </div>

      <div class="flex flex-col gap-1">
        <p class="text-[11px] uppercase tracking-wide text-muted-color">recomputes</p>
        <div
          v-for="entry in preflight.recompute"
          :key="entry.slug"
          class="flex items-center justify-between gap-3"
        >
          <code class="font-mono text-xs">{{ entry.slug }}</code>
          <span class="text-xs text-muted-color">{{ formatCost(entry.seconds) }}</span>
        </div>
        <div
          class="flex items-center justify-between gap-3 border-t border-surface-200 dark:border-surface-700 pt-1 mt-0.5"
        >
          <span class="text-xs">total</span>
          <span class="text-xs font-medium">{{ formatCost(preflight.totalSeconds) }}</span>
        </div>
      </div>

      <label class="flex items-center gap-2 text-xs cursor-pointer" :for="forceId">
        <Checkbox v-model="force" :input-id="forceId" binary />
        <span>force rerun — ignore memo hits</span>
      </label>

      <Button size="small" :label="runLabel" class="w-full" @click="confirmRun" />
    </div>
  </Popover>
</template>

<script setup lang="ts">
import { computed, ref, useId, useTemplateRef } from 'vue'
import { Button, Checkbox, Popover } from 'primevue'
import { Play } from 'lucide-vue-next'
import { formatCost, formatCount } from '../../model/format'
import type { Preflight } from '../../model/types'

/**
 * Run never happens blind: the closure — what is cached, what recomputes, and
 * the total seconds — is on screen before the click. Force-rerun is a labeled
 * modifier, never the default.
 */
const props = defineProps<{
  preflight: Preflight
  target: string
  /** Optional trigger label; without it the trigger is an icon button. */
  label?: string
}>()

const emit = defineEmits<{ run: [payload: { force: boolean }] }>()

const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')
const force = ref(false)
const forceId = useId()

const runLabel = computed(() => {
  const { cached, recompute, totalSeconds } = props.preflight
  if (force.value && cached.length > 0) {
    // Memo hits recompute too; their cost is unknown, so the total is open-ended.
    return `run ${formatCount(recompute.length + cached.length, 'cell')} · ~${formatCost(totalSeconds)}+`
  }
  return `run ${formatCount(recompute.length, 'cell')} · ~${formatCost(totalSeconds)}`
})

function confirmRun(): void {
  emit('run', { force: force.value })
  force.value = false
  popover.value?.hide()
}
</script>
