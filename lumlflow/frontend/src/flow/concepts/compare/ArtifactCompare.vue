<template>
  <section class="border border-surface-300 dark:border-surface-600 rounded p-3">
    <header class="flex flex-wrap items-center gap-3 mb-3">
      <h3 class="font-medium text-sm">Results side by side</h3>

      <label class="text-xs text-muted-color flex items-center gap-1">
        asset
        <select
          v-model="focusAssetId"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-1 py-0.5 text-xs"
          @change="pinned = true"
        >
          <option v-for="option in assetOptions" :key="option.assetId" :value="option.assetId">
            {{ option.name }}
          </option>
        </select>
      </label>

      <label class="text-xs text-muted-color flex items-center gap-1">
        compare
        <select
          v-model="mode"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-1 py-0.5 text-xs"
        >
          <option value="baseline">with baseline</option>
          <option value="previous">with previous column</option>
        </select>
      </label>

      <label class="text-xs text-muted-color flex items-center gap-1">
        baseline
        <select
          :value="baselineId"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-1 py-0.5 text-xs"
          @change="emit('update:baselineId', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="branchId in branchIds" :key="branchId" :value="branchId">
            {{ session.branches[branchId]?.name ?? branchId }}
          </option>
        </select>
      </label>
    </header>

    <IntegrityWarnings :warnings="warnings" />

    <table v-if="rows.length" class="w-full text-sm text-left border-collapse mb-4">
      <thead>
        <tr class="border-b border-surface-200 dark:border-surface-700">
          <th class="py-1.5 pr-4 font-medium">metric</th>
          <th
            v-for="branchId in branchIds"
            :key="branchId"
            class="py-1.5 pr-4 font-medium whitespace-nowrap"
          >
            <span
              class="inline-block w-2 h-2 rounded-full mr-1.5"
              :style="{ background: session.branches[branchId]?.color }"
            />
            {{ session.branches[branchId]?.name ?? branchId }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.name"
          class="border-b border-surface-100 dark:border-surface-800"
        >
          <td class="py-1.5 pr-4 whitespace-nowrap">
            {{ row.name }}
            <span class="text-xs text-muted-color">
              {{ row.higherIsBetter ? '↑ better' : '↓ better' }}
            </span>
          </td>
          <td
            v-for="branchId in branchIds"
            :key="branchId"
            class="py-1.5 pr-4 whitespace-nowrap tabular-nums"
          >
            <template v-if="row.byBranch[branchId] !== null">
              {{ row.byBranch[branchId]?.toFixed(4) }}
              <span
                v-if="signedDelta(row, branchId)"
                class="ml-1 text-xs"
                :class="deltaTone(row, branchId)"
              >
                {{ formatDelta(signedDelta(row, branchId)?.value ?? 0) }}
              </span>
              <span v-else-if="branchId !== referenceFor(branchId)" class="ml-1 text-xs text-muted-color">
                —
              </span>
            </template>
            <span v-else class="text-muted-color">absent</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="grid gap-3" :style="{ gridTemplateColumns: `repeat(${branchIds.length}, minmax(14rem, 1fr))` }">
      <div
        v-for="branchId in branchIds"
        :key="branchId"
        class="border rounded p-2 min-w-0"
        :class="
          branchId === baselineId
            ? 'border-primary-400'
            : 'border-surface-200 dark:border-surface-700'
        "
      >
        <p class="text-xs mb-1.5 flex items-center gap-1.5">
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :style="{ background: session.branches[branchId]?.color }"
          />
          <span class="truncate">{{ session.branches[branchId]?.name ?? branchId }}</span>
          <span v-if="branchId === baselineId" class="text-muted-color">baseline</span>
        </p>
        <p class="text-xs text-muted-color mb-1.5 font-mono">{{ versionTag(branchId) }}</p>
        <ArtifactView v-if="valueFor(branchId)" :value="valueFor(branchId) as ArtifactValue" />
        <p v-else class="text-sm text-muted-color">
          absent in this variant
        </p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ArtifactView from '../../components/ArtifactView.vue'
import IntegrityWarnings from '../../components/IntegrityWarnings.vue'
import { integrityWarnings, resolveSlice, topoOrder } from '../../engine'
import { deltaOf, metricRows, type MetricRow } from './metrics'
import type { ArtifactValue, AssetId, BranchId, FlowSession } from '../../types'

/**
 * Pane (b): the values themselves, with direction-aware deltas.
 *
 * "Compare with baseline" answers *is this variant better than the thing we
 * ship*; "compare with previous" answers *did the last change help*. They are
 * different questions and a single hardcoded reference silently picks one.
 */
const props = defineProps<{
  session: FlowSession
  branchIds: BranchId[]
  baselineId: BranchId
}>()

const emit = defineEmits<{ 'update:baselineId': [value: BranchId] }>()

const mode = ref<'baseline' | 'previous'>('baseline')
const focusAssetId = ref<AssetId | ''>('')
const pinned = ref(false)

const slices = computed(() =>
  Object.fromEntries(props.branchIds.map((id) => [id, resolveSlice(props.session, id)])),
)

const assetOptions = computed(() => {
  const seen = new Map<AssetId, string>()
  for (const branchId of props.branchIds) {
    for (const assetId of topoOrder(props.session, branchId)) {
      const version = slices.value[branchId]?.[assetId]
      const materialization = version && props.session.materializations[version.versionId]
      if (!version || !materialization || !Object.keys(materialization.values).length) continue
      seen.set(assetId, version.definition.name)
    }
  }
  return [...seen.entries()].map(([assetId, name]) => ({ assetId, name }))
})

/** Default to the asset the comparison is actually about: the terminal result. */
const preferredAssetId = computed(() => {
  const ranked = ['eval', 'metric', 'experiment', 'note']
  for (const kind of ranked) {
    for (const option of assetOptions.value) {
      const version = props.branchIds
        .map((branchId) => slices.value[branchId]?.[option.assetId])
        .find(Boolean)
      if (version?.definition.kind === kind) return option.assetId
    }
  }
  return assetOptions.value.at(-1)?.assetId ?? ''
})

// Until the human picks an asset, follow the terminal result: during playback the
// terminal result *moves* as the graph grows, and a focus pinned at whatever
// existed on step 3 leaves this pane showing the raw frame for the rest of the run.
watch(
  [assetOptions, preferredAssetId],
  () => {
    const stillPresent = assetOptions.value.some((option) => option.assetId === focusAssetId.value)
    if (!pinned.value || !stillPresent) focusAssetId.value = preferredAssetId.value
  },
  { immediate: true },
)

const warnings = computed(() => integrityWarnings(props.session, props.branchIds))
const rows = computed(() => metricRows(props.session, props.branchIds))

const referenceFor = (branchId: BranchId): BranchId => {
  if (mode.value === 'baseline') return props.baselineId
  const index = props.branchIds.indexOf(branchId)
  return index > 0 ? props.branchIds[index - 1] : branchId
}

const signedDelta = (row: MetricRow, branchId: BranchId) => {
  const reference = referenceFor(branchId)
  if (reference === branchId) return null
  return deltaOf(row, branchId, reference)
}

/** An exact tie is not good news; colouring it green would flatter every sweep. */
const formatDelta = (value: number): string =>
  value === 0 ? 'no change' : `${value > 0 ? '+' : ''}${value.toFixed(4)}`

const deltaTone = (row: MetricRow, branchId: BranchId): string => {
  const delta = signedDelta(row, branchId)
  if (!delta || delta.value === 0) return 'text-muted-color'
  return delta.favourable
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-600 dark:text-red-400'
}

const versionFor = (branchId: BranchId) =>
  focusAssetId.value ? slices.value[branchId]?.[focusAssetId.value] : undefined

const versionTag = (branchId: BranchId): string => {
  const version = versionFor(branchId)
  return version ? version.versionId : '—'
}

const valueFor = (branchId: BranchId): ArtifactValue | null => {
  const version = versionFor(branchId)
  if (!version) return null
  const values = props.session.materializations[version.versionId]?.values ?? {}
  return (Object.values(values)[0] as ArtifactValue | undefined) ?? null
}
</script>
