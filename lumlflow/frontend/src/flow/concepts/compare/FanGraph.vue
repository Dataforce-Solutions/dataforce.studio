<template>
  <section class="border border-surface-300 dark:border-surface-600 rounded p-3">
    <header class="flex items-baseline gap-3 mb-1">
      <h3 class="font-medium text-sm">Where these variants diverge</h3>
      <span class="text-xs text-muted-color">
        {{ codeFans }} code fan{{ codeFans === 1 ? '' : 's' }} ·
        {{ valueFans }} value fan{{ valueFans === 1 ? '' : 's' }} ·
        {{ sharedAssetIds.length }} shared assets not drawn
      </span>
      <button
        class="ml-auto text-xs px-2 py-0.5 rounded border border-surface-300 dark:border-surface-600"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'collapse long stages' : 'show every value fan' }}
      </button>
    </header>

    <!--
      The canvas would otherwise assert a product of fan widths. Saying the number
      out loud, next to the number of slices that actually exist, is the cheapest
      possible fix for a graph that lies about what was tried.
    -->
    <p class="text-xs mb-3" :class="overclaims ? 'text-amber-600 dark:text-amber-400' : 'text-muted-color'">
      <template v-if="overclaims">
        These fans lay out {{ assertedCombinations }} possible combinations, but only
        {{ branchIds.length }} were ever run. Hover a variant to see which combinations it
        actually appears in.
      </template>
      <template v-else>
        Hover a variant to highlight the slices that contain it.
      </template>
    </p>

    <p v-if="!stages.length" class="text-sm text-muted-color py-6">
      These variants select an identical version of every asset — there is nothing to fan.
    </p>

    <div v-for="(stage, stageIndex) in stages" :key="stageIndex">
      <div class="flex flex-wrap gap-3">
        <article
          v-for="node in visibleNodes(stage)"
          :key="node.assetId"
          class="rounded border px-3 py-2 min-w-[15rem]"
          :class="nodeClass(node)"
          @mouseleave="hovered = null"
        >
          <header class="flex items-center gap-2 mb-1.5">
            <span class="font-medium text-sm">{{ node.name }}</span>
            <span class="text-xs text-muted-color">
              <template v-if="node.kind === 'definition'">
                code fan · {{ node.variants.length }} definitions
              </template>
              <template v-else>
                value fan · {{ node.results.length }} distinct result{{
                  node.results.length === 1 ? '' : 's'
                }}
              </template>
            </span>
            <StatusBadges :cause="unsyncedCause(node.assetId)" />
          </header>

          <p v-if="node.scopedDeps.length" class="text-xs text-muted-color mb-1.5">
            reads
            <template v-for="(dep, depIndex) in node.scopedDeps" :key="dep">
              <span v-if="depIndex" >, </span>
              <span
                class="font-mono"
                :class="conflictingDep(node.assetId, dep) ? 'text-red-600 dark:text-red-400 font-medium' : ''"
              >
                {{ nameOf(dep) }}
              </span>
            </template>
          </p>

          <!-- Code fan: one chip per distinct definition. Solid is committed. -->
          <div v-if="node.kind === 'definition'" class="flex flex-wrap gap-1.5">
            <button
              v-for="variant in node.variants"
              :key="variant.key"
              class="text-left px-2 py-1 rounded border text-xs max-w-[15rem]"
              :class="variantClass(node.assetId, variant)"
              :title="variantTitle(node, variant)"
              @mouseenter="hovered = { assetId: node.assetId, key: variant.key }"
              @click="onVariantClick(node, variant)"
            >
              <span class="flex items-center gap-1">
                <span
                  v-for="branchId in variant.branchIds"
                  :key="branchId"
                  class="w-1.5 h-1.5 rounded-full"
                  :style="{ background: session.branches[branchId]?.color }"
                />
                <span class="font-mono">{{ variant.tag }}</span>
                <span v-if="variant.failed" class="text-red-600 dark:text-red-400">failed</span>
                <span v-if="isCommitted(node.assetId, variant.key)" class="text-primary-600 dark:text-primary-400">
                  committed
                </span>
              </span>
              <span class="block text-muted-color truncate">{{ variant.intent }}</span>
            </button>
          </div>

          <!--
            Value fan: same code, different inputs. Drawing one node copy per
            branch here is what makes a five-way comparison unreadable and a
            twenty-way one impossible, so it stays one node with N result chips.
          -->
          <div v-else class="flex flex-wrap gap-1.5">
            <span
              v-for="result in node.results"
              :key="result.key"
              class="px-2 py-1 rounded border border-surface-300 dark:border-surface-600 text-xs"
              :class="resultClass(result)"
              :title="`${result.branchIds.length} branch(es) share this materialization`"
            >
              <span class="flex items-center gap-1">
                <span
                  v-for="branchId in result.branchIds"
                  :key="branchId"
                  class="w-1.5 h-1.5 rounded-full"
                  :style="{ background: session.branches[branchId]?.color }"
                />
                <span v-if="result.metric" class="font-medium">
                  {{ result.metric.name }} {{ result.metric.value.toFixed(3) }}
                </span>
                <span v-else class="font-mono text-muted-color">{{ result.label }}</span>
              </span>
            </span>
            <span v-if="node.results.length === 1" class="text-xs text-muted-color self-center">
              identical across all {{ branchIds.length }}
            </span>
          </div>

          <p
            v-for="conflict in conflictsFor(node.assetId)"
            :key="conflict.onAssetId"
            class="mt-2 text-xs text-red-700 dark:text-red-300"
          >
            {{ conflict.message }}
          </p>
        </article>

        <span
          v-if="hiddenCount(stage) > 0"
          class="self-center text-xs text-muted-color px-2 py-1 rounded border border-dashed border-surface-300 dark:border-surface-600"
        >
          +{{ hiddenCount(stage) }} more value fans downstream
        </span>
      </div>

      <svg
        v-if="stageIndex < stages.length - 1"
        class="h-5 w-24 ml-6"
        viewBox="0 0 24 20"
        preserveAspectRatio="none"
      >
        <line
          x1="12"
          y1="0"
          x2="12"
          y2="20"
          :class="stageConflict(stageIndex) ? 'stroke-red-500' : 'stroke-surface-300 dark:stroke-surface-600'"
          :stroke-width="stageConflict(stageIndex) ? 2 : 1"
        />
      </svg>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import StatusBadges from '../../components/StatusBadges.vue'
import { ABSENT, type ComposedPath, type FanNode, type PathConflict, type Variant } from './useComparison'
import type { AssetId, BranchId, FlowSession, UnsyncedCause, VersionId } from '../../types'

/**
 * The scoped fan graph.
 *
 * Only the sub-DAG in which the selected variants actually differ is drawn, and
 * it fans on *definition* divergence only. Everything below a fan diverges too —
 * that is what content-addressed versions guarantee — but it diverges in value,
 * not in code, and value differences are a table, not a shape.
 */
const props = defineProps<{
  session: FlowSession
  stages: FanNode[][]
  branchIds: BranchId[]
  sharedAssetIds: AssetId[]
  assertedCombinations: number
  path: ComposedPath
  conflicts: PathConflict[]
  unsyncedCause: (assetId: AssetId) => UnsyncedCause | null
  correlatedBranchIds: (assetId: AssetId, key: VersionId | typeof ABSENT) => BranchId[]
}>()

const emit = defineEmits<{
  commit: [assetId: AssetId, key: VersionId | typeof ABSENT]
  inspect: [assetId: AssetId, key: VersionId | typeof ABSENT]
}>()

const COLLAPSED_PER_STAGE = 6

const expanded = ref(false)
const hovered = ref<{ assetId: AssetId; key: VersionId | typeof ABSENT } | null>(null)

const nodes = computed(() => props.stages.flat())
const codeFans = computed(() => nodes.value.filter((node) => node.kind === 'definition').length)
const valueFans = computed(() => nodes.value.filter((node) => node.kind === 'materialization').length)
const overclaims = computed(() => props.assertedCombinations > props.branchIds.length)

/** Branch ids the hovered variant appears in — the slices, not the fan point. */
const hoveredBranchIds = computed<BranchId[] | null>(() =>
  hovered.value ? props.correlatedBranchIds(hovered.value.assetId, hovered.value.key) : null,
)

const correlated = (branchIds: BranchId[]): boolean =>
  !hoveredBranchIds.value || branchIds.some((id) => hoveredBranchIds.value?.includes(id))

const isCommitted = (assetId: AssetId, key: VersionId | typeof ABSENT): boolean =>
  props.path[assetId] === key

const visibleNodes = (stage: FanNode[]): FanNode[] => {
  if (expanded.value) return stage
  const fans = stage.filter((node) => node.kind === 'definition')
  const collapsed = stage.filter((node) => node.kind === 'materialization')
  return [...fans, ...collapsed.slice(0, COLLAPSED_PER_STAGE)]
}

const hiddenCount = (stage: FanNode[]): number => stage.length - visibleNodes(stage).length

const nameOf = (assetId: AssetId): string =>
  nodes.value.find((node) => node.assetId === assetId)?.name ??
  props.session.assets[assetId]?.at(-1)?.definition.name ??
  assetId

const conflictsFor = (assetId: AssetId): PathConflict[] =>
  props.conflicts.filter((conflict) => conflict.assetId === assetId)

const conflictingDep = (assetId: AssetId, depId: AssetId): boolean =>
  props.conflicts.some((c) => c.assetId === assetId && c.onAssetId === depId)

const stageConflict = (stageIndex: number): boolean =>
  (props.stages[stageIndex + 1] ?? []).some((node) => conflictsFor(node.assetId).length > 0)

const nodeClass = (node: FanNode): string => {
  if (conflictsFor(node.assetId).length) return 'border-red-500 bg-red-50 dark:bg-red-950/20'
  return node.kind === 'definition'
    ? 'border-surface-300 dark:border-surface-600'
    : 'border-dashed border-surface-300 dark:border-surface-700'
}

const variantClass = (assetId: AssetId, variant: Variant): string => {
  const dimmed = correlated(variant.branchIds) ? '' : ' opacity-25'
  if (isCommitted(assetId, variant.key)) {
    return `border-primary-500 bg-primary-50 dark:bg-primary-950/30${dimmed}`
  }
  return `border-dashed border-surface-300 dark:border-surface-600 opacity-70 hover:opacity-100${dimmed}`
}

const resultClass = (result: { branchIds: BranchId[] }): string =>
  correlated(result.branchIds) ? '' : 'opacity-25'

const variantTitle = (node: FanNode, variant: Variant): string => {
  if (isCommitted(node.assetId, variant.key)) return 'On the committed path. Click to inspect.'
  return `Swap ${node.name} ${variant.tag} into the committed path — composes a slice no branch ran.`
}

const onVariantClick = (node: FanNode, variant: Variant): void => {
  if (isCommitted(node.assetId, variant.key)) {
    emit('inspect', node.assetId, variant.key)
    return
  }
  emit('commit', node.assetId, variant.key)
  emit('inspect', node.assetId, variant.key)
}
</script>
