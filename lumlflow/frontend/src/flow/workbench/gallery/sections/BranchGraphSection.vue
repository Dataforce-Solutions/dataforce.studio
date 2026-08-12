<template>
  <div class="flex flex-col gap-8 max-w-4xl">
    <GallerySpecimen
      title="The fork tree"
      caption="One lane per branch, x is the journal step, a curve from the parent lane at the fork step. Each row carries the head state, last intent, headline metric, and who is on it. Archived branches collapse behind the toggle."
    >
      <BranchGraph
        :branches="branches"
        @view="onView"
        @checkout="onCheckout(false, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Selection mode"
      caption="Checkboxes replace the verbs; the compare CTA arms at 2–5 selections and names the count."
    >
      <BranchGraph
        :branches="branches"
        selectable
        @view="onView"
        @checkout="onCheckout(false, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Locked checkout"
      caption="View stays available for every branch — a pure store read. Check out waits on the agent's worktree lock: disabled with the reason, plus the labeled force escape."
    >
      <BranchGraph
        :branches="branches"
        worktree-locked
        @view="onView"
        @checkout="onCheckout(true, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="The overlay"
      caption="The graph wrapped in a modal dialog — the disclosure behind the branch identifier. Topology is consulted at decision points, not watched."
    >
      <Button label="Open branch graph" size="small" outlined @click="overlayVisible = true">
        <template #icon>
          <GitFork :size="13" />
        </template>
      </Button>
      <BranchGraphOverlay
        v-model:visible="overlayVisible"
        :branches="branches"
        :worktree-locked="true"
        @view="onView"
        @checkout="onCheckout(true, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from 'primevue'
import { GitFork } from 'lucide-vue-next'
import { useToast } from 'primevue/usetoast'
import BranchGraph from '../../components/graph/BranchGraph.vue'
import BranchGraphOverlay from '../../components/graph/BranchGraphOverlay.vue'
import { branches } from '../../fixtures'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

const overlayVisible = ref(false)

function onView(name: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'view',
    detail: `would view \`${name}\` — a pure store read, no lock, no kernel`,
    life: 2500,
  })
}

function onCheckout(locked: boolean, name: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'checkout',
    detail: locked
      ? `would check out \`${name}\` — waits on the agent's worktree lock`
      : `would check out \`${name}\` — rebinds the worktree files`,
    life: 2500,
  })
}

function onArchive(name: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'archive',
    detail: `would archive \`${name}\``,
    life: 2500,
  })
}

function onCompare(names: string[]): void {
  toast.add({
    severity: 'secondary',
    summary: 'compare',
    detail: `would compare ${names.map((name) => `\`${name}\``).join(' · ')}`,
    life: 2500,
  })
}
</script>
