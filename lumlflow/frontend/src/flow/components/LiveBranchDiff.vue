<template>
  <section
    data-branch-diff
    class="mb-4 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
  >
    <div class="flex items-start gap-4">
      <div class="min-w-0 flex-1">
        <h3 class="font-medium">Compare branches</h3>
        <p class="text-xs text-muted-color">
          Adopt actions copy from the comparison into the baseline.
        </p>
      </div>
      <button
        type="button"
        class="text-xs text-muted-color hover:text-color"
        aria-label="Close branch comparison"
        @click="emit('close')"
      >
        Close
      </button>
    </div>

    <form class="mt-3 flex flex-wrap items-end gap-3" data-diff-form @submit.prevent="loadDiff">
      <label class="text-sm">
        <span class="mb-1 block text-xs text-muted-color">Baseline</span>
        <select
          v-model="leftBranchId"
          name="diff-left-branch"
          class="rounded border border-surface-300 bg-transparent px-2 py-1.5 dark:border-surface-600"
        >
          <option v-for="branch in branches" :key="branch.branch_id" :value="branch.branch_id">
            {{ branch.name }}
          </option>
        </select>
      </label>
      <label class="text-sm">
        <span class="mb-1 block text-xs text-muted-color">Comparison</span>
        <select
          v-model="rightBranchId"
          name="diff-right-branch"
          class="rounded border border-surface-300 bg-transparent px-2 py-1.5 dark:border-surface-600"
        >
          <option v-for="branch in branches" :key="branch.branch_id" :value="branch.branch_id">
            {{ branch.name }}
          </option>
        </select>
      </label>
      <button
        type="submit"
        class="rounded border border-surface-300 px-3 py-1.5 text-sm dark:border-surface-600"
        :disabled="diffPending || leftBranchId === rightBranchId"
      >
        {{ diffPending ? 'Comparing…' : 'Compare' }}
      </button>
    </form>

    <p v-if="diffError" role="alert" data-diff-error class="mt-3 text-sm text-red-600">
      {{ diffError }}
    </p>

    <div v-if="diffResult" class="mt-4 overflow-x-auto">
      <table class="w-full border-collapse text-left text-sm">
        <thead>
          <tr class="border-b border-surface-200 dark:border-surface-700">
            <th class="py-2 pr-4 font-medium">cell</th>
            <th class="py-2 pr-4 font-medium">change</th>
            <th class="py-2 pr-4 font-medium">{{ diffResult.left }}</th>
            <th class="py-2 pr-4 font-medium">{{ diffResult.right }}</th>
            <th class="py-2 font-medium"><span class="sr-only">actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="difference in diffResult.differences"
            :key="difference.cell"
            data-diff-row
            class="border-b border-surface-100 align-top dark:border-surface-800"
          >
            <td class="py-2 pr-4 font-mono font-medium">{{ difference.cell }}</td>
            <td class="py-2 pr-4">{{ divergenceLabel(difference) }}</td>
            <td class="py-2 pr-4">
              <DiffSide
                :params="difference.left_params"
                :outputs="difference.left_outputs"
                :show-params="paramsDiffer(difference)"
              />
            </td>
            <td class="py-2 pr-4">
              <DiffSide
                :params="difference.right_params"
                :outputs="difference.right_outputs"
                :show-params="paramsDiffer(difference)"
              />
            </td>
            <td class="py-2 text-right">
              <button
                v-if="difference.right_version"
                type="button"
                data-adopt-cell
                class="whitespace-nowrap rounded border border-surface-300 px-2 py-1 text-xs dark:border-surface-600"
                :disabled="adoptPendingCell !== null"
                @click="adopt(difference)"
              >
                {{
                  adoptPendingCell === difference.cell
                    ? 'Adopting…'
                    : `Adopt into ${diffResult.left}`
                }}
              </button>
              <span v-else class="text-xs text-muted-color">Absent from comparison</span>
              <p
                v-if="adoptErrors[difference.cell]"
                role="alert"
                data-adopt-error
                class="mt-1 max-w-64 text-left text-xs text-red-600"
              >
                {{ adoptErrors[difference.cell] }}
              </p>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!diffResult.differences.length" class="py-4 text-sm text-muted-color">
        These branches have identical cells, parameters, and outputs.
      </p>
    </div>

    <p v-if="adoptSuccess" role="status" data-adopt-success class="mt-3 text-sm text-emerald-600">
      {{ adoptSuccess }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref, watch, type PropType, type VNode } from 'vue'
import type { FlowSessionClient } from '../api/client'
import type { JsonValue, LiveBranch } from '../api/types'

interface BranchDifference {
  cell: string
  divergence: 'definition' | 'materialization'
  left_version: string | null
  right_version: string | null
  left_params: Record<string, JsonValue> | null
  right_params: Record<string, JsonValue> | null
  left_outputs: Record<string, string | null> | null
  right_outputs: Record<string, string | null> | null
}

interface BranchDiffResult {
  left: string
  right: string
  differences: BranchDifference[]
}

const props = defineProps<{
  client: FlowSessionClient
  branches: LiveBranch[]
  activeBranchId: string
}>()

const emit = defineEmits<{ close: [] }>()
const leftBranchId = ref(props.activeBranchId)
const rightBranchId = ref(
  props.branches.find(({ branch_id }) => branch_id !== props.activeBranchId)?.branch_id ??
    props.activeBranchId,
)
const diffPending = ref(false)
const diffError = ref('')
const diffResult = ref<BranchDiffResult | null>(null)
const adoptPendingCell = ref<string | null>(null)
const adoptErrors = ref<Record<string, string>>({})
const adoptSuccess = ref('')

const branchName = (branchId: string): string =>
  props.branches.find(({ branch_id }) => branch_id === branchId)?.name ?? branchId

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error)

const loadDiff = async (): Promise<void> => {
  if (diffPending.value || leftBranchId.value === rightBranchId.value) return
  diffPending.value = true
  diffError.value = ''
  adoptSuccess.value = ''
  adoptErrors.value = {}
  try {
    diffResult.value = (await props.client.rpc('diff', {
      left: leftBranchId.value,
      right: rightBranchId.value,
    })) as unknown as BranchDiffResult
  } catch (error) {
    diffResult.value = null
    diffError.value = errorMessage(error)
  } finally {
    diffPending.value = false
  }
}

const adopt = async (difference: BranchDifference): Promise<void> => {
  if (adoptPendingCell.value !== null) return
  adoptPendingCell.value = difference.cell
  adoptSuccess.value = ''
  adoptErrors.value = { ...adoptErrors.value, [difference.cell]: '' }
  const source = branchName(rightBranchId.value)
  const target = branchName(leftBranchId.value)
  try {
    await props.client.rpc('adopt', {
      slug: difference.cell,
      from_branch: rightBranchId.value,
      branch: leftBranchId.value,
      actor: 'user:ui',
      intent: `adopt ${difference.cell} from ${source} into ${target}`,
    })
    adoptSuccess.value = `Adopted ${difference.cell} from ${source} into ${target}.`
  } catch (error) {
    adoptErrors.value = { ...adoptErrors.value, [difference.cell]: errorMessage(error) }
  } finally {
    adoptPendingCell.value = null
  }
}

const paramsDiffer = (difference: BranchDifference): boolean =>
  JSON.stringify(difference.left_params) !== JSON.stringify(difference.right_params)

const divergenceLabel = (difference: BranchDifference): string => {
  if (paramsDiffer(difference)) return 'parameters and definition'
  return difference.divergence === 'definition' ? 'definition' : 'outputs'
}

watch([leftBranchId, rightBranchId], () => {
  diffResult.value = null
  diffError.value = ''
  adoptSuccess.value = ''
  adoptErrors.value = {}
})

watch(
  () => props.activeBranchId,
  (branchId) => {
    leftBranchId.value = branchId
    if (rightBranchId.value === branchId) {
      rightBranchId.value =
        props.branches.find(({ branch_id }) => branch_id !== branchId)?.branch_id ?? branchId
    }
  },
)

const DiffSide = defineComponent({
  props: {
    params: { type: Object as PropType<Record<string, JsonValue> | null>, default: null },
    outputs: { type: Object as PropType<Record<string, string | null> | null>, default: null },
    showParams: { type: Boolean, required: true },
  },
  setup(sideProps) {
    const outputEntries = computed(() => Object.entries(sideProps.outputs ?? {}))
    return (): VNode => {
      if (sideProps.params === null && sideProps.outputs === null) {
        return h('span', { class: 'text-muted-color' }, 'absent')
      }
      const children: VNode[] = []
      if (sideProps.showParams) {
        children.push(
          h('p', { 'data-diff-params': '', class: 'font-mono text-xs' }, [
            h('span', { class: 'text-muted-color' }, 'params '),
            JSON.stringify(sideProps.params ?? {}),
          ]),
        )
      }
      for (const [name, hash] of outputEntries.value) {
        children.push(
          h('p', { 'data-diff-output': '', class: 'font-mono text-xs' }, [
            `${name}: `,
            h(
              'span',
              { title: hash ?? undefined, class: hash === null ? 'text-muted-color' : '' },
              hash?.slice(0, 12) ?? 'not run',
            ),
          ]),
        )
      }
      if (!children.length) children.push(h('span', { class: 'text-muted-color' }, '—'))
      return h('div', children)
    }
  },
})
</script>
