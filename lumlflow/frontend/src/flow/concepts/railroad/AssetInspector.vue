<template>
  <div class="h-full flex flex-col border-l border-surface-200 dark:border-surface-700">
    <div v-if="!version" class="p-3 text-sm text-muted-color">
      Select a node on the canvas. Editing lives here, in this panel — nodes never expand, because a
      node that grows is a node that moves everything else.
    </div>

    <template v-else>
      <div class="px-3 py-2 border-b border-surface-200 dark:border-surface-700">
        <div class="flex items-center gap-2">
          <h3 class="font-medium text-sm truncate">{{ version.definition.name }}</h3>
          <span class="font-mono text-[10px] text-muted-color">{{ versionTag }}</span>
          <span class="ml-auto text-[10px] text-muted-color">{{ version.definition.kind }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-1.5 mt-1">
          <span
            class="px-1 rounded text-[10px] text-white"
            :style="{ background: session.agents[version.authoredBy]?.color ?? '#64748b' }"
          >
            {{ session.agents[version.authoredBy]?.label ?? version.authoredBy }}
          </span>
          <span class="text-[10px] text-muted-color truncate">{{ version.intent }}</span>
          <StatusBadges :cause="cause" />
        </div>
        <p
          v-if="version.status === 'failed'"
          class="mt-1.5 px-2 py-1 rounded border border-red-400 text-red-700 dark:text-red-400 text-[11px] font-mono"
        >
          {{ version.failureMessage }}
        </p>
      </div>

      <div class="flex-1 min-h-0 overflow-y-auto p-3 space-y-4">
        <section>
          <div class="flex items-center gap-2 mb-1">
            <h4 class="text-xs font-medium">definition</h4>
            <span class="text-[10px] text-muted-color">
              {{ editing ? 'you have taken over' : 'written by agents · read-only' }}
            </span>
            <button
              class="ml-auto px-1.5 py-0.5 rounded border text-[11px]"
              :class="
                editing
                  ? 'border-surface-300 dark:border-surface-600 text-muted-color'
                  : 'border-primary-500 text-primary-600 dark:text-primary-400'
              "
              @click="editing = !editing"
            >
              {{ editing ? 'discard' : 'take over' }}
            </button>
          </div>

          <textarea
            v-if="editing"
            v-model="draft"
            rows="12"
            class="w-full font-mono text-[11px] p-2 rounded border border-primary-500 bg-transparent"
          />
          <pre
            v-else
            class="text-[11px] font-mono p-2 rounded bg-surface-100 dark:bg-surface-800 overflow-x-auto"
            >{{ version.definition.source }}</pre
          >

          <div
            v-if="editing"
            class="mt-1.5 flex flex-wrap items-center gap-2 px-2 py-1.5 rounded border border-surface-300 dark:border-surface-600"
          >
            <span class="text-[11px]">committing writes a new version on {{ branchName }}</span>
            <CostChip :cost="editCost" />
          </div>
        </section>

        <section v-if="artifact">
          <h4 class="text-xs font-medium mb-1">materialization</h4>
          <ArtifactView :value="artifact" />
        </section>

        <section>
          <h4 class="text-xs font-medium mb-1">versions of this asset</h4>
          <ul class="space-y-1">
            <li
              v-for="candidate in history"
              :key="candidate.versionId"
              class="flex items-start gap-1.5 text-[11px]"
            >
              <span
                class="mt-1 w-1.5 h-1.5 rounded-full shrink-0"
                :class="
                  candidate.versionId === version.versionId
                    ? 'bg-primary-500'
                    : candidate.status === 'failed'
                      ? 'bg-red-500'
                      : 'bg-surface-400'
                "
              />
              <span class="font-mono text-muted-color">{{ tagOf(candidate.versionId) }}</span>
              <span class="truncate">{{ candidate.intent }}</span>
              <span class="ml-auto text-muted-color">s{{ candidate.createdAtStep }}</span>
            </li>
          </ul>
        </section>

        <section>
          <ScratchConsole :asset-name="version.definition.name" @promote="onPromote" />
          <div
            v-if="promoted"
            class="mt-2 px-2 py-1.5 rounded border border-primary-500 text-[11px] space-y-1"
          >
            <p>
              promote to asset —
              <span class="font-mono">Scratch1(deps=[{{ version.definition.name }}])</span>
            </p>
            <p class="font-mono text-muted-color break-all">{{ promoted }}</p>
            <div class="flex items-center gap-2">
              <CostChip :cost="promoteCost" />
              <button
                class="px-1.5 py-0.5 rounded border border-surface-300 dark:border-surface-600 text-[11px]"
                @click="promoted = null"
              >
                cancel
              </button>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ArtifactView from '../../components/ArtifactView.vue'
import CostChip from '../../components/CostChip.vue'
import ScratchConsole from '../../components/ScratchConsole.vue'
import StatusBadges from '../../components/StatusBadges.vue'
import { downstreamOf, resolveSlice, versionsOf } from '../../engine'
import { railroadUnsyncedCause } from './staleness'
import type { ArtifactValue, AssetId, BranchId, FlowSession, PreflightCost } from '../../types'

/**
 * Where editing lives in this concept: a side panel, never an expanding node.
 *
 * The canvas is spatially stable by construction, and an inline editor would
 * undo that the first time a node grew to twenty lines. The panel is also the
 * only place that can honestly price an edit before it happens — a definition
 * change recomputes this asset and everything below it.
 */
const props = defineProps<{
  session: FlowSession
  branchId: BranchId
  assetId: AssetId | null
}>()

const editing = ref(false)
const draft = ref('')
const promoted = ref<string | null>(null)

const slice = computed(() => resolveSlice(props.session, props.branchId))

const version = computed(() => {
  if (!props.assetId) return null
  const versions = versionsOf(props.session, props.assetId)
  return slice.value[props.assetId] ?? versions[versions.length - 1] ?? null
})

watch(version, (value) => {
  editing.value = false
  promoted.value = null
  draft.value = value?.definition.source ?? ''
})

const versionTag = computed(() => tagOf(version.value?.versionId ?? ''))
const branchName = computed(() => props.session.branches[props.branchId]?.name ?? props.branchId)

const cause = computed(() =>
  props.assetId && slice.value[props.assetId]
    ? railroadUnsyncedCause(props.session, props.branchId, props.assetId)
    : null,
)

const history = computed(() => (props.assetId ? versionsOf(props.session, props.assetId) : []))

const artifact = computed<ArtifactValue | null>(() => {
  const materialization = version.value
    ? props.session.materializations[version.value.versionId]
    : null
  const values = Object.values(materialization?.values ?? {})
  return (values[0] as ArtifactValue | undefined) ?? null
})

/** Editing this asset invalidates it and everything below it; the rest stays cached. */
const editCost = computed<PreflightCost>(() => {
  if (!props.assetId) return { cachedAssetIds: [], recomputeAssetIds: [], totalSeconds: 0 }
  const affected = [props.assetId, ...downstreamOf(props.session, props.branchId, props.assetId)]
  const affectedSet = new Set(affected)
  const totalSeconds = affected.reduce((sum, assetId) => {
    const selected = slice.value[assetId]
    return sum + (props.session.materializations[selected?.versionId]?.costSeconds ?? 0)
  }, 0)
  return {
    cachedAssetIds: Object.keys(slice.value).filter((assetId) => !affectedSet.has(assetId)),
    recomputeAssetIds: affected,
    totalSeconds,
  }
})

/** Promotion reads the already-cached materialization, so it costs nothing. */
const promoteCost = computed<PreflightCost>(() => ({
  cachedAssetIds: props.assetId ? [props.assetId] : [],
  recomputeAssetIds: [],
  totalSeconds: 0,
}))

const onPromote = (expression: string): void => {
  promoted.value = expression
}

function tagOf(versionId: string): string {
  return versionId.split('@')[1] ?? versionId
}
</script>
