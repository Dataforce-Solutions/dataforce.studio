<template>
  <section class="border border-surface-300 dark:border-surface-600 rounded p-3 space-y-3">
    <header class="flex flex-wrap items-center gap-2">
      <h3 class="font-medium text-sm">The committed path</h3>
      <span
        class="px-1.5 py-0.5 rounded text-xs border"
        :class="
          isNovel
            ? 'border-amber-400 text-amber-700 dark:text-amber-400'
            : 'border-surface-300 dark:border-surface-600 text-muted-color'
        "
      >
        {{ isNovel ? 'novel slice — no branch ran this' : `identical to ${matchingName}` }}
      </span>
      <CostChip :cost="cost" />
    </header>

    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span class="text-muted-color">pick winner</span>
      <button
        v-for="branchId in branchIds"
        :key="branchId"
        class="px-2 py-0.5 rounded border flex items-center gap-1.5"
        :class="
          branchId === pathSeed
            ? 'border-primary-500 text-primary-600 dark:text-primary-400'
            : 'border-surface-300 dark:border-surface-600 text-muted-color'
        "
        @click="emit('seed', branchId)"
      >
        <span
          class="w-1.5 h-1.5 rounded-full"
          :style="{ background: session.branches[branchId]?.color }"
        />
        {{ session.branches[branchId]?.name ?? branchId }}
      </button>
      <button
        class="ml-auto px-2 py-0.5 rounded border border-primary-500 text-primary-600 dark:text-primary-400 disabled:opacity-40"
        :disabled="conflicts.length > 0"
        :title="
          conflicts.length
            ? 'Resolve the interface conflicts before freezing this slice.'
            : 'Freeze this slice as an artifact.'
        "
        @click="emit('export')"
      >
        export this path
      </button>
    </div>

    <div v-if="conflicts.length" class="rounded border border-red-500 bg-red-50 dark:bg-red-950/20 px-3 py-2">
      <p class="text-sm font-medium text-red-800 dark:text-red-300 mb-1">
        {{ conflicts.length }} interface conflict{{ conflicts.length === 1 ? '' : 's' }}
      </p>
      <ul class="text-sm text-red-700 dark:text-red-300 space-y-0.5">
        <li v-for="(conflict, index) in conflicts" :key="index">{{ conflict.message }}</li>
      </ul>
      <p class="text-xs text-red-700/80 dark:text-red-300/80 mt-1">
        Cherry-picking composes a slice nobody ran. This one does not type-check against itself.
      </p>
    </div>

    <ul class="text-sm space-y-1">
      <li
        v-for="entry in visibleEntries"
        :key="entry.assetId"
        class="flex items-center gap-2 flex-wrap"
      >
        <span
          class="w-1.5 h-1.5 rounded-full shrink-0"
          :style="{ background: session.agents[entry.author]?.color ?? '#94a3b8' }"
          :title="`authored by ${session.agents[entry.author]?.label ?? entry.author}`"
        />
        <span>{{ entry.name }}</span>
        <span class="font-mono text-xs text-muted-color">{{ entry.tag }}</span>
        <StatusBadges :cause="unsyncedCause(entry.assetId)" />
        <span
          v-if="entry.fromBranchId && entry.fromBranchId !== pathSeed"
          class="text-xs text-muted-color"
        >
          cherry-picked from {{ session.branches[entry.fromBranchId]?.name }}
        </span>
      </li>
    </ul>

    <p class="text-xs text-muted-color">
      <template v-if="entries.length > visibleEntries.length">
        +{{ entries.length - visibleEntries.length }} more assets differ only in value.
      </template>
      <template v-if="sharedCount">
        {{ sharedCount }} further assets are identical in every variant and are carried through
        unchanged.
      </template>
    </p>

    <!--
      Where editing lives. Not a file tree and not a notebook: a version at a fan
      point, opened from the graph, read-only until you take over from the agent
      that wrote it. Editing here would author a new version and widen this fan.
    -->
    <div v-if="inspected" class="border-t border-surface-200 dark:border-surface-700 pt-3">
      <div class="flex items-center gap-2 mb-1">
        <h4 class="text-sm font-medium">{{ inspected.definition.name }}</h4>
        <span class="font-mono text-xs text-muted-color">{{ inspected.versionId }}</span>
        <span class="text-xs text-muted-color">
          written by {{ session.agents[inspected.authoredBy]?.label ?? inspected.authoredBy }}
        </span>
        <button
          class="ml-auto px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600 text-xs opacity-60"
          disabled
          title="Prototype: editing is not wired. In the product this detaches the agent from this asset and opens the definition in your editor against the live kernel."
        >
          take over
        </button>
      </div>
      <p class="text-xs text-muted-color mb-1">{{ inspected.intent }}</p>
      <p v-if="inspected.failureMessage" class="text-xs text-red-600 dark:text-red-400 mb-1">
        {{ inspected.failureMessage }}
      </p>
      <pre class="text-xs p-2 rounded bg-surface-100 dark:bg-surface-800 overflow-x-auto">{{ inspected.definition.source }}</pre>
      <p class="text-xs text-muted-color mt-1">
        Read-only. Saving an edit here authors a new version and adds a variant to this fan — it
        does not overwrite what the agent produced.
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CostChip from '../../components/CostChip.vue'
import StatusBadges from '../../components/StatusBadges.vue'
import { ABSENT, type ComposedPath, type FanNode, type PathConflict } from './useComparison'
import type { AssetId, AssetVersion, BranchId, FlowSession, PreflightCost, UnsyncedCause } from '../../types'

const props = defineProps<{
  session: FlowSession
  branchIds: BranchId[]
  nodes: FanNode[]
  path: ComposedPath
  pathSeed: BranchId
  isNovel: boolean
  matchingBranchId: BranchId | null
  conflicts: PathConflict[]
  cost: PreflightCost
  unsyncedCause: (assetId: AssetId) => UnsyncedCause | null
  inspectedAssetId: AssetId | null
  sharedCount: number
}>()

const emit = defineEmits<{ seed: [branchId: BranchId]; export: [] }>()

const MAX_ENTRIES = 14

const matchingName = computed(
  () => props.session.branches[props.matchingBranchId ?? '']?.name ?? 'an existing branch',
)

const versionOf = (assetId: AssetId): AssetVersion | null => {
  const versionId = props.path[assetId]
  if (!versionId || versionId === ABSENT) return null
  return (props.session.assets[assetId] ?? []).find((v) => v.versionId === versionId) ?? null
}

/** Only the assets that actually vary — the rest is summarised as a count. */
const entries = computed(() =>
  props.nodes.map((node) => {
    const version = versionOf(node.assetId)
    const variant = node.variants.find((item) => item.key === props.path[node.assetId])
    return {
      assetId: node.assetId,
      name: version?.definition.name ?? node.name,
      tag: version ? (version.versionId.split('@')[1] ?? version.versionId) : 'absent',
      author: version?.authoredBy ?? 'human',
      fromBranchId: variant?.branchIds[0] ?? null,
    }
  }),
)

/** Fan points always survive truncation; value-only assets are dropped first. */
const visibleEntries = computed(() => {
  if (entries.value.length <= MAX_ENTRIES) return entries.value
  const fanAssetIds = new Set(
    props.nodes.filter((node) => node.kind === 'definition').map((node) => node.assetId),
  )
  let budget = MAX_ENTRIES - fanAssetIds.size
  return entries.value.filter((entry) => {
    if (fanAssetIds.has(entry.assetId)) return true
    if (budget <= 0) return false
    budget -= 1
    return true
  })
})

const inspected = computed(() =>
  props.inspectedAssetId ? versionOf(props.inspectedAssetId) : null,
)
</script>
