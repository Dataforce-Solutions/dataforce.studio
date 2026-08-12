<template>
  <div class="flex items-center gap-x-2 gap-y-1 flex-wrap text-xs text-muted-color min-w-0">
    <span class="shrink-0">created</span>
    <ActorChip :actor="provenance.createdBy" muted />
    <span>·</span>
    <span class="shrink-0">last edit</span>
    <ActorChip
      :actor="provenance.lastEditedBy"
      :uncertain="provenance.attributionUncertain"
      muted
    />
    <span>·</span>
    <em class="italic truncate max-w-64">“{{ provenance.intent }}”</em>
    <span>·</span>
    <span class="shrink-0">step {{ provenance.step }}</span>
    <template v-if="repairedLine">
      <span>·</span>
      <span class="inline-flex items-center gap-1 shrink-0">
        <History :size="11" />
        {{ repairedLine }}
      </span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { History } from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { ProvenanceInfo } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'

/**
 * Version authorship as recorded, plus the folded repair history: an
 * agent-authored failure repaired by the same author collapses into one line
 * rather than interrupting anyone.
 */
const props = defineProps<{
  provenance: ProvenanceInfo
  repairedAttempts?: number
}>()

// Version numbers are not in the view model yet; the fold derives a plausible
// pair so the gallery renders the contract's exact line shape.
const repairedLine = computed(() => {
  const attempts = props.repairedAttempts
  if (!attempts) return ''
  return `v${attempts + 2}→v${attempts + 3} · ${formatCount(attempts, 'failed attempt')}`
})
</script>
