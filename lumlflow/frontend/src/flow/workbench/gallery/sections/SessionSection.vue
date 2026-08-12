<template>
  <div class="flex flex-col gap-8 max-w-4xl">
    <GallerySpecimen
      title="Pair panel"
      caption="One direction only: the UI hands over the command, then detects the agent_begin transaction on the journal. Unpaired is a working state, not an error."
    >
      <div class="grid gap-4 sm:grid-cols-2">
        <PairPanel />
        <PairPanel :paired="session.paired" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Catch-up marker"
      caption="Reopening after an overnight run knows exactly how far behind it was — the cursor is durable. A marker, not an inbox: the reopen rule still lands on the active branch."
    >
      <CatchUpMarker :count="12" @open="onOpenAtCursor" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Journal feed"
      caption="Read-only activity over the journal: time, actor, intent, and a one-line summary with slugs in mono. Failed attempts fold into their repair; the offline window renders visibly coarse instead of posing as a normal burst."
    >
      <JournalFeed :entries="journal" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Daemon down"
      caption="Nothing live: last-known state is shown and marked stale, with the command to start the daemon — never a blank screen."
    >
      <DaemonDownBanner />
    </GallerySpecimen>

    <GallerySpecimen
      title="Socket reconnect"
      caption="A dropped socket is a latency event, never a data event: reconnect replays from the cursor, so the banner promises no refresh and no loss."
    >
      <SocketReconnectBanner />
    </GallerySpecimen>

    <GallerySpecimen
      title="Env mismatch"
      caption="The branch's lockfile differs from the live venv: restart under this branch's lock, and background work is deferred meanwhile — said out loud rather than looking idle."
    >
      <div class="max-w-lg">
        <EnvMismatchBanner @restart="onRestartKernel" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Worktree lock notice"
      caption="The one real lock: checkout, rewind and adopt wait while an agent session holds the worktree. UI edits still land in the store; projection to files is deferred."
    >
      <div class="max-w-xl">
        <WorktreeLockNotice holder="claude-1" @force="onForce" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Kernel start hint"
      caption="Every surface has a kernel-free tier. The hint rides next to expand, page, and diff affordances — the UI says so before it spins a kernel up."
    >
      <div class="flex items-center gap-3">
        <Button label="Expand full value" size="small" severity="secondary" outlined>
          <template #icon>
            <Maximize2 :size="13" />
          </template>
        </Button>
        <KernelStartHint />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Degraded states, enumerated"
      caption="A failure mode without a surface is a spinner that never resolves — every condition in ui-draft §10 has its surface."
    >
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr>
            <th :class="cellClass" class="font-medium w-1/3">Condition</th>
            <th :class="cellClass" class="font-medium">Surface</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="[condition, surface] in degradedStates" :key="condition">
            <td :class="cellClass">{{ condition }}</td>
            <td :class="cellClass" class="text-muted-color">{{ surface }}</td>
          </tr>
        </tbody>
      </table>
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import { useToast } from 'primevue/usetoast'
import CatchUpMarker from '../../components/session/CatchUpMarker.vue'
import DaemonDownBanner from '../../components/session/DaemonDownBanner.vue'
import EnvMismatchBanner from '../../components/session/EnvMismatchBanner.vue'
import JournalFeed from '../../components/session/JournalFeed.vue'
import KernelStartHint from '../../components/session/KernelStartHint.vue'
import PairPanel from '../../components/session/PairPanel.vue'
import SocketReconnectBanner from '../../components/session/SocketReconnectBanner.vue'
import WorktreeLockNotice from '../../components/session/WorktreeLockNotice.vue'
import { journal, session } from '../../fixtures'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

const cellClass = 'border border-surface-200 dark:border-surface-700 px-3 py-2 text-left align-top'

// ui-draft.md §10's condition→surface table, rendered so the enumeration itself is visible.
const degradedStates: [string, string][] = [
  ['Daemon down', 'Last-known session, read-only, marked stale, with the command to start it.'],
  [
    'Kernel not started',
    'Full browsing from previews. Expand/page/diff announce "this starts the kernel".',
  ],
  ['Socket dropped', 'Banner, auto-reconnect, cursor replay. No refresh, no loss.'],
  [
    'Worktree lock held by an agent',
    'Checkout, rewind, and adopt disabled with the reason and a force escape; UI edits still land, projection deferred.',
  ],
  [
    'Env mismatch on the viewed branch',
    'Header flag "env mismatch — restart under this branch\'s lock"; background work for that branch is deferred, and the UI says so rather than looking idle.',
  ],
  ['Value never persisted', 'Materialize and download with preflight, not a broken download.'],
  ['Irrecoverable rewind', 'Preflight declares it before the click, never after.'],
  [
    'Unknown preview/kind version',
    'Key-value fallback with an explicit "newer preview format" note.',
  ],
]

function onOpenAtCursor(): void {
  toast.add({
    severity: 'secondary',
    summary: 'open',
    detail: 'would open the transaction list at the cursor — still landing on the active branch',
    life: 2500,
  })
}

function onRestartKernel(): void {
  toast.add({
    severity: 'secondary',
    summary: 'restart',
    detail: "would restart the kernel under this branch's lock",
    life: 2500,
  })
}

function onForce(): void {
  toast.add({
    severity: 'secondary',
    summary: 'force',
    detail: 'would take the worktree from claude-1 — the agent loses its file view',
    life: 2500,
  })
}
</script>
