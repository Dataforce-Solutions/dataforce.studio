import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ToastService from 'primevue/toastservice'

import DesignSystemPage from '@/flow/workbench/gallery/DesignSystemPage.vue'
import BranchGraphSection from '@/flow/workbench/gallery/sections/BranchGraphSection.vue'
import CellCardSection from '@/flow/workbench/gallery/sections/CellCardSection.vue'
import CompareSection from '@/flow/workbench/gallery/sections/CompareSection.vue'
import ErrorsSection from '@/flow/workbench/gallery/sections/ErrorsSection.vue'
import FoundationsSection from '@/flow/workbench/gallery/sections/FoundationsSection.vue'
import LeftPanelSection from '@/flow/workbench/gallery/sections/LeftPanelSection.vue'
import PagesSection from '@/flow/workbench/gallery/sections/PagesSection.vue'
import RenderersSection from '@/flow/workbench/gallery/sections/RenderersSection.vue'
import RunControlsSection from '@/flow/workbench/gallery/sections/RunControlsSection.vue'
import SessionSection from '@/flow/workbench/gallery/sections/SessionSection.vue'
import ComparePage from '@/flow/workbench/pages/ComparePage.vue'
import FlowsPage from '@/flow/workbench/pages/FlowsPage.vue'
import WorkbenchPage from '@/flow/workbench/pages/WorkbenchPage.vue'

const IGNORED_WARNINGS = [
  /Vue Flow parent container needs a width and a height/,
  // jsdom cannot compute SVG layout; vue-flow warns about unmeasurable handles.
  /\[Vue Flow\]/,
]

const unexpected = (spy: { mock: { calls: unknown[][] } }): string[] =>
  spy.mock.calls
    .map((call) => call.map(String).join(' '))
    .filter((message) => !IGNORED_WARNINGS.some((pattern) => pattern.test(message)))

const Empty = defineComponent({ template: '<div />' })

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Empty },
      { path: '/flow/design/:section?', component: Empty },
      { path: '/flow/flows', component: Empty },
      { path: '/flow/work', component: Empty },
      { path: '/flow/compare', component: Empty },
      { path: '/flow/railroad', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
}

async function mountClean(component: unknown, path?: string): Promise<string> {
  const router = testRouter()
  if (path) {
    await router.push(path)
    await router.isReady()
  }
  const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
  const warnings = vi.spyOn(console, 'warn').mockImplementation(() => {})

  const wrapper = mount(component as never, {
    global: { plugins: [router, ToastService] },
  })
  await nextTick()
  await nextTick()

  const html = wrapper.html()
  expect(html.length).toBeGreaterThan(0)
  expect(unexpected(errors)).toEqual([])
  expect(unexpected(warnings)).toEqual([])

  const text = wrapper.text()
  wrapper.unmount()
  errors.mockRestore()
  warnings.mockRestore()
  return text
}

const sections = [
  ['foundations', FoundationsSection],
  ['renderers', RenderersSection],
  ['cell-card', CellCardSection],
  ['run-controls', RunControlsSection],
  ['errors', ErrorsSection],
  ['left-panel', LeftPanelSection],
  ['branch-graph', BranchGraphSection],
  ['session', SessionSection],
  ['compare', CompareSection],
  ['pages', PagesSection],
] as const

describe('design system gallery', () => {
  for (const [name, component] of sections) {
    it(`section ${name} mounts without errors and leaks no internals`, async () => {
      const text = await mountClean(component)
      // §10's error-vocabulary rule: no uid, content hash, or memo key on screen.
      expect(text).not.toMatch(/\buid\b/i)
      expect(text).not.toMatch(/memo key/i)
      expect(text).not.toMatch(/\b[0-9a-f]{16,}\b/i)
    })
  }

  it('gallery shell mounts and lists every registered section', async () => {
    const text = await mountClean(DesignSystemPage, '/flow/design/foundations')
    for (const [, label] of [
      ['foundations', 'Foundations'],
      ['renderers', 'Renderers'],
      ['cell-card', 'Cell card'],
      ['pages', 'Pages'],
    ]) {
      expect(text).toContain(label)
    }
  })
})

describe('workbench pages', () => {
  it('flows picker mounts', async () => {
    const text = await mountClean(FlowsPage, '/flow/flows')
    expect(text).toContain('churn.flow')
    expect(text).toContain('lumlflow init')
  })

  it('compare page mounts with the sweep fixture', async () => {
    const text = await mountClean(ComparePage, '/flow/compare')
    expect(text).toContain('exp/lr-1e3')
    expect(text).toContain('train_model')
  })

  const states = [
    'running',
    'idle',
    'unpaired',
    'empty',
    'kernel-not-started',
    'daemon-down',
    'locked',
  ]
  for (const state of states) {
    it(`workbench mounts in state=${state}`, async () => {
      await mountClean(WorkbenchPage, `/flow/work?state=${state}`)
    })
  }

  it('workbench mounts the notebook view with an asset selected', async () => {
    const text = await mountClean(WorkbenchPage, '/flow/work?view=notebook&asset=train_model')
    expect(text).toContain('train_model')
  })
})
