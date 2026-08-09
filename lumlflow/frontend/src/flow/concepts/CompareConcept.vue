<template>
  <!--
    Concept 2 — Compare & compose workspace.
    Owned by one prototype agent. See src/flow/README.md for the brief.
  -->
  <div class="p-4 space-y-4">
    <p class="text-sm text-muted-color">Concept 2 — not built yet.</p>
    <DifferenceTable :session="session" :branch-ids="branchIds" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DifferenceTable from '../components/DifferenceTable.vue'
import { useWorkspace } from '../composables/useWorkspace'

const { session } = useWorkspace()

const branchIds = computed(() => Object.keys(session.value.branches).slice(0, 4))
</script>
