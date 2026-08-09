<template>
  <div>
    <IntegrityWarnings :warnings="warnings" />

    <div class="flex items-center gap-2 mb-2 text-xs">
      <span class="text-muted-color">baseline</span>
      <button
        v-for="branchId in branchIds"
        :key="branchId"
        class="px-2 py-0.5 rounded border"
        :class="
          branchId === baselineId
            ? 'border-primary-500 text-primary-600 dark:text-primary-400'
            : 'border-surface-300 dark:border-surface-600 text-muted-color'
        "
        @click="baselineId = branchId"
      >
        {{ session.branches[branchId]?.name ?? branchId }}
      </button>
      <label class="ml-auto flex items-center gap-1.5">
        <input v-model="changedOnly" type="checkbox" />
        changed only
      </label>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-sm text-left border-collapse">
        <thead>
          <tr class="border-b border-surface-200 dark:border-surface-700">
            <th class="py-1.5 pr-4 font-medium">asset</th>
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
              <span v-if="branchId === baselineId" class="text-xs text-muted-color">baseline</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.assetId"
            class="border-b border-surface-100 dark:border-surface-800 align-top"
          >
            <td class="py-1.5 pr-4 whitespace-nowrap">
              {{ row.name }}
              <span
                class="ml-1 text-xs"
                :class="row.kind === 'definition' ? 'text-amber-600 dark:text-amber-400' : 'text-muted-color'"
              >
                {{ row.kind === 'definition' ? 'edited' : 'downstream' }}
              </span>
            </td>
            <td v-for="branchId in branchIds" :key="branchId" class="py-1.5 pr-4">
              <template v-if="!row.byBranch[branchId]">
                <span class="text-muted-color">absent</span>
              </template>
              <template v-else-if="row.byBranch[branchId] === row.byBranch[baselineId]">
                <span class="text-muted-color">—</span>
              </template>
              <template v-else>
                <span class="font-mono text-xs">{{ tagOf(row.byBranch[branchId] as string) }}</span>
                <span class="block text-xs text-muted-color max-w-[16rem]">
                  {{ intentOf(row.byBranch[branchId] as string) }}
                </span>
              </template>
            </td>
          </tr>

          <tr
            v-for="metricName in metricNames"
            :key="`metric-${metricName}`"
            class="border-b border-surface-100 dark:border-surface-800 bg-surface-50 dark:bg-surface-900/40"
          >
            <td class="py-1.5 pr-4 font-medium whitespace-nowrap">{{ metricName }}</td>
            <td v-for="branchId in branchIds" :key="branchId" class="py-1.5 pr-4 whitespace-nowrap">
              <template v-if="metricFor(branchId, metricName) !== null">
                {{ metricFor(branchId, metricName)?.toFixed(4) }}
                <span
                  v-if="branchId !== baselineId && deltaFor(branchId, metricName) !== null"
                  class="ml-1 text-xs"
                  :class="(deltaFor(branchId, metricName) as number) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'"
                >
                  {{ (deltaFor(branchId, metricName) as number) >= 0 ? '+' : ''
                  }}{{ (deltaFor(branchId, metricName) as number).toFixed(4) }}
                </span>
              </template>
              <span v-else class="text-muted-color">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="!rows.length" class="text-sm text-muted-color py-4">
      These variants select identical versions of every asset.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import IntegrityWarnings from './IntegrityWarnings.vue'
import { divergence, integrityWarnings, resolveSlice, versionById } from '../engine'
import type { BranchId, FlowSession } from '../types'

/**
 * Comparison across any N variants.
 *
 * Cells are *change chips* — version tag plus the intent of the transaction that
 * produced it — not source. That is what lets the table survive structurally
 * heterogeneous variants rather than only param sweeps: an asset that exists in
 * one branch and not another renders as "absent" instead of breaking the grid.
 */
const props = defineProps<{ session: FlowSession; branchIds: BranchId[] }>()

const baselineId = ref(props.branchIds[0])
const changedOnly = ref(true)

const warnings = computed(() => integrityWarnings(props.session, props.branchIds))

const rows = computed(() =>
  divergence(props.session, props.branchIds)
    .filter((entry) => (changedOnly.value ? entry.kind !== 'none' : true))
    .map((entry) => {
      const anyVersionId = Object.values(entry.byBranch).find(Boolean) as string | undefined
      const version = anyVersionId ? versionById(props.session, anyVersionId) : null
      return { ...entry, name: version?.definition.name ?? entry.assetId }
    })
    .sort((a, b) => (a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === 'definition' ? -1 : 1)),
)

const tagOf = (versionId: string): string => versionId.split('@')[1] ?? versionId
const intentOf = (versionId: string): string =>
  versionById(props.session, versionId)?.intent ?? ''

const metricsByBranch = computed(() => {
  const result: Record<BranchId, Record<string, number>> = {}
  for (const branchId of props.branchIds) {
    const slice = resolveSlice(props.session, branchId)
    const merged: Record<string, number> = {}
    for (const version of Object.values(slice)) {
      const materialization = props.session.materializations[version.versionId]
      Object.assign(merged, materialization?.metrics ?? {})
    }
    result[branchId] = merged
  }
  return result
})

const metricNames = computed(() => {
  const names = new Set<string>()
  Object.values(metricsByBranch.value).forEach((metrics) =>
    Object.keys(metrics).forEach((name) => names.add(name)),
  )
  return [...names].sort()
})

const metricFor = (branchId: BranchId, name: string): number | null =>
  metricsByBranch.value[branchId]?.[name] ?? null

const deltaFor = (branchId: BranchId, name: string): number | null => {
  const value = metricFor(branchId, name)
  const base = metricFor(baselineId.value, name)
  if (value === null || base === null) return null
  return value - base
}
</script>
