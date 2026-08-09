<template>
  <!--
    Concept 1 — Canvas + focused railroad.
    Owned by one prototype agent. See src/flow/README.md for the brief.
  -->
  <div class="p-4 space-y-3">
    <p class="text-sm text-muted-color">Concept 1 — not built yet.</p>
    <PlaybackBar :playback="playback" />
    <CacheSkipBanner :session="playback.session.value" :branch-id="branchId" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CacheSkipBanner from '../components/CacheSkipBanner.vue'
import PlaybackBar from '../components/PlaybackBar.vue'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'

const { session } = useWorkspace()
const playback = usePlayback(session.value)
const branchId = computed(() => playback.session.value.headBranchId)
</script>
