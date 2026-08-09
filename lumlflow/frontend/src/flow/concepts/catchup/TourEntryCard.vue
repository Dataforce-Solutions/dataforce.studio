<template>
  <article
    class="rounded border transition-colors"
    :class="[
      selected
        ? 'border-primary-500 bg-primary-50/40 dark:bg-primary-950/20'
        : 'border-surface-200 dark:border-surface-700 hover:border-surface-400 dark:hover:border-surface-500',
      reviewed ? 'opacity-55' : '',
    ]"
  >
    <button class="w-full text-left px-3 py-2" @click="emit('select')">
      <div class="flex items-start gap-2">
        <span
          class="mt-0.5 shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] text-white"
          :style="{ background: agentColor }"
          :title="`${agentLabel} · active on ${activeBranch}`"
        >
          {{ agentLabel.slice(0, 2) }}
        </span>

        <div class="min-w-0 flex-1">
          <p class="text-sm leading-snug">
            <span class="font-medium">{{ agentLabel }}</span>
            <span class="text-muted-color"> — </span>
            <span>{{ entry.intent }}</span>
            <span v-if="entry.rawIntents.length > 1" class="ml-1 text-xs text-muted-color">
              ({{ entry.rawIntents.length }} intents folded)
            </span>
          </p>
          <p class="text-xs text-muted-color mt-0.5">{{ entry.detail }}</p>

          <div class="flex flex-wrap items-center gap-1 mt-1.5">
            <span
              v-for="branchId in entry.branchIds"
              :key="branchId"
              class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] border border-surface-300 dark:border-surface-600"
            >
              <span
                class="w-1.5 h-1.5 rounded-full"
                :style="{ background: session.branches[branchId]?.color ?? '#94a3b8' }"
              />
              {{ session.branches[branchId]?.name ?? branchId }}
            </span>
            <span class="text-[11px] text-muted-color font-mono">
              steps {{ entry.firstStep }}–{{ entry.lastStep }}
            </span>
          </div>

          <!--
            Ranking reasons are the whole point: an ordered list the reader cannot
            audit is just another opinion, and the Lazy LGTM follows.
          -->
          <ul class="flex flex-wrap gap-1 mt-1.5">
            <li
              v-for="reason in entry.reasons.slice(0, 3)"
              :key="reason.code + reason.label"
              class="px-1.5 py-0.5 rounded text-[11px] border"
              :class="toneFor(reason.code)"
              :title="`+${Math.round(reason.points)} to review-worthiness`"
            >
              {{ reason.label }}
            </li>
          </ul>
        </div>

        <div class="shrink-0 text-right">
          <p class="text-xs font-mono" :class="entry.score >= 45 ? 'text-red-600 dark:text-red-400' : 'text-muted-color'">
            {{ Math.round(entry.score) }}
          </p>
          <p class="text-[10px] text-muted-color">rank</p>
        </div>
      </div>
    </button>

    <footer
      class="flex items-center gap-2 px-3 py-1.5 border-t border-surface-100 dark:border-surface-800 text-xs"
    >
      <label class="flex items-center gap-1.5 cursor-pointer">
        <input
          type="checkbox"
          :checked="reviewed"
          @change="emit('toggle-reviewed')"
        />
        reviewed
      </label>
      <span v-if="entry.structuralNotes.length" class="text-muted-color truncate">
        {{ entry.structuralNotes.join(' · ') }}
      </span>
      <button
        class="ml-auto px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600"
        @click="emit('select')"
      >
        open {{ entry.touches.length }} asset{{ entry.touches.length === 1 ? '' : 's' }} →
      </button>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FlowSession } from '../../types'
import type { ReasonCode, TourEntry } from './tour'

const props = defineProps<{
  entry: TourEntry
  session: FlowSession
  reviewed: boolean
  selected: boolean
}>()

const emit = defineEmits<{ select: []; 'toggle-reviewed': [] }>()

const agent = computed(() => props.session.agents[props.entry.author])
const agentLabel = computed(() => agent.value?.label ?? props.entry.author)
const agentColor = computed(() => agent.value?.color ?? '#64748b')
const activeBranch = computed(
  () => props.session.branches[agent.value?.activeBranchId ?? '']?.name ?? 'idle',
)

const toneFor = (code: ReasonCode): string => {
  switch (code) {
    case 'failure':
      return 'border-red-400 text-red-700 dark:text-red-400'
    case 'integrity':
      return 'border-red-400 text-red-700 dark:text-red-400'
    case 'structural':
      return 'border-amber-400 text-amber-700 dark:text-amber-400'
    case 'metric-moved':
      return 'border-emerald-400 text-emerald-700 dark:text-emerald-400'
    case 'blast-radius':
      return 'border-surface-300 dark:border-surface-600 text-muted-color'
    default:
      return 'border-surface-200 dark:border-surface-700 text-muted-color'
  }
}
</script>
