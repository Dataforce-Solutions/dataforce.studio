<template>
  <!--
    The destination is deliberately thin: a topo-ordered list of the assets the
    entry touched plus everything below them. Concept 1 owns the rich canvas —
    this concept is betting that after a good tour you need to see the artifact
    and the source, and nothing else.
  -->
  <div class="space-y-3">
    <header class="space-y-2">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-muted-color">branch</span>
        <button
          v-for="branchId in entry.branchIds"
          :key="branchId"
          class="px-2 py-0.5 rounded text-xs border"
          :class="
            branchId === activeBranchId
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-surface-300 dark:border-surface-600 text-muted-color'
          "
          @click="activeBranchId = branchId"
        >
          {{ session.branches[branchId]?.name ?? branchId }}
        </button>
        <CostChip v-if="session.branches[activeBranchId]" :cost="cost" class="ml-auto" />
      </div>

      <CacheSkipBanner
        v-if="session.branches[activeBranchId]"
        :session="session"
        :branch-id="activeBranchId"
      />
    </header>

    <p class="text-xs text-muted-color">
      {{ rows.length }} assets in dependency order —
      {{ rows.filter((row) => row.direct).length }} touched directly, the rest downstream.
    </p>

    <ol class="space-y-2">
      <li
        v-for="row in visibleRows"
        :key="row.assetId"
        class="rounded border px-3 py-2"
        :class="
          row.direct
            ? 'border-surface-300 dark:border-surface-600'
            : 'border-dashed border-surface-200 dark:border-surface-800'
        "
      >
        <div class="flex items-baseline gap-2 flex-wrap">
          <h4 class="font-medium text-sm">{{ row.name }}</h4>
          <span class="font-mono text-xs text-muted-color">{{ row.versionTag }}</span>
          <span class="text-xs text-muted-color">{{ row.kind }}</span>
          <StatusBadges :cause="row.cause" />
          <span
            v-if="!row.direct"
            class="text-[11px] text-muted-color"
            title="Not edited by this entry — it sits below something that was."
          >
            downstream
          </span>
          <span
            v-if="row.failed"
            class="px-1.5 py-0.5 rounded text-[11px] border border-red-400 text-red-700 dark:text-red-400"
          >
            failed: {{ row.failureMessage }}
          </span>
          <button
            class="ml-auto text-xs px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600"
            @click="scratchAssetId = row.assetId"
          >
            scratch
          </button>
        </div>

        <p class="text-xs text-muted-color mt-0.5">{{ row.doc }}</p>

        <ArtifactView v-if="row.value" :value="row.value" class="mt-2" />

        <details class="mt-2">
          <summary class="text-xs text-muted-color cursor-pointer">
            source · authored by {{ session.agents[row.authoredBy]?.label ?? row.authoredBy }}
          </summary>

          <!--
            Where editing lives: in place, on the asset, as a takeover of the
            agent's definition. Nothing gates the agent; taking over forks so it
            keeps working while you type.
          -->
          <div class="mt-1">
            <textarea
              v-if="editingAssetId === row.assetId"
              class="w-full h-48 text-xs font-mono p-2 rounded bg-surface-100 dark:bg-surface-800"
              :value="row.source"
              readonly
            />
            <pre
              v-else
              class="text-xs p-2 rounded bg-surface-100 dark:bg-surface-800 overflow-x-auto"
            >{{ row.source }}</pre>

            <div class="flex flex-wrap items-center gap-2 mt-1.5">
              <button
                class="text-xs px-2 py-0.5 rounded border border-primary-500 text-primary-600 dark:text-primary-400"
                @click="editingAssetId = editingAssetId === row.assetId ? null : row.assetId"
              >
                {{ editingAssetId === row.assetId ? 'discard takeover' : 'take over this asset' }}
              </button>
              <template v-if="editingAssetId === row.assetId">
                <CostChip :cost="takeoverCost(row.assetId)" />
                <span class="text-xs text-muted-color">
                  writes {{ row.name }}@next on a fork of
                  {{ session.branches[activeBranchId]?.name ?? activeBranchId }} —
                  {{ session.agents[row.authoredBy]?.label ?? row.authoredBy }} keeps working on the
                  original.
                </span>
              </template>
            </div>
          </div>
        </details>
      </li>
    </ol>

    <button
      v-if="rows.length > visibleCount"
      class="text-xs px-2 py-1 rounded border border-surface-300 dark:border-surface-600"
      @click="visibleCount += 25"
    >
      show {{ Math.min(25, rows.length - visibleCount) }} more of {{ rows.length }}
    </button>

    <ScratchConsole :asset-name="scratchName" @promote="promote" />

    <div
      v-if="promoted.length"
      class="rounded border border-primary-400 px-3 py-2 text-xs space-y-1"
    >
      <p class="font-medium">Promoted to assets (pending materialization)</p>
      <div v-for="item in promoted" :key="item.expression" class="flex items-center gap-2">
        <span class="font-mono">{{ item.name }}</span>
        <span class="text-muted-color font-mono">{{ item.expression }}</span>
        <CostChip :cost="promotionCost" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ArtifactView from '../../components/ArtifactView.vue'
import CacheSkipBanner from '../../components/CacheSkipBanner.vue'
import CostChip from '../../components/CostChip.vue'
import ScratchConsole from '../../components/ScratchConsole.vue'
import StatusBadges from '../../components/StatusBadges.vue'
import { preflightCost, resolveSlice } from '../../engine'
import type { ArtifactValue, AssetId, BranchId, FlowSession, PreflightCost } from '../../types'
import { causesForBranch } from './staleness'
import { destinationAssets, type TourEntry } from './tour'

const props = defineProps<{ session: FlowSession; entry: TourEntry }>()

const activeBranchId = ref<BranchId>(props.entry.branchIds[0])
const editingAssetId = ref<AssetId | null>(null)
const scratchAssetId = ref<AssetId | null>(null)
const visibleCount = ref(25)
const promoted = ref<{ name: string; expression: string }[]>([])

watch(
  () => props.entry.key,
  () => {
    activeBranchId.value = props.entry.branchIds[0]
    editingAssetId.value = null
    scratchAssetId.value = null
    visibleCount.value = 25
  },
)

const slice = computed(() => resolveSlice(props.session, activeBranchId.value))
const causes = computed(() => causesForBranch(props.session, activeBranchId.value))
const cost = computed(() => preflightCost(props.session, activeBranchId.value))

const rows = computed(() =>
  destinationAssets(props.session, props.entry, activeBranchId.value)
    .map(({ assetId, direct }) => {
      const version = slice.value[assetId]
      if (!version) return null
      const materialization = props.session.materializations[version.versionId]
      const values = Object.values(materialization?.values ?? {})
      return {
        assetId,
        direct,
        name: version.definition.name,
        kind: version.definition.kind,
        doc: version.definition.doc,
        source: version.definition.source,
        authoredBy: version.authoredBy,
        versionTag: version.versionId.split('@')[1] ?? version.versionId,
        cause: causes.value[assetId] ?? null,
        failed: version.status === 'failed' || materialization?.state === 'failed',
        failureMessage: version.failureMessage ?? 'materialization failed',
        value: (values[0] as ArtifactValue | undefined) ?? null,
      }
    })
    .filter((row): row is NonNullable<typeof row> => row !== null),
)

const visibleRows = computed(() => rows.value.slice(0, visibleCount.value))

const scratchName = computed(() => {
  const assetId = scratchAssetId.value ?? rows.value[0]?.assetId
  return assetId ? (slice.value[assetId]?.definition.name ?? assetId) : 'nothing selected'
})

/** Taking over recomputes only what sits below the asset you edit. */
const takeoverCost = (assetId: AssetId): PreflightCost => {
  const full = preflightCost(props.session, activeBranchId.value)
  const version = slice.value[assetId]
  const seconds = props.session.materializations[version?.versionId ?? '']?.costSeconds ?? 0
  return { cachedAssetIds: full.cachedAssetIds, recomputeAssetIds: [assetId], totalSeconds: seconds }
}

const promotionCost = computed<PreflightCost>(() => ({
  cachedAssetIds: cost.value.cachedAssetIds,
  recomputeAssetIds: ['scratch'],
  totalSeconds: 2,
}))

const promote = (expression: string): void => {
  promoted.value.push({ name: `Scratch${promoted.value.length + 1}`, expression })
}
</script>
