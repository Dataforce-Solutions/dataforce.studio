<template>
  <section
    data-sweep-comparison
    class="mb-4 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
  >
    <h3 class="mb-2 font-medium">Sweep · {{ sweep.group }}</h3>
    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead>
          <tr class="border-b border-surface-200 dark:border-surface-700">
            <th class="py-2 pr-4 font-medium">branch</th>
            <th class="py-2 pr-4 font-medium">parameters</th>
            <th class="py-2 pr-4 font-medium">outputs</th>
            <th class="py-2 font-medium"><span class="sr-only">actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="variant in sweep.variants"
            :key="variant.branch_id"
            data-sweep-variant
            :data-sweep-state="isComplete(variant) ? 'complete' : 'waiting'"
            class="border-b border-surface-100 align-top dark:border-surface-800"
          >
            <td class="py-2 pr-4">{{ variant.branch }}</td>
            <td class="py-2 pr-4 font-mono text-xs">{{ JSON.stringify(variant.params) }}</td>
            <td class="py-2 pr-4 font-mono text-xs">
              <template v-if="outputEntries(variant).length">
                <p v-for="[output, hash] in outputEntries(variant)" :key="output">
                  {{ output }}:
                  <span :title="hash ?? undefined">{{ hash?.slice(0, 8) ?? 'not run' }}</span>
                </p>
              </template>
              <span v-else class="text-muted-color">waiting for materialization</span>
            </td>
            <td class="py-2 text-right">
              <button
                v-if="sweptCell"
                type="button"
                data-adopt-sweep-winner
                class="whitespace-nowrap rounded border border-surface-300 px-2 py-1 text-xs dark:border-surface-600"
                :disabled="adoptPendingBranch !== null || !isComplete(variant)"
                @click="adoptWinner(variant)"
              >
                {{ adoptPendingBranch === variant.branch_id ? 'Adopting…' : 'Adopt winner' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p
      v-if="adoptSuccess"
      role="status"
      data-sweep-adopt-success
      class="mt-3 text-sm text-emerald-600"
    >
      {{ adoptSuccess }}
    </p>
    <p v-if="adoptError" role="alert" data-sweep-adopt-error class="mt-3 text-sm text-red-600">
      {{ adoptError }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FlowSessionClient } from '../api/client'
import type { SweepComparison, SweepVariant } from '../api/types'

const props = defineProps<{
  sweep: SweepComparison
  client: FlowSessionClient
}>()

const adoptPendingBranch = ref<string | null>(null)
const adoptSuccess = ref('')
const adoptError = ref('')

const sweptCell = computed(() => {
  const cells = new Set(props.sweep.variants.flatMap((variant) => Object.keys(variant.params)))
  return cells.size === 1 ? ([...cells][0] ?? null) : null
})

const outputEntries = (variant: SweepVariant): [string, string | null][] =>
  Object.entries(variant.output_hashes)

const isComplete = (variant: SweepVariant): boolean =>
  outputEntries(variant).some(([, hash]) => hash !== null)

const adoptWinner = async (variant: SweepVariant): Promise<void> => {
  if (!sweptCell.value || adoptPendingBranch.value !== null || !isComplete(variant)) return
  adoptPendingBranch.value = variant.branch_id
  adoptSuccess.value = ''
  adoptError.value = ''
  try {
    await props.client.rpc('adopt', {
      slug: sweptCell.value,
      from_branch: variant.branch_id,
      branch: props.sweep.parent,
      actor: 'user:ui',
      intent: `adopt ${sweptCell.value} from ${variant.branch} into ${props.sweep.parent}`,
    })
    adoptSuccess.value = `Adopted ${sweptCell.value} from ${variant.branch} into ${props.sweep.parent}.`
  } catch (error) {
    adoptError.value = error instanceof Error ? error.message : String(error)
  } finally {
    adoptPendingBranch.value = null
  }
}
</script>
