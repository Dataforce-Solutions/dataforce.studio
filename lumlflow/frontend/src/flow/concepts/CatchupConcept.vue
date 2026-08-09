<template>
  <!--
    Concept 3 — Catch-up first.

    The default surface is the diff, not the state. You cannot watch five agents,
    so the workspace opens on what changed while you were away, ranked and
    explained; the graph is a destination you dive into, not a thing you stare at.
    Nothing here gates the agents: this is post-hoc review, and the log keeps
    advancing behind the reader.
  -->
  <div class="p-4 space-y-3">
    <PlaybackBar :playback="playback" />

    <!-- Agent presence: who is where, and how much of the backlog is theirs. -->
    <section
      class="flex flex-wrap items-center gap-2 px-3 py-2 rounded border border-surface-200 dark:border-surface-700"
    >
      <span class="text-xs text-muted-color">live</span>
      <span
        v-for="presence in agentPresence"
        :key="presence.agentId"
        class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border border-surface-300 dark:border-surface-600"
        :title="`${presence.label} on ${presence.branchName} · ${presence.assetName}`"
      >
        <span
          class="w-2 h-2 rounded-full"
          :class="presence.working ? 'animate-pulse' : ''"
          :style="{ background: presence.color }"
        />
        {{ presence.label }}
        <span class="text-muted-color">{{ presence.branchName }}</span>
        <span v-if="presence.unseenCount" class="font-mono">+{{ presence.unseenCount }}</span>
      </span>
      <span class="ml-auto text-xs text-muted-color">
        agents are not blocked by this review — work lands, then you read it
      </span>
    </section>

    <!-- Return-from-away summary. The count is a door, not a badge. -->
    <section
      v-if="!open"
      class="rounded border border-primary-500 px-4 py-3 space-y-2"
    >
      <h3 class="font-medium">
        {{ unseenTransactions.length }} change{{ unseenTransactions.length === 1 ? '' : 's' }} since
        you looked away
      </h3>
      <p class="text-sm text-muted-color">
        {{ summary }}
      </p>
      <ul class="text-sm space-y-0.5">
        <li v-for="entry in previewEntries" :key="entry.key" class="text-muted-color">
          <span class="text-color">{{ entry.headline }}</span> —
          {{ entry.reasons[0]?.label }}
        </li>
      </ul>
      <div class="flex items-center gap-2">
        <button
          class="px-3 py-1 rounded border border-primary-500 text-primary-600 dark:text-primary-400 text-sm"
          @click="openCatchup"
        >
          Open catch-up diff
        </button>
        <button
          class="px-3 py-1 rounded border border-surface-300 dark:border-surface-600 text-sm"
          @click="playback.markSeen()"
        >
          dismiss without reading
        </button>
      </div>
    </section>

    <div v-else class="grid grid-cols-1 xl:grid-cols-[minmax(0,7fr)_minmax(0,9fr)] gap-4">
      <!-- The tour. -->
      <section class="space-y-2 min-w-0">
        <header class="space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="font-medium text-sm">
              Catch-up · {{ reviewedCount }}/{{ entries.length }} reviewed
            </h3>
            <div class="flex-1 h-1.5 rounded bg-surface-200 dark:bg-surface-700 min-w-24">
              <div
                class="h-full rounded bg-primary-500 transition-all"
                :style="{ width: `${entries.length ? (reviewedCount / entries.length) * 100 : 0}%` }"
              />
            </div>
            <button
              class="px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600 text-xs"
              @click="markAllCaughtUp"
            >
              mark all caught up
            </button>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-muted-color">reading order</span>
            <button
              v-for="mode in orderModes"
              :key="mode.id"
              class="px-2 py-0.5 rounded text-xs border"
              :class="
                order === mode.id
                  ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                  : 'border-surface-300 dark:border-surface-600 text-muted-color'
              "
              @click="order = mode.id"
            >
              {{ mode.label }}
            </button>
            <label class="ml-auto flex items-center gap-1.5 text-xs">
              <input v-model="hideReviewed" type="checkbox" />
              hide reviewed
            </label>
          </div>

          <p class="text-xs text-muted-color">{{ ordered.explanation }}</p>

          <button
            v-if="pendingCount"
            class="w-full px-3 py-1.5 rounded border border-amber-400 text-amber-700 dark:text-amber-400 text-xs text-left"
            @click="foldInPending"
          >
            {{ pendingCount }} more transaction{{ pendingCount === 1 ? '' : 's' }} landed while you
            were reading — the list did not reflow under you. Fold them in →
          </button>
        </header>

        <template v-if="ordered.readFirst.length">
          <p class="text-xs font-medium">
            Read first — failed, structurally rewired, or not comparable
          </p>
          <TourEntryCard
            v-for="entry in visible(ordered.readFirst)"
            :key="entry.key"
            :entry="entry"
            :session="session"
            :reviewed="reviewed.has(entry.key)"
            :selected="entry.key === selectedKey"
            @select="selectedKey = entry.key"
            @toggle-reviewed="toggleReviewed(entry.key)"
          />
        </template>

        <p v-if="ordered.readFirst.length && visible(ordered.rest).length" class="text-xs font-medium pt-1">
          Then, in dependency order
        </p>
        <TourEntryCard
          v-for="entry in visible(ordered.rest).slice(0, restLimit)"
          :key="entry.key"
          :entry="entry"
          :session="session"
          :reviewed="reviewed.has(entry.key)"
          :selected="entry.key === selectedKey"
          @select="selectedKey = entry.key"
          @toggle-reviewed="toggleReviewed(entry.key)"
        />

        <button
          v-if="visible(ordered.rest).length > restLimit"
          class="w-full px-2 py-1 rounded border border-surface-300 dark:border-surface-600 text-xs"
          @click="restLimit += 20"
        >
          show {{ Math.min(20, visible(ordered.rest).length - restLimit) }} more of
          {{ visible(ordered.rest).length }}
        </button>

        <p v-if="!entries.length" class="text-sm text-muted-color py-4">
          Nothing has landed since you marked yourself caught up. Press play, or reset and play, to
          let the agents work.
        </p>
      </section>

      <!-- The destination and the two things you do once you have read. -->
      <section class="min-w-0 space-y-3">
        <nav class="flex gap-1">
          <button
            v-for="tabId in tabs"
            :key="tabId"
            class="px-2.5 py-1 rounded text-xs border"
            :class="
              tab === tabId
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-surface-300 dark:border-surface-600 text-muted-color'
            "
            @click="tab = tabId"
          >
            {{ tabId }}
          </button>
          <span v-if="selected" class="ml-auto text-xs text-muted-color self-center truncate">
            {{ selected.headline }}
          </span>
        </nav>

        <p v-if="!selected" class="text-sm text-muted-color">
          Pick an entry on the left to open its assets.
        </p>

        <DestinationPane
          v-else-if="tab === 'assets'"
          :key="selected.key"
          :session="session"
          :entry="selected"
        />

        <template v-else-if="tab === 'compare'">
          <div class="flex flex-wrap gap-1.5">
            <label
              v-for="branch in allBranches"
              :key="branch.branchId"
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border cursor-pointer"
              :class="
                compareIds.includes(branch.branchId)
                  ? 'border-primary-500'
                  : 'border-surface-300 dark:border-surface-600 text-muted-color'
              "
            >
              <input
                type="checkbox"
                :checked="compareIds.includes(branch.branchId)"
                @change="toggleCompare(branch.branchId)"
              />
              <span class="w-1.5 h-1.5 rounded-full" :style="{ background: branch.color }" />
              {{ branch.name }}
            </label>
          </div>
          <p class="text-xs text-muted-color">
            {{ compareIds.length }} branches · {{ divergentCount }} assets differ
          </p>
          <DifferenceTable
            v-if="compareIds.length > 1"
            :key="compareIds.join()"
            :session="session"
            :branch-ids="compareIds"
          />
          <p v-else class="text-sm text-muted-color">Select at least two branches.</p>
        </template>

        <template v-else>
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-muted-color">freeze</span>
            <button
              v-for="branchId in selected.branchIds"
              :key="branchId"
              class="px-2 py-0.5 rounded text-xs border"
              :class="
                branchId === exportBranchId
                  ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                  : 'border-surface-300 dark:border-surface-600 text-muted-color'
              "
              @click="exportBranchId = branchId"
            >
              {{ session.branches[branchId]?.name ?? branchId }}
            </button>
          </div>
          <ExportPreview
            v-if="session.branches[exportBranchId]"
            :key="exportBranchId"
            :session="session"
            :branch-id="exportBranchId"
          />
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DifferenceTable from '../components/DifferenceTable.vue'
import ExportPreview from '../components/ExportPreview.vue'
import PlaybackBar from '../components/PlaybackBar.vue'
import { checkpoints } from '../engine'
import { usePlayback } from '../composables/usePlayback'
import { useWorkspace } from '../composables/useWorkspace'
import type { BranchId } from '../types'
import DestinationPane from './catchup/DestinationPane.vue'
import TourEntryCard from './catchup/TourEntryCard.vue'
import {
  buildTour,
  comparisonBranches,
  divergentAssetCount,
  orderTour,
  type ReadingOrder,
  type TourEntry,
} from './catchup/tour'

const { session: fixture } = useWorkspace()
const playback = usePlayback(fixture.value)

/**
 * Put the viewer in the state the concept is designed for: away since the last
 * settled checkpoint in the first stretch of the log, everything since then
 * unread. Without this the page opens caught-up and has nothing to say.
 */
const awayStep =
  checkpoints(fixture.value)
    .map((tx) => tx.step)
    .filter((step) => step <= playback.lastStep * 0.25)
    .pop() ?? 0
playback.seek(awayStep)
playback.markSeen()
playback.seek(playback.lastStep)

const session = computed(() => playback.session.value)

const open = ref(false)
const ceiling = ref(playback.lastStep)
const order = ref<ReadingOrder>('recommended')
const hideReviewed = ref(false)
const reviewed = ref(new Set<string>())
const selectedKey = ref<string | null>(null)
const restLimit = ref(20)
const tab = ref<'assets' | 'compare' | 'export'>('assets')
const compareIds = ref<BranchId[]>([])
const exportBranchId = ref<BranchId>(fixture.value.headBranchId)

const tabs = ['assets', 'compare', 'export'] as const
const orderModes: { id: ReadingOrder; label: string }[] = [
  { id: 'recommended', label: 'recommended' },
  { id: 'risk', label: 'review-worthiness' },
  { id: 'time', label: 'chronological' },
]

/** Frozen at the moment the reader opened the tour, so the list never reflows. */
const unseenTransactions = computed(() => playback.unseen.value)
const tourTransactions = computed(() =>
  unseenTransactions.value.filter((tx) => tx.step <= ceiling.value),
)
const pendingCount = computed(
  () => unseenTransactions.value.length - tourTransactions.value.length,
)

const entries = computed(() =>
  buildTour(session.value, tourTransactions.value, session.value.headBranchId),
)

const ordered = computed(() => orderTour(entries.value, order.value))

const visible = (list: TourEntry[]): TourEntry[] =>
  hideReviewed.value ? list.filter((entry) => !reviewed.value.has(entry.key)) : list

const previewEntries = computed(() =>
  orderTour(entries.value, 'risk').rest.slice(0, 3),
)

const summary = computed(() => {
  const agentIds = new Set(tourTransactions.value.map((tx) => tx.author))
  const branchIds = new Set(tourTransactions.value.map((tx) => tx.branchId))
  return `${entries.value.length} intents from ${agentIds.size} agents across ${branchIds.size} branches, coalesced from ${tourTransactions.value.length} transactions between step ${awayStep} and ${playback.step.value}.`
})

const reviewedCount = computed(
  () => entries.value.filter((entry) => reviewed.value.has(entry.key)).length,
)

const selected = computed<TourEntry | null>(
  () => entries.value.find((entry) => entry.key === selectedKey.value) ?? null,
)

const allBranches = computed(() => Object.values(session.value.branches))

const divergentCount = computed(() => divergentAssetCount(session.value, compareIds.value))

const agentPresence = computed(() =>
  Object.values(session.value.agents).map((agent) => ({
    agentId: agent.agentId,
    label: agent.label,
    color: agent.color,
    working: agent.activeBranchId !== null && agent.agentId !== 'human',
    branchName: session.value.branches[agent.activeBranchId ?? '']?.name ?? 'idle',
    assetName:
      Object.values(session.value.assets)
        .flat()
        .find((version) => version.assetId === agent.activeAssetId)?.definition.name ?? '—',
    unseenCount: tourTransactions.value.filter((tx) => tx.author === agent.agentId).length,
  })),
)

const openCatchup = (): void => {
  ceiling.value = playback.step.value
  open.value = true
  selectedKey.value = selectedKey.value ?? ordered.value.readFirst[0]?.key ?? ordered.value.rest[0]?.key ?? null
}

const foldInPending = (): void => {
  ceiling.value = playback.step.value
}

const toggleReviewed = (key: string): void => {
  const next = new Set(reviewed.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  reviewed.value = next
}

const markAllCaughtUp = (): void => {
  playback.markSeen()
  reviewed.value = new Set()
  selectedKey.value = null
  open.value = false
}

watch(
  selected,
  (entry) => {
    if (!entry) return
    compareIds.value = comparisonBranches(session.value, entry)
    exportBranchId.value = entry.branchIds[0] ?? session.value.headBranchId
  },
  { immediate: true },
)

const toggleCompare = (branchId: BranchId): void => {
  compareIds.value = compareIds.value.includes(branchId)
    ? compareIds.value.filter((id) => id !== branchId)
    : [...compareIds.value, branchId]
}
</script>
