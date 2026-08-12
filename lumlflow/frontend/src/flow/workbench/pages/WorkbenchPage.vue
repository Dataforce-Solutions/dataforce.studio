<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <DaemonDownBanner v-if="opsDisabled" />

    <WorkbenchTopBar
      v-model:view="view"
      :session="wb.session"
      :viewed-branch="viewedBranch"
      :branch-preflight="hasCells ? branchPreflight : null"
      :ops-disabled="opsDisabled"
      @rerun-branch="onRerunBranch"
      @stop-session="onStopSession"
      @open-catchup="onOpenCatchup"
    />

    <WorktreeLockNotice
      v-if="wb.variant === 'locked'"
      :holder="wb.session.paired?.label"
      @force="onForceWorktree"
    />

    <div class="flex min-h-0 flex-1 gap-3">
      <aside
        class="w-80 shrink-0 min-h-0 overflow-hidden rounded-lg border border-surface-200 dark:border-surface-700"
      >
        <LeftPanel
          :branches="wb.branches"
          :cells="slice"
          :viewed-branch="viewedBranch"
          :session="wb.session"
          :env="wb.env"
          :settings="settings"
          :journal="wb.journal"
          @open-graph="graphVisible = true"
          @select-cell="onSelectCell"
          @summarize-branch="onSummarizeBranch"
          @update-settings="onUpdateSettings"
        />
      </aside>

      <main class="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
        <!-- Pairing is detected, not declared: the panel flips on the journal event. -->
        <div v-if="wb.variant === 'unpaired' && hasCells" class="max-w-xl">
          <PairPanel />
        </div>

        <div
          v-if="hasStale"
          class="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm dark:border-amber-500/30 dark:bg-amber-500/10"
        >
          <TriangleAlert :size="14" class="shrink-0 text-amber-600 dark:text-amber-400" />
          <span v-if="directStale.length" class="text-amber-800 dark:text-amber-200">
            {{ directStale.length }} stale:
            <template v-for="(cell, index) in directStale" :key="cell.slug">
              <code class="font-mono text-[12px]">{{ cell.slug }}</code
              ><template v-if="index < directStale.length - 1">, </template>
            </template>
          </span>
          <span v-if="transitiveStale.length" class="text-amber-700/90 dark:text-amber-300/90">
            {{ directStale.length ? '· ' : '' }}{{ transitiveStale.length }} more downstream
          </span>
          <label
            v-if="transitiveStale.length"
            class="ml-auto flex cursor-pointer items-center gap-1.5 text-xs text-amber-800 dark:text-amber-200"
            :for="tintToggleId"
          >
            <ToggleSwitch v-model="showTint" :input-id="tintToggleId" />
            show downstream staleness
          </label>
          <KernelStartHint v-if="kernelHint" />
        </div>
        <div v-else-if="kernelHint" class="px-1">
          <KernelStartHint />
        </div>

        <div class="min-h-0 flex-1" :class="opsDisabled ? 'opacity-60' : ''">
          <EmptyFlowState
            v-if="!hasCells"
            @cheatsheet="onCheatsheet"
            @notebook="view = 'notebook'"
          />
          <FlowCanvas
            v-else-if="view === 'canvas'"
            class="h-full rounded-lg border border-surface-200 dark:border-surface-700"
            :cells="displayCells"
            :branch="viewedBranch"
            :selected-slug="selectedSlug"
            :tinted-slugs="tintedSlugs"
            :preflights="preflights"
            @select="onSelect"
            @expand="onExpand"
            @run="onRun"
            @stop="onStopCell"
            @rename="onRename"
            @delete="onDelete"
            @duplicate="onDuplicate"
            @navigate="onNavigate"
            @send-to-agent="onSendToAgent"
            @resolve-conflict="onResolveConflict"
            @edit="onEdit"
            @edit-params="onEditParams"
          />
          <NotebookColumn
            v-else
            :cells="displayCells"
            :branch="viewedBranch"
            :selected-slug="selectedSlug"
            :tinted-slugs="tintedSlugs"
            :preflights="preflights"
            @select="onSelect"
            @expand="onExpand"
            @run="onRun"
            @stop="onStopCell"
            @rename="onRename"
            @delete="onDelete"
            @duplicate="onDuplicate"
            @navigate="onNavigate"
            @send-to-agent="onSendToAgent"
            @resolve-conflict="onResolveConflict"
            @edit="onEdit"
            @edit-params="onEditParams"
          />
        </div>
      </main>
    </div>

    <BranchGraphOverlay
      v-model:visible="graphVisible"
      :branches="wb.branches"
      :worktree-locked="wb.session.worktreeLocked"
      @view="onGraphView"
      @checkout="onGraphCheckout"
      @archive="onGraphArchive"
      @compare="onGraphCompare"
    />

    <ExpandDrawer
      v-if="expandCell"
      v-model:visible="drawerVisible"
      :cell="expandCell"
      :kernel-started="kernelStarted"
    />

    <!-- The kernel-free tier ends here: expand is the first gesture that starts one. -->
    <Dialog
      v-model:visible="hintVisible"
      modal
      header="Start the kernel?"
      :style="{ width: '26rem' }"
    >
      <div class="flex flex-col gap-3">
        <p class="text-sm">
          Browsing works from stored previews — expanding
          <code class="font-mono">{{ expandSlug }}</code> into its full value is the first gesture
          that needs a kernel.
        </p>
        <KernelStartHint />
        <div class="flex justify-end gap-2 pt-1">
          <Button
            size="small"
            text
            severity="secondary"
            label="stay on previews"
            @click="hintVisible = false"
          />
          <Button size="small" label="expand — start the kernel" @click="confirmKernelStart" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dialog, ToggleSwitch } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { TriangleAlert } from 'lucide-vue-next'
import FlowCanvas from '../components/canvas/FlowCanvas.vue'
import ExpandDrawer from '../components/card/ExpandDrawer.vue'
import BranchGraphOverlay from '../components/graph/BranchGraphOverlay.vue'
import LeftPanel from '../components/panel/LeftPanel.vue'
import DaemonDownBanner from '../components/session/DaemonDownBanner.vue'
import KernelStartHint from '../components/session/KernelStartHint.vue'
import PairPanel from '../components/session/PairPanel.vue'
import WorktreeLockNotice from '../components/session/WorktreeLockNotice.vue'
import { evalPreflight } from '../fixtures'
import { formatCost, formatCount } from '../model/format'
import type { FlowCell, FlowSettings, ParamValue, Preflight } from '../model/types'
import EmptyFlowState from './EmptyFlowState.vue'
import NotebookColumn from './NotebookColumn.vue'
import WorkbenchTopBar from './WorkbenchTopBar.vue'
import { useWorkbenchState } from './useWorkbenchState'

/**
 * The workbench: one screen, two views. Left is the viewed branch and its
 * inventory; center is canvas or notebook over the SAME branch slice. View,
 * selection, and viewed branch live in the URL so links are shareable and the
 * two views can never disagree.
 */
const route = useRoute()
const router = useRouter()
const toast = useToast()

const wb = useWorkbenchState(route)

const opsDisabled = wb.variant === 'daemon-down'

// --- URL-synced selection ---------------------------------------------------

const view = ref<'canvas' | 'notebook'>(route.query.view === 'notebook' ? 'notebook' : 'canvas')
const selectedSlug = ref<string | null>(
  typeof route.query.asset === 'string' && route.query.asset ? route.query.asset : null,
)
const branchNames = new Set(wb.branches.map((branch) => branch.name))
const viewedBranch = ref(
  typeof route.query.branch === 'string' && branchNames.has(route.query.branch)
    ? route.query.branch
    : wb.session.worktreeBranch,
)

// FlowShell keys its RouterView on route.fullPath, so a router.replace would
// remount the whole page on every selection change (canvas refit, drawer
// close). The URL is mirrored with history.replaceState instead: same
// shareable links, no remount.
watch([view, selectedSlug, viewedBranch], () => {
  const params = new URLSearchParams()
  if (typeof route.query.state === 'string') params.set('state', route.query.state)
  if (view.value !== 'canvas') params.set('view', view.value)
  if (selectedSlug.value) params.set('asset', selectedSlug.value)
  if (viewedBranch.value !== wb.session.worktreeBranch) params.set('branch', viewedBranch.value)
  const search = params.toString()
  window.history.replaceState(
    window.history.state,
    '',
    `${route.path}${search ? `?${search}` : ''}`,
  )
})

// --- the viewed slice and its staleness -------------------------------------

const slice = computed<FlowCell[]>(() => wb.cellsByBranch[viewedBranch.value] ?? [])
const hasCells = computed(() => slice.value.length > 0)

const directStale = computed(() =>
  slice.value.filter((cell) => cell.stale && !cell.stale.transitive),
)
const transitiveStale = computed(() => slice.value.filter((cell) => cell.stale?.transitive))
const hasStale = computed(() => directStale.value.length > 0 || transitiveStale.value.length > 0)

const showTint = ref(false)
const tintToggleId = useId()

// Default OFF: transitive cells drop their stale chip; the header count keeps
// the staleness visible, so nothing is SILENTLY fresh-looking.
const displayCells = computed<FlowCell[]>(() => {
  if (showTint.value) return slice.value
  return slice.value.map((cell): FlowCell => {
    if (!cell.stale?.transitive) return cell
    return {
      ...cell,
      status: cell.status === 'stale' ? 'materialized' : cell.status,
      stale: undefined,
    }
  })
})

const tintedSlugs = computed<Set<string>>(() =>
  showTint.value ? new Set(transitiveStale.value.map((cell) => cell.slug)) : new Set(),
)

// --- preflights -------------------------------------------------------------

function cheapPreflightFor(cell: FlowCell): Preflight {
  const seconds = cell.timing?.costSeconds ?? 1
  return { cached: [], recompute: [{ slug: cell.slug, seconds }], totalSeconds: seconds }
}

const preflights = computed<Record<string, Preflight | undefined>>(() =>
  Object.fromEntries(
    slice.value.map((cell) => [
      cell.slug,
      cell.slug === 'train_model' ? evalPreflight : cheapPreflightFor(cell),
    ]),
  ),
)

/** Rerun-to-leaves batch, built from the stale cells' recorded timings. */
const branchPreflight = computed<Preflight | null>(() => {
  const cells = slice.value.filter((cell) => !cell.isNote)
  if (cells.length === 0) return null
  const needsRun = (cell: FlowCell): boolean =>
    Boolean(cell.stale) ||
    cell.status === 'stale' ||
    cell.status === 'unmaterialized' ||
    cell.status === 'failed'
  const recompute = cells
    .filter(needsRun)
    .map((cell) => ({ slug: cell.slug, seconds: cell.timing?.costSeconds ?? 1 }))
  return {
    cached: cells.filter((cell) => !needsRun(cell)).map((cell) => cell.slug),
    recompute,
    totalSeconds: recompute.reduce((sum, entry) => sum + entry.seconds, 0),
  }
})

// --- toasts: every op acknowledges, and daemon-down says why it cannot -------

function ack(
  summary: string,
  detail: string,
  severity: 'secondary' | 'info' | 'warn' = 'secondary',
): void {
  if (opsDisabled) {
    toast.add({
      severity: 'warn',
      summary: 'Daemon down',
      detail: 'nothing live to receive this op — showing last-known state',
      life: 3000,
    })
    return
  }
  toast.add({ severity, summary, detail, life: 3200 })
}

// --- selection and cross-navigation -----------------------------------------

function onSelect(slug: string): void {
  selectedSlug.value = slug
}

function onSelectCell(slug: string): void {
  selectedSlug.value = slug
}

function onNavigate(target: { view: 'canvas' | 'notebook'; slug: string }): void {
  selectedSlug.value = target.slug
  view.value = target.view
}

// --- expand and the kernel boundary -----------------------------------------

const expandSlug = ref<string | null>(null)
const drawerVisible = ref(false)
const hintVisible = ref(false)
const kernelStarted = ref(wb.variant !== 'kernel-not-started')

const expandCell = computed(
  () => slice.value.find((cell) => cell.slug === expandSlug.value) ?? null,
)

const kernelHint = computed(() => wb.variant === 'kernel-not-started' && !kernelStarted.value)

function onExpand(slug: string): void {
  expandSlug.value = slug
  if (!kernelStarted.value) {
    hintVisible.value = true
    return
  }
  drawerVisible.value = true
}

function confirmKernelStart(): void {
  hintVisible.value = false
  kernelStarted.value = true
  drawerVisible.value = true
  toast.add({
    severity: 'info',
    summary: 'Kernel starting',
    detail: 'previews never needed one — expand is the first gesture that does',
    life: 2500,
  })
}

// --- card ops ----------------------------------------------------------------

function onRun(slug: string, payload: { force: boolean }): void {
  const preflight = preflights.value[slug]
  const scope = preflight
    ? `${formatCount(preflight.recompute.length, 'cell')} · ~${formatCost(preflight.totalSeconds)}`
    : slug
  ack(
    `Run ${slug}`,
    payload.force ? `force rerun — memo ignored · ${scope}` : `minimal stale closure · ${scope}`,
    'info',
  )
}

function onStopCell(slug: string): void {
  ack(`Stop ${slug}`, 'cancels when no other awaiter still wants the result', 'info')
}

function onRename(slug: string): void {
  ack(`Rename ${slug}`, 'free — every reference rewires atomically, no cache or history touched')
}

function onDelete(slug: string): void {
  ack(
    `Deleted ${slug} from ${viewedBranch.value}`,
    'this branch’s selection only — other branches keep it; consumers here show a flagged reference',
  )
}

function onDuplicate(slug: string): void {
  ack(
    `Duplicated ${slug}`,
    'a fresh identity with no consumers — forking is usually the better move',
  )
}

function onSendToAgent(slug: string, payload: string): void {
  const label = wb.session.paired?.label
  if (label) {
    ack(
      `Handed to ${label}`,
      `context payload for ${slug} · ${formatCount(payload.split('\n').length, 'line')}`,
      'info',
    )
  } else {
    ack(
      'No agent paired',
      'copy the payload from the popover and paste it into your agent’s terminal',
      'warn',
    )
  }
}

function onResolveConflict(slug: string, choice: 'overwrite' | 'fork'): void {
  ack(
    choice === 'fork' ? `Forked your edit of ${slug}` : `Overwrote ${slug}`,
    choice === 'fork'
      ? 'your version lands on a fork; the moved head stays where the agent put it'
      : 'your version replaces the moved head — the agent’s edit stays in history',
    'info',
  )
}

function onEdit(slug: string): void {
  ack(
    `Edit of ${slug} saved to the store`,
    wb.session.worktreeLocked
      ? 'projection to files deferred — the agent holds the worktree'
      : 'projected to the worktree files',
    'info',
  )
}

function onEditParams(slug: string, params: Record<string, ParamValue>): void {
  ack(
    `Params-only version of ${slug}`,
    `${formatCount(Object.keys(params).length, 'param')} · marked stale, cause: definition changed`,
    'info',
  )
}

// --- session ops -------------------------------------------------------------

function onRerunBranch(payload: { force: boolean }): void {
  const preflight = branchPreflight.value
  if (!preflight) return
  ack(
    `Rerun ${viewedBranch.value}`,
    `runs the slice to its leaves — ${formatCount(preflight.recompute.length, 'recompute')}${
      payload.force ? ' plus every memo hit (force)' : ''
    } · ~${formatCost(preflight.totalSeconds)}${payload.force ? '+' : ''}`,
    'info',
  )
}

function onStopSession(): void {
  ack(
    'Session stopped',
    'in-flight run cancelled, queue drained — the agent in your terminal is untouched',
    'info',
  )
}

function onOpenCatchup(): void {
  const count = wb.session.changesBehind ?? 0
  ack(
    'Opening at the cursor',
    `${formatCount(count, 'change')} since you were here — the intent timeline in the left panel holds them`,
    'info',
  )
}

function onForceWorktree(): void {
  ack(
    'Worktree taken',
    'the agent loses its file view until it re-registers — its unsynced edits stay in the store',
    'warn',
  )
}

function onSummarizeBranch(): void {
  const label = wb.session.paired?.label
  ack(
    'Summarize this branch',
    label
      ? `branch payload handed to ${label} — it writes the note cell`
      : 'no agent paired — pair one and the payload is ready to hand over',
    label ? 'info' : 'warn',
  )
}

// --- settings ----------------------------------------------------------------

const settings = ref<FlowSettings>({ ...wb.settings })

function onUpdateSettings(next: FlowSettings): void {
  settings.value = next
  ack('Settings updated', 'reactivity and env-change policy are per-flow, stored by the daemon')
}

// --- branch graph ------------------------------------------------------------

const graphVisible = ref(false)

function onGraphView(name: string): void {
  viewedBranch.value = name
  if (!(wb.cellsByBranch[name] ?? []).some((cell) => cell.slug === selectedSlug.value)) {
    selectedSlug.value = null
  }
  graphVisible.value = false
}

function onGraphCheckout(name: string): void {
  if (wb.session.worktreeLocked) {
    ack(
      `Checkout of ${name} waits`,
      'the agent holds the worktree lock — checking out rebinds files, so it waits (or force)',
      'warn',
    )
    return
  }
  ack(`Would check out ${name}`, 'rebinds the single worktree’s files to this branch', 'info')
}

function onGraphArchive(name: string): void {
  ack(`Archived ${name}`, 'collapsed behind the archived toggle — nothing is deleted')
}

function onGraphCompare(): void {
  graphVisible.value = false
  void router.push('/flow/compare')
}

// --- fixture-only doors ------------------------------------------------------

function onCheatsheet(): void {
  toast.add({
    severity: 'secondary',
    summary: 'Fixture only',
    detail: 'AGENTS.md opens from the flow directory — no surface behind it in this draft',
    life: 2500,
  })
}
</script>
