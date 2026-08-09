<template>
  <!--
    Concept 3 — Catch-up first.
    Owned by one prototype agent. See src/flow/README.md for the brief.
  -->
  <div class="p-4 space-y-3">
    <p class="text-sm text-muted-color">Concept 3 — not built yet.</p>
    <PlaybackBar :playback="playback" />
    <ul class="text-sm space-y-1">
      <li v-for="group in byIntent" :key="group.intent">
        <span class="font-medium">{{ group.intent }}</span>
        <span class="text-muted-color"> — {{ group.count }} transactions</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PlaybackBar from '../components/PlaybackBar.vue'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'

const { session } = useWorkspace()
const playback = usePlayback(session.value)

/** Grouping reads the intent string on each transaction — it is not inferable
 *  from the mutation ops alone, which is why the agent supplies it. */
const byIntent = computed(() => {
  const counts = new Map<string, number>()
  for (const tx of playback.session.value.transactions) {
    counts.set(tx.intent, (counts.get(tx.intent) ?? 0) + 1)
  }
  return [...counts.entries()].map(([intent, count]) => ({ intent, count }))
})
</script>
