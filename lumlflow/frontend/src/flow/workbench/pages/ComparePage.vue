<template>
  <div class="flex max-w-5xl flex-col gap-8 pb-12">
    <header class="flex flex-col gap-2">
      <h3 class="text-xl font-medium">Comparing {{ fixture.branches.length }} branches</h3>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <BranchTag
          v-for="column in fixture.branches"
          :key="column.branch"
          :name="column.branch"
          :checked-out="column.branch === target"
        />
      </div>
      <p class="text-xs text-muted-color">
        Selection happens in the branch graph — pick 2–5 branches there and land here.
      </p>
    </header>

    <section class="flex flex-col gap-3">
      <SectionLabel label="Final results" />
      <!-- Integrity warnings render inline at the top of the columns. -->
      <ResultColumns :fixture="fixture" />
    </section>

    <section class="flex flex-col gap-3">
      <SectionLabel label="Where the paths go differently" />
      <DivergencePointCard
        v-for="divergence in fixture.definitionDivergences"
        :key="divergence.slug"
        :divergence="divergence"
      />
      <MaterializationRows :rows="fixture.materializationRows" />
      <button
        type="button"
        class="inline-flex items-center gap-1 self-start text-xs text-muted-color hover:underline"
        @click="showAllDifferences = !showAllDifferences"
      >
        <ChevronDown
          :size="13"
          class="transition-transform"
          :class="showAllDifferences ? 'rotate-180' : ''"
        />
        {{ showAllDifferences ? 'hide' : 'show' }} all differences ({{
          fixture.shapelessDifferences.length
        }})
      </button>
      <ShapelessTable v-if="showAllDifferences" :differences="fixture.shapelessDifferences" />
    </section>

    <section class="flex flex-col gap-3">
      <SectionLabel label="Artifacts" />
      <ArtifactLinks :artifacts="fixture.artifacts" />
    </section>

    <AdoptBar
      :winner="winner"
      :asset="adoptAsset"
      :target="target"
      @adopt="onAdopt"
      @export="onExport"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { ChevronDown } from 'lucide-vue-next'
import AdoptBar from '../components/compare/AdoptBar.vue'
import ArtifactLinks from '../components/compare/ArtifactLinks.vue'
import DivergencePointCard from '../components/compare/DivergencePointCard.vue'
import MaterializationRows from '../components/compare/MaterializationRows.vue'
import ResultColumns from '../components/compare/ResultColumns.vue'
import ShapelessTable from '../components/compare/ShapelessTable.vue'
import { sweepCompare } from '../fixtures/compare'
import BranchTag from '../ui/BranchTag.vue'
import SectionLabel from '../ui/SectionLabel.vue'

const fixture = sweepCompare
const target = 'main'
const adoptAsset = 'train_model'

const toast = useToast()
const showAllDifferences = ref(false)

const winner = computed(() => {
  const [first, ...rest] = fixture.branches
  return rest.reduce((best, column) => {
    const better = column.headlineMetric.higherIsBetter
      ? column.headlineMetric.value > best.headlineMetric.value
      : column.headlineMetric.value < best.headlineMetric.value
    return better ? column : best
  }, first).branch
})

function onAdopt(): void {
  toast.add({
    severity: 'info',
    summary: 'Adopt',
    detail: `would adopt ${adoptAsset} from ${winner.value} onto ${target} — three-way check on the definition runs first`,
    life: 4000,
  })
}

function onExport(): void {
  toast.add({
    severity: 'info',
    summary: 'Export flow file',
    detail: 'would export the chosen slice as a flow file — a file export, not a platform upload',
    life: 4000,
  })
}
</script>
