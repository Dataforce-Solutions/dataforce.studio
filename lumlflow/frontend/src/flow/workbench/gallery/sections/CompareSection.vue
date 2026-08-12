<template>
  <div class="flex max-w-5xl flex-col gap-8">
    <GallerySpecimen
      title="Integrity warning"
      caption="Comparability is never assumed — divergent pins, mismatched datasets, or mismatched scoring surface inline and name the affected branches."
    >
      <div class="flex flex-col gap-3">
        <IntegrityWarningBar :warning="sweepCompare.warnings[0]" />
        <IntegrityWarningBar :warning="scoringMismatch" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Result columns"
      caption="One column per branch aligned on asset; the best value per score row is marked; the shared metric overlays on one chart, one color per branch."
    >
      <ResultColumns :fixture="twoBranchCompare" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Definition divergence"
      caption="The branching point: someone edited the cell — rare, structural. One side per distinct definition, with the differing param highlighted."
    >
      <DivergencePointCard :divergence="sweepCompare.definitionDivergences[0]" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Materialization divergence"
      caption="Same code, different inputs — transitively closed, so it collapses to one row per asset with a chip per branch, never a fan of identical-code nodes."
    >
      <div class="flex flex-col gap-4">
        <MaterializationRows :rows="sweepCompare.materializationRows" />
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-color">
          <span
            class="inline-flex items-center rounded-full border border-surface-200 bg-surface-50 px-2 py-0.5 text-surface-700 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-300"
          >
            same
          </span>
          <span
            class="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300"
          >
            better
          </span>
          <span
            class="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
          >
            worse
          </span>
          <span
            class="inline-flex items-center rounded-full border border-dashed border-surface-300 px-2 py-0.5 text-muted-color dark:border-surface-600"
          >
            missing
          </span>
          <span>state colors relative to the comparison baseline</span>
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Shapeless differences"
      caption="Renames, absences, and param-only changes get an exhaustive plain table, so nothing is unreachable just because it did not fit the visual."
    >
      <ShapelessTable :differences="sweepCompare.shapelessDifferences" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Artifact links"
      caption="The fallback chain: experiment → the tracker experiment screen, model → the model card, dataset → the dataset view, anything else → the main metric."
    >
      <ArtifactLinks :artifacts="sweepCompare.artifacts" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Adopt & export"
      caption="The two closing verbs: adopt the winner's version of an asset (per-asset cherry-pick with three-way conflict detection) and export the chosen slice as a file."
    >
      <AdoptBar winner="exp/lr-1e3" asset="train_model" target="main" />
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import AdoptBar from '../../components/compare/AdoptBar.vue'
import ArtifactLinks from '../../components/compare/ArtifactLinks.vue'
import DivergencePointCard from '../../components/compare/DivergencePointCard.vue'
import IntegrityWarningBar from '../../components/compare/IntegrityWarningBar.vue'
import MaterializationRows from '../../components/compare/MaterializationRows.vue'
import ResultColumns from '../../components/compare/ResultColumns.vue'
import ShapelessTable from '../../components/compare/ShapelessTable.vue'
import { sweepCompare } from '../../fixtures/compare'
import type { CompareFixture, CompareWarning } from '../../fixtures/compare'
import GallerySpecimen from '../GallerySpecimen.vue'

// Two-branch slice of the sweep, warnings dropped — they have their own specimen.
const twoBranchCompare: CompareFixture = {
  ...sweepCompare,
  branches: sweepCompare.branches.slice(0, 2),
  warnings: [],
}

const scoringMismatch: CompareWarning = {
  kind: 'scoring-mismatch',
  message:
    '`holdout_eval` scores with weighted accuracy on exp/feature-drop but plain accuracy on main',
  affectedBranches: ['main', 'exp/feature-drop'],
}
</script>
