import type { Component } from 'vue'
import { defineAsyncComponent } from 'vue'

export interface GallerySection {
  id: string
  label: string
  group: 'Foundations' | 'Components' | 'Pages'
  blurb: string
  component: Component
}

export const sections: GallerySection[] = [
  {
    id: 'foundations',
    label: 'Foundations',
    group: 'Foundations',
    blurb:
      'The shared vocabulary: status chips with named causes, kind iconography, actor identity, branch identity, factual badges, and the five-state flow indicator.',
    component: defineAsyncComponent(() => import('./sections/FoundationsSection.vue')),
  },
  {
    id: 'renderers',
    label: 'Renderers',
    group: 'Foundations',
    blurb:
      'One renderer per asset kind, drawing from the stored preview — the kernel-free tier. Unknown kinds fall back to a key-value grid, never an error.',
    component: defineAsyncComponent(() => import('./sections/RenderersSection.vue')),
  },
  {
    id: 'cell-card',
    label: 'Cell card',
    group: 'Components',
    blurb:
      'The product in one component: a tab strip over the assets a cell produced, plus code and logs, at two densities. Every state a card can be in.',
    component: defineAsyncComponent(() => import('./sections/CellCardSection.vue')),
  },
  {
    id: 'run-controls',
    label: 'Run controls',
    group: 'Components',
    blurb:
      'Run with its preflight (what is cached, what recomputes, total seconds — before the click), awaiter-aware stop, rerun branch, force-rerun as a labeled modifier.',
    component: defineAsyncComponent(() => import('./sections/RunControlsSection.vue')),
  },
  {
    id: 'errors',
    label: 'Errors & recovery',
    group: 'Components',
    blurb:
      'Demoted agent failures, loud user failures with a fix-this handoff, flagged references with did-you-mean, conflicts, and the session-level banners.',
    component: defineAsyncComponent(() => import('./sections/ErrorsSection.vue')),
  },
  {
    id: 'left-panel',
    label: 'Left panel',
    group: 'Components',
    blurb:
      'The active branch: identifier, current agent task, and the inventory — cells, experiments, models, inputs, docs, packages — plus the two settings that are real.',
    component: defineAsyncComponent(() => import('./sections/LeftPanelSection.vue')),
  },
  {
    id: 'branch-graph',
    label: 'Branch graph',
    group: 'Components',
    blurb:
      'The fork tree behind the branch identifier: view vs. check out as separate verbs, archive, and 2–5 branch selection for comparison.',
    component: defineAsyncComponent(() => import('./sections/BranchGraphSection.vue')),
  },
  {
    id: 'session',
    label: 'Session & pairing',
    group: 'Components',
    blurb:
      'Pairing detected from the journal rather than declared, the flow state indicator, catch-up marker, and every degraded state with its surface.',
    component: defineAsyncComponent(() => import('./sections/SessionSection.vue')),
  },
  {
    id: 'compare',
    label: 'Compare',
    group: 'Components',
    blurb:
      'Side-by-side results, definition divergence as the branching point, materialization divergence collapsed to chip rows, and integrity warnings inline.',
    component: defineAsyncComponent(() => import('./sections/CompareSection.vue')),
  },
  {
    id: 'pages',
    label: 'Pages',
    group: 'Pages',
    blurb: 'The assembled surfaces, each opening in its own route with switchable states.',
    component: defineAsyncComponent(() => import('./sections/PagesSection.vue')),
  },
]

export const sectionGroups = ['Foundations', 'Components', 'Pages'] as const

export function sectionById(id: string | undefined): GallerySection {
  return sections.find((section) => section.id === id) ?? sections[0]
}
