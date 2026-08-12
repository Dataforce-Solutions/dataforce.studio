<template>
  <div class="flex flex-col">
    <div
      v-for="artifact in artifacts"
      :key="artifact.slug + artifact.output"
      class="flex flex-col gap-1.5 border-t border-surface-200 py-3 first:border-t-0 first:pt-0 last:pb-0 dark:border-surface-700"
    >
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <KindBadge :kind="artifact.kind" icon-only />
        <a v-if="artifact.href" class="link text-sm" :href="artifact.href">{{ artifact.label }}</a>
        <span v-else class="text-sm">{{ artifact.label }}</span>
        <span class="font-mono text-xs text-muted-color">
          {{ artifact.slug }}.{{ artifact.output }}
        </span>
        <span class="ml-auto text-xs text-muted-color">{{ destination(artifact.kind) }}</span>
      </div>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="(reference, branch) in artifact.byBranch"
          :key="branch"
          v-tooltip.top="branch"
          class="inline-flex items-center gap-1.5 rounded border border-surface-200 px-1.5 py-0.5 font-mono text-[11px] dark:border-surface-700"
        >
          <span
            class="h-2 w-2 shrink-0 rounded-full"
            :style="{ background: branchColor(String(branch)) }"
          />
          {{ reference }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CompareArtifactLink } from '../../fixtures/compare'
import KindBadge from '../../ui/KindBadge.vue'
import { branchColor } from '../../ui/kinds'

defineProps<{ artifacts: CompareArtifactLink[] }>()

/** The fallback chain: experiment → tracker, model → model card, dataset → view, else → metric. */
function destination(kind: CompareArtifactLink['kind']): string {
  switch (kind) {
    case 'experiment':
      return 'opens the tracker experiment screen'
    case 'model':
      return 'opens the model card'
    case 'dataset':
      return 'opens the dataset view'
    default:
      return 'no artifact screen — the main metric shown as is'
  }
}
</script>
