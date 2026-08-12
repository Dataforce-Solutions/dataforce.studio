import type { FlowState } from '../model/types'

export interface FlowListEntry {
  name: string
  path: string
  state: FlowState
  lastOpened: string
  branchCount: number
  cellCount: number
  diskUsage: string
  pairedAgent?: string
}

export const knownFlows: FlowListEntry[] = [
  {
    name: 'churn.flow',
    path: '~/work/churn-analysis',
    state: 'running',
    lastOpened: 'open now',
    branchCount: 6,
    cellCount: 9,
    diskUsage: '1.8 GB',
    pairedAgent: 'claude-1',
  },
  {
    name: 'support-evals.flow',
    path: '~/work/llm-support',
    state: 'idle',
    lastOpened: '2h ago',
    branchCount: 11,
    cellCount: 6,
    diskUsage: '640 MB',
    pairedAgent: 'codex-a',
  },
  {
    name: 'pricing.flow',
    path: '~/work/pricing-experiments',
    state: 'kernel-not-started',
    lastOpened: '3d ago',
    branchCount: 4,
    cellCount: 14,
    diskUsage: '3.2 GB',
  },
  {
    name: 'onboarding-funnel.flow',
    path: '~/scratch/funnel',
    state: 'daemon-down',
    lastOpened: '3w ago',
    branchCount: 2,
    cellCount: 5,
    diskUsage: '210 MB',
  },
]
