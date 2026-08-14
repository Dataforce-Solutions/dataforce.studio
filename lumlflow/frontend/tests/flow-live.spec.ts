import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  FlowConnectionError,
  FlowRpcError,
  FlowSessionClient,
  type EventSourceFactory,
  type EventSourceLike,
} from '@/flow/api/client'
import { groupTransactionsByIntent } from '@/flow/api/catchup'
import { LiveSessionModel, foldJournalStops, type LiveSessionState } from '@/flow/api/liveSession'
import type {
  JournalTransaction,
  LiveBranch,
  LiveCell as LiveCellRecord,
  LiveSessionSnapshot,
} from '@/flow/api/types'
import FlowShell from '@/flow/FlowShell.vue'
import FlowConnectForm from '@/flow/components/FlowConnectForm.vue'
import LiveCell from '@/flow/components/LiveCell.vue'
import LiveFlowSession from '@/flow/components/LiveFlowSession.vue'

class FakeEventSource implements EventSourceLike {
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  constructor(readonly url: string) {}

  message(value: object): void {
    this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent<string>)
  }

  close(): void {
    this.closed = true
  }
}

const transaction = (step: number): JournalTransaction => ({
  step,
  ts: '2026-08-12T00:00:00Z',
  actor: 'agent:test',
  intent: `step ${step}`,
  offline: false,
  settled: true,
  branch: 'branch-main',
  ops: [{ op: 'flag_set', flag: 'test', enabled: true, uid: null, version_id: null }],
})

const mainLane: LiveBranch = {
  branch_id: 'branch-main',
  name: 'main',
  parent_branch_id: null,
  fork_step: 0,
  archived: false,
  sweep_group: null,
}

const sessionState = (
  snapshot: LiveSessionSnapshot,
  transactions: JournalTransaction[] = [],
  lanes: LiveBranch[] = [mainLane],
): LiveSessionState => ({
  snapshot,
  lanes,
  transactions,
  stops: foldJournalStops(transactions, lanes),
  catchUpGroups: groupTransactionsByIntent(transactions),
  cursor: transactions.length,
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('FlowSessionClient', () => {
  it('reconnects from the last delivered cursor and suppresses replay duplicates', () => {
    vi.useFakeTimers()
    const sources: FakeEventSource[] = []
    const eventSource: EventSourceFactory = (url) => {
      const source = new FakeEventSource(url)
      sources.push(source)
      return source
    }
    const delivered: number[] = []
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      eventSource,
      reconnectDelayMs: 10,
    })

    client.connect({ transaction: (message) => delivered.push(message.cursor) }, 4)
    expect(sources[0].url).toContain('cursor=4')
    sources[0].message({
      channel: 'journal',
      kind: 'transaction',
      cursor: 5,
      transaction: transaction(5),
    })
    sources[0].onerror?.()
    vi.advanceTimersByTime(10)

    expect(sources[1].url).toContain('cursor=5')
    sources[1].message({
      channel: 'journal',
      kind: 'transaction',
      cursor: 5,
      transaction: transaction(5),
    })
    sources[1].message({
      channel: 'journal',
      kind: 'transaction',
      cursor: 6,
      transaction: transaction(6),
    })

    expect(delivered).toEqual([5, 6])
    client.disconnect()
  })

  it('requests snapshots and authenticates with the daemon token', async () => {
    let request: RequestInfo | URL | null = null
    const fetcher: typeof fetch = async (input) => {
      request = input
      return new Response(
        JSON.stringify({ flow_id: 'flow', name: 'demo', branch: 'main', step: 1, cells: [] }),
      )
    }
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: fetcher,
    })

    await expect(client.snapshot()).resolves.toMatchObject({ name: 'demo', step: 1 })
    expect(String(request)).toContain('token=secret')
  })

  it('calls the global fetch without rebinding its receiver', async () => {
    function guardedFetch(this: unknown): Promise<Response> {
      if (this !== undefined && this !== globalThis) {
        throw new TypeError('Illegal invocation')
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ flow_id: 'flow', name: 'demo', branch: 'main', step: 1, cells: [] }),
        ),
      )
    }
    vi.stubGlobal('fetch', guardedFetch)
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret')

    await expect(client.snapshot()).resolves.toMatchObject({ name: 'demo', step: 1 })
  })

  it('calls browser RPC methods and preserves structured daemon errors', async () => {
    const requests: Array<{ input: RequestInfo | URL; options?: RequestInit }> = []
    const fetcher: typeof fetch = async (input, options) => {
      requests.push({ input, options })
      if (requests.length === 1) return new Response(JSON.stringify({ branch: 'main' }))
      return new Response(
        JSON.stringify({
          error: {
            code: -32009,
            message: 'definition changed',
            data: { current_definition_hash: 'definition-2' },
          },
        }),
        { status: 400 },
      )
    }
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: fetcher,
    })

    await expect(client.rpc('tree', { branch: 'main' })).resolves.toEqual({ branch: 'main' })
    expect(String(requests[0].input)).toContain('/api/rpc?token=secret')
    expect(requests[0].options).toMatchObject({
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ method: 'tree', params: { branch: 'main' } }),
    })

    const failure = client.rpc('cells_edit', { slug: 'train' })
    await expect(failure).rejects.toMatchObject({
      code: -32009,
      data: { current_definition_hash: 'definition-2' },
      message: 'definition changed',
      status: 400,
    })
    await expect(failure).rejects.toBeInstanceOf(FlowRpcError)
  })

  it('distinguishes unauthorized responses from an unreachable daemon', async () => {
    const unauthorized = new FlowSessionClient('http://127.0.0.1:9000', 'wrong', {
      fetch: async () =>
        new Response(JSON.stringify({ detail: 'invalid daemon token' }), { status: 401 }),
    })
    const unreachable = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: async () => {
        throw new TypeError('fetch failed')
      },
    })

    await expect(unauthorized.snapshot()).rejects.toMatchObject({ kind: 'unauthorized' })
    await expect(unreachable.snapshot()).rejects.toMatchObject({ kind: 'unreachable' })
    await expect(unauthorized.snapshot()).rejects.toBeInstanceOf(FlowConnectionError)
    await expect(unreachable.snapshot()).rejects.toBeInstanceOf(FlowConnectionError)
  })

  it('bounds a stalled connection attempt and reports it as unreachable', async () => {
    vi.useFakeTimers()
    const fetcher: typeof fetch = async (_input, options) =>
      new Promise<Response>((_resolve, reject) => {
        options?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'))
        })
      })
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: fetcher,
      requestTimeoutMs: 10,
    })

    const snapshot = expect(client.snapshot()).rejects.toMatchObject({ kind: 'unreachable' })
    await vi.advanceTimersByTimeAsync(10)

    await snapshot
  })

  it('requests asset pages through the authenticated browser endpoint', async () => {
    let request: RequestInfo | URL | null = null
    let init: RequestInit | undefined
    const fetcher: typeof fetch = async (input, options) => {
      request = input
      init = options
      return new Response(
        JSON.stringify({ columns: ['score'], rows: [{ score: 0.95 }], offset: 0, total_rows: 1 }),
      )
    }
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: fetcher,
    })

    await expect(client.assetPage('evaluate.results')).resolves.toMatchObject({ total_rows: 1 })
    expect(String(request)).toContain('/api/assets/evaluate/results/page?token=secret')
    expect(init).toMatchObject({ method: 'POST' })
    expect(init?.body).toBe(JSON.stringify({ offset: 0, limit: 100 }))
    await expect(client.assetPage('invalid')).rejects.toThrow('asset target must be slug.output')
  })

  it('sends optimistic parameter edits through the authenticated endpoint', async () => {
    let request: RequestInfo | URL | null = null
    let init: RequestInit | undefined
    const fetcher: typeof fetch = async (input, options) => {
      request = input
      init = options
      return new Response(JSON.stringify({ changed: true }))
    }
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: fetcher,
    })

    await client.editParams('train model', { lr: 0.2 }, 'definition-1')

    expect(String(request)).toContain('/api/cells/train%20model/params?token=secret')
    expect(init?.body).toBe(
      JSON.stringify({ params: { lr: 0.2 }, base_definition_hash: 'definition-1' }),
    )
  })

  it('keeps replay order while grouping catch-up entries by actor and intent', () => {
    const transactions = [
      { ...transaction(5), intent: 'overnight evaluation' },
      { ...transaction(6), intent: 'overnight evaluation' },
      { ...transaction(7), actor: 'agent:other' },
    ]

    const groups = groupTransactionsByIntent(transactions)

    expect(groups).toHaveLength(2)
    expect(groups[0].transactions.map(({ step }) => step)).toEqual([5, 6])
    expect(groups[1].transactions.map(({ step }) => step)).toEqual([7])
  })
})

describe('LiveSessionModel', () => {
  it('folds consecutive routine work into stops and red-tints failures', () => {
    const transactions: JournalTransaction[] = [
      {
        ...transaction(1),
        settled: false,
        intent: 'edit data',
        ops: [
          {
            op: 'cell_accepted',
            uid: 'cell-1',
            version_id: 'version-1',
            slug: 'train',
            source_hash: 'source-1',
            bound_hash: 'bound-1',
            definition_hash: 'definition-1',
            manifest: {},
            flags: [],
            parent_version: null,
            author: 'agent:test',
            copied_from: null,
          },
        ],
      },
      {
        ...transaction(2),
        settled: false,
        intent: 'train model',
        ops: [
          {
            op: 'run_recorded',
            mat_id: 'mat-1',
            version_id: 'version-1',
            memo_key: 'memo-1',
            state: 'failed',
            inputs: {},
            outputs: {},
            identity_dependent: false,
            env_lock_hash: null,
            cost_seconds: 0.1,
            log_ref: null,
            started_step: 2,
            finished_step: 2,
          },
        ],
      },
      { ...transaction(3), settled: true, intent: 'green checkpoint' },
      { ...transaction(4), settled: false, intent: 'edit report' },
    ]

    const stops = foldJournalStops(transactions)

    expect(
      stops.map(({ kind, step, txCount, failed }) => ({ kind, step, txCount, failed })),
    ).toEqual([
      { kind: 'run', step: 2, txCount: 2, failed: true },
      { kind: 'checkpoint', step: 3, txCount: 1, failed: false },
      { kind: 'checkpoint', step: 4, txCount: 1, failed: false },
    ])
    expect(stops[0]).toMatchObject({
      label: '2 edits · agent:test · failed',
      detail: 'agent:test · train',
      affectedCells: ['train'],
    })
  })

  it('loads snapshot staleness and branch ancestry before replaying from cursor zero', async () => {
    const snapshot = {
      flow_id: 'flow',
      name: 'demo',
      branch: 'experiment',
      step: 3,
      cells: [
        {
          uid: 'cell-1',
          slug: 'train',
          version_id: 'version-1',
          definition_hash: 'definition-1',
          source: 'class Train:\n    pass\n',
          manifest: {},
          verdict: {
            direct: { state: 'unsynced' as const, causes: ['definition-changed'] },
            transitive: { state: 'unsynced' as const, causes: ['definition-changed'] },
          },
          outputs: [],
          logs: [],
          run_id: null,
        },
      ],
      sweeps: [],
    }
    let handlers: Parameters<FlowSessionClient['connect']>[0] = {}
    let cursor: number | null = null
    const client = {
      snapshot: vi.fn(async () => snapshot),
      rpc: vi.fn(async () => ({
        branch: 'experiment',
        cells: [],
        branches: [
          {
            branch_id: 'branch-main',
            name: 'main',
            parent_branch_id: null,
            fork_step: 1,
            archived: false,
            sweep_group: null,
          },
          {
            branch_id: 'branch-exp',
            name: 'experiment',
            parent_branch_id: 'branch-main',
            fork_step: 2,
            archived: false,
            sweep_group: null,
          },
        ],
      })),
      connect: vi.fn((receivedHandlers, receivedCursor) => {
        handlers = receivedHandlers
        cursor = receivedCursor
        return { close: vi.fn() }
      }),
    } as unknown as FlowSessionClient

    const model = await LiveSessionModel.connect(client)

    expect(cursor).toBe(0)
    expect(client.rpc).toHaveBeenCalledWith('tree', { branch: 'experiment' })
    expect(model.state.snapshot.cells[0].verdict.transitive).toEqual({
      state: 'unsynced',
      causes: ['definition-changed'],
    })
    expect(model.state.lanes[1]).toMatchObject({
      name: 'experiment',
      parent_branch_id: 'branch-main',
      fork_step: 2,
    })

    handlers.transaction?.({
      channel: 'journal',
      kind: 'transaction',
      cursor: 1,
      transaction: { ...transaction(1), intent: 'initialize demo' },
    })
    handlers.transaction?.({
      channel: 'journal',
      kind: 'transaction',
      cursor: 2,
      transaction: {
        ...transaction(2),
        actor: 'user:ui',
        intent: 'fork candidate',
        branch: 'branch-exp',
        ops: [
          {
            op: 'branch_created',
            branch_id: 'branch-candidate',
            name: 'candidate',
            parent: 'branch-exp',
            fork_step: 2,
            sweep_group: null,
          },
        ],
      },
    })

    expect(model.state.transactions.map(({ step }) => step)).toEqual([1, 2])
    expect(model.state.catchUpGroups.map(({ actor, intent }) => ({ actor, intent }))).toEqual([
      { actor: 'agent:test', intent: 'initialize demo' },
      { actor: 'user:ui', intent: 'fork candidate' },
    ])
    expect(model.state.lanes.at(-1)).toMatchObject({
      branch_id: 'branch-candidate',
      parent_branch_id: 'branch-exp',
      fork_step: 2,
    })
    expect(model.state.stops.find(({ branch }) => branch === 'branch-candidate')).toMatchObject({
      step: 2,
      kind: 'checkpoint',
      label: 'candidate',
      detail: 'forked from experiment',
      txCount: 0,
      laneHead: true,
    })
    expect(
      model.state.stops.every(({ branch }) =>
        model.state.lanes.some(({ branch_id }) => branch_id === branch),
      ),
    ).toBe(true)

    handlers.transaction?.({
      channel: 'journal',
      kind: 'transaction',
      cursor: 3,
      transaction: {
        ...transaction(3),
        actor: 'user:ui',
        intent: 'rename experiment to trial',
        branch: 'branch-exp',
        ops: [
          {
            op: 'branch_renamed',
            branch_id: 'branch-exp',
            old_name: 'experiment',
            new_name: 'trial',
          },
        ],
      },
    })

    expect(model.state.snapshot.branch).toBe('trial')
    expect(model.state.lanes.find(({ branch_id }) => branch_id === 'branch-exp')?.name).toBe(
      'trial',
    )
    model.close()
  })

  it('resumes a model journal connection from its last replayed cursor', async () => {
    vi.useFakeTimers()
    const sources: FakeEventSource[] = []
    const fetcher: typeof fetch = async (input) => {
      const url = String(input)
      if (url.includes('/api/session')) {
        return new Response(
          JSON.stringify({
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 2,
            cells: [],
            sweeps: [],
          }),
        )
      }
      return new Response(
        JSON.stringify({
          branch: 'main',
          cells: [],
          branches: [
            {
              branch_id: 'branch-main',
              name: 'main',
              parent_branch_id: null,
              fork_step: 1,
              archived: false,
              sweep_group: null,
            },
          ],
        }),
      )
    }
    const client = new FlowSessionClient('http://127.0.0.1:9000', 'secret', {
      fetch: fetcher,
      eventSource: (url) => {
        const source = new FakeEventSource(url)
        sources.push(source)
        return source
      },
      reconnectDelayMs: 10,
    })
    const model = await LiveSessionModel.connect(client)

    expect(sources[0].url).toContain('cursor=0')
    sources[0].message({
      channel: 'journal',
      kind: 'transaction',
      cursor: 1,
      transaction: transaction(1),
    })
    sources[0].message({
      channel: 'journal',
      kind: 'transaction',
      cursor: 2,
      transaction: transaction(2),
    })
    sources[0].onerror?.()
    vi.advanceTimersByTime(10)

    expect(sources[1].url).toContain('cursor=2')
    expect(model.state.cursor).toBe(2)
    expect(model.state.transactions.map(({ step }) => step)).toEqual([1, 2])
    model.close()
  })

  it('folds kernel stream events into running cells without waiting for an RPC result', async () => {
    const snapshot: LiveSessionSnapshot = {
      flow_id: 'flow',
      name: 'demo',
      branch: 'main',
      step: 2,
      cells: [
        {
          uid: 'cell-1',
          slug: 'train',
          version_id: 'version-1',
          definition_hash: 'definition-1',
          source: 'class Train:\n    pass\n',
          manifest: {},
          verdict: {
            direct: { state: 'unsynced', causes: ['definition-changed'] },
            transitive: { state: 'unsynced', causes: ['definition-changed'] },
          },
          outputs: [],
          logs: [],
          run_id: null,
        },
      ],
      sweeps: [],
    }
    let handlers: Parameters<FlowSessionClient['connect']>[0] = {}
    const client = {
      snapshot: vi.fn(async () => snapshot),
      rpc: vi.fn(async () => ({ branch: 'main', cells: [], branches: [mainLane] })),
      connect: vi.fn((receivedHandlers) => {
        handlers = receivedHandlers
        return { close: vi.fn() }
      }),
    } as unknown as FlowSessionClient
    const model = await LiveSessionModel.connect(client)

    handlers.kernel?.({
      channel: 'journal',
      kind: 'kernel',
      event: 'started',
      run_id: 'run-streamed',
      payload: { run_id: 'run-streamed', slug: 'train' },
    })

    expect(model.state.snapshot.cells[0].run_id).toBe('run-streamed')

    handlers.kernel?.({
      channel: 'journal',
      kind: 'kernel',
      event: 'failed',
      run_id: 'run-streamed',
      payload: { run_id: 'run-streamed', slug: 'train', state: 'failed' },
    })

    expect(model.state.snapshot.cells[0].run_id).toBeNull()
    await flushPromises()
    expect(model.state.snapshot.cells[0].run_id).toBeNull()
    model.close()
  })
})

describe('FlowConnectForm', () => {
  it('prefills deep-link coordinates, surfaces connection states, and supports retry', async () => {
    const wrapper = mount(FlowConnectForm, {
      props: {
        initialBaseUrl: 'http://127.0.0.1:9010',
        initialToken: 'deep-link-token',
        error: 'Daemon rejected the token. Check it and try again.',
        errorKind: 'unauthorized',
      },
    })

    expect(wrapper.get<HTMLInputElement>('[name="daemon-url"]').element.value).toBe(
      'http://127.0.0.1:9010',
    )
    expect(wrapper.get<HTMLInputElement>('[name="daemon-token"]').element.value).toBe(
      'deep-link-token',
    )
    expect(wrapper.get('[role="alert"]').attributes('data-connection-error')).toBe('unauthorized')

    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('connect')).toEqual([
      [{ baseUrl: 'http://127.0.0.1:9010', token: 'deep-link-token' }],
      [{ baseUrl: 'http://127.0.0.1:9010', token: 'deep-link-token' }],
    ])
  })

  it('remembers recent connections and restores their tokens', async () => {
    localStorage.clear()
    const first = mount(FlowConnectForm)
    await first.get('[name="daemon-url"]').setValue('http://127.0.0.1:9020/')
    await first.get('[name="daemon-token"]').setValue('remembered-token')
    await first.get('form').trigger('submit')
    first.unmount()

    const second = mount(FlowConnectForm)
    await second.get('[data-recent-connections]').setValue('http://127.0.0.1:9020')

    expect(second.get<HTMLInputElement>('[name="daemon-url"]').element.value).toBe(
      'http://127.0.0.1:9020',
    )
    expect(second.get<HTMLInputElement>('[name="daemon-token"]').element.value).toBe(
      'remembered-token',
    )
  })
})

describe('FlowShell live connection', () => {
  it('distinguishes connection failures, stops waiting, and recovers on retry', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'invalid daemon token' }), { status: 401 }),
      )
      .mockRejectedValueOnce(new TypeError('fetch failed'))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 1,
            cells: [],
            sweeps: [],
          }),
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            branch: 'main',
            cells: [],
            branches: [
              {
                branch_id: 'branch-main',
                name: 'main',
                parent_branch_id: null,
                fork_step: 1,
                archived: false,
                sweep_group: null,
              },
            ],
          }),
        ),
      )
    vi.stubGlobal('fetch', fetcher)
    vi.stubGlobal('EventSource', FakeEventSource)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/flow/railroad', component: { template: '<div />' } }],
    })
    await router.push('/flow/railroad?live=http://127.0.0.1:9010&token=deep-link-token')
    await router.isReady()

    const wrapper = mount(FlowShell, {
      global: {
        plugins: [router],
        stubs: { LiveFlowSession: true },
      },
    })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').attributes('data-connection-error')).toBe('unauthorized')
    expect(wrapper.get('button[type="submit"]').text()).toBe('Connect')

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').attributes('data-connection-error')).toBe('unreachable')
    expect(wrapper.get('button[type="submit"]').text()).toBe('Connect')

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Connected')
    expect(wrapper.text()).toContain('Live at journal step 1')
  })

  it('renders agent CLI journal events in catch-up while connected', async () => {
    const snapshots = [
      { flow_id: 'flow', name: 'demo', branch: 'main', step: 1, cells: [], sweeps: [] },
      { flow_id: 'flow', name: 'demo', branch: 'main', step: 2, cells: [], sweeps: [] },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async (input) => {
        if (String(input).includes('/api/rpc')) {
          return new Response(
            JSON.stringify({
              branch: 'main',
              cells: [],
              branches: [
                {
                  branch_id: 'branch-main',
                  name: 'main',
                  parent_branch_id: null,
                  fork_step: 1,
                  archived: false,
                  sweep_group: null,
                },
              ],
            }),
          )
        }
        return new Response(JSON.stringify(snapshots.shift()))
      }),
    )
    const sources: FakeEventSource[] = []
    class RecordingEventSource extends FakeEventSource {
      constructor(url: string) {
        super(url)
        sources.push(this)
      }
    }
    vi.stubGlobal('EventSource', RecordingEventSource)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/flow/railroad', component: { template: '<div />' } }],
    })
    await router.push('/flow/railroad?live=http://127.0.0.1:9010&token=token')
    await router.isReady()
    const wrapper = mount(FlowShell, { global: { plugins: [router] } })
    await flushPromises()

    sources[0].message({
      channel: 'journal',
      kind: 'transaction',
      cursor: 2,
      transaction: {
        ...transaction(2),
        actor: 'agent:cli:test',
        intent: 'build agent cell',
      },
    })
    await flushPromises()

    const catchUp = wrapper.get('[data-catchup-group]')
    expect(catchUp.text()).toContain('agent:cli:test')
    expect(catchUp.text()).toContain('build agent cell')
    expect(wrapper.text()).toContain('Live at journal step 2')
    wrapper.unmount()
  })
})

describe('LiveCell', () => {
  it('launches JSON parameter values as overrides and runs sweep variants serially', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: { params: { learning_rate: 0.1, epochs: 10 } },
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const firstRun = Promise.withResolvers<object>()
    const rpc = vi.fn((method: string) => {
      if (method === 'sweep') {
        return Promise.resolve({
          group: 'train-2',
          variants: [
            { branch: 'sweep/train-2/1', branch_id: 'branch-sweep-1' },
            { branch: 'sweep/train-2/2', branch_id: 'branch-sweep-2' },
            { branch: 'sweep/train-2/3', branch_id: 'branch-sweep-3' },
          ],
        })
      }
      if (method === 'run' && rpc.mock.calls.filter(([name]) => name === 'run').length === 1) {
        return firstRun.promise
      }
      return Promise.resolve({})
    })
    const wrapper = mount(LiveCell, {
      props: { cell, client: { rpc } as unknown as FlowSessionClient, branch: 'main' },
    })

    await wrapper.get('[data-open-sweep]').trigger('click')
    await wrapper.get('[data-sweep-values]').setValue('[0.2, 0.3, 0.4]')
    await wrapper.get('[data-sweep-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenNthCalledWith(1, 'sweep', {
      slug: 'train',
      overrides: [{ learning_rate: 0.2 }, { learning_rate: 0.3 }, { learning_rate: 0.4 }],
      parent: 'main',
      actor: 'user:ui',
      intent: 'sweep train.learning_rate',
    })
    expect(rpc).toHaveBeenNthCalledWith(2, 'run', {
      target: 'train',
      branch: 'branch-sweep-1',
      force: false,
      actor: 'user:ui',
      intent: 'run train sweep train-2 variant 1',
    })
    expect(rpc).toHaveBeenCalledTimes(2)

    firstRun.resolve({})
    await flushPromises()

    expect(rpc).toHaveBeenNthCalledWith(3, 'run', {
      target: 'train',
      branch: 'branch-sweep-2',
      force: false,
      actor: 'user:ui',
      intent: 'run train sweep train-2 variant 2',
    })
    expect(rpc).toHaveBeenNthCalledWith(4, 'run', {
      target: 'train',
      branch: 'branch-sweep-3',
      force: false,
      actor: 'user:ui',
      intent: 'run train sweep train-2 variant 3',
    })
    expect(wrapper.get('[data-sweep-status]').text()).toContain('Sweep train-2 completed')
  })

  it('rejects empty and malformed sweep value lists before making a request', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: { params: { learning_rate: 0.1 } },
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const rpc = vi.fn()
    const wrapper = mount(LiveCell, {
      props: { cell, client: { rpc } as unknown as FlowSessionClient, branch: 'main' },
    })

    await wrapper.get('[data-open-sweep]').trigger('click')
    await wrapper.get('[data-sweep-values]').setValue('{"learning_rate": 0.2}')
    await wrapper.get('[data-sweep-form]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-sweep-error]').text()).toContain('non-empty JSON array')
    expect(rpc).not.toHaveBeenCalled()
  })

  it('surfaces sweep request failures and does not start variant runs', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: { params: { learning_rate: 0.1 } },
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const rpc = vi
      .fn()
      .mockRejectedValue(new FlowRpcError(-32004, 'cell not found: train', null, 404))
    const wrapper = mount(LiveCell, {
      props: { cell, client: { rpc } as unknown as FlowSessionClient, branch: 'main' },
    })

    await wrapper.get('[data-open-sweep]').trigger('click')
    await wrapper.get('[data-sweep-values]').setValue('[0.2, 0.3, 0.4]')
    await wrapper.get('[data-sweep-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-sweep-error]').text()).toContain('cell not found: train')
  })

  it('saves code with the definition hash and UI attribution', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const rpc = vi.fn(async () => ({ definition_hash: 'definition-2' }))
    const client = { rpc } as unknown as FlowSessionClient
    const wrapper = mount(LiveCell, { props: { cell, client } })

    await wrapper.get('[data-code-editor]').setValue('class Train:\n    value = 2\n')
    await wrapper.get('[data-code-editor-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('cells_edit', {
      slug: 'train',
      source: 'class Train:\n    value = 2\n',
      base_definition_hash: 'definition-1',
      actor: 'user:ui',
      intent: 'edit train',
    })
    expect(wrapper.get('[data-edit-pending-acceptance]').text()).toContain('journal acceptance')
  })

  it('surfaces an edit conflict and reloads the daemon source and definition hash', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const rpc = vi
      .fn()
      .mockRejectedValueOnce(
        new FlowRpcError(
          -32009,
          'train changed since it was loaded',
          {
            current_definition_hash: 'definition-agent',
            current_source: 'class Train:\n    agent_value = 3\n',
          },
          409,
        ),
      )
      .mockResolvedValueOnce({ definition_hash: 'definition-2' })
    const client = { rpc } as unknown as FlowSessionClient
    const wrapper = mount(LiveCell, { props: { cell, client } })

    await wrapper.get('[data-code-editor]').setValue('class Train:\n    user_value = 2\n')
    await wrapper.get('[data-code-editor-form]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-edit-conflict]').text()).toContain('changed since it was loaded')
    await wrapper.get('[data-reload-code]').trigger('click')
    expect(wrapper.get<HTMLTextAreaElement>('[data-code-editor]').element.value).toBe(
      'class Train:\n    agent_value = 3\n',
    )

    await wrapper
      .get('[data-code-editor]')
      .setValue('class Train:\n    agent_value = 3\n    user_value = 2\n')
    await wrapper.get('[data-code-editor-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('cells_edit', {
      slug: 'train',
      source: 'class Train:\n    agent_value = 3\n    user_value = 2\n',
      base_definition_hash: 'definition-agent',
      actor: 'user:ui',
      intent: 'edit train',
    })
  })

  it('fixes a failed cell in the code tab and reruns it after journal acceptance', async () => {
    const failedCell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-failed',
      definition_hash: 'definition-failed',
      source: 'class Train:\n    raise RuntimeError("broken")\n',
      manifest: {},
      verdict: {
        direct: { state: 'failed', causes: ['materialization-failed'] },
        transitive: { state: 'failed', causes: ['materialization-failed'] },
      },
      outputs: [],
      logs: [
        {
          run_id: 'run-failed',
          stream: 'stderr',
          seq: 0,
          bytes: 'Traceback: RuntimeError: broken\n',
        },
      ],
      run_id: null,
    }
    const rpc = vi.fn(async () => ({}))
    const client = { rpc } as unknown as FlowSessionClient
    const wrapper = mount(LiveCell, { props: { cell: failedCell, client, branch: 'main' } })

    expect(wrapper.get('[data-run-failure]').text()).toContain('latest materialization failed')
    expect(wrapper.text()).toContain('Traceback: RuntimeError: broken')

    await wrapper.findAll('[role="tab"]')[0].trigger('click')
    await wrapper.get('[data-code-editor]').setValue('class Train:\n    pass\n')
    await wrapper.get('[data-code-editor-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('cells_edit', {
      slug: 'train',
      source: 'class Train:\n    pass\n',
      base_definition_hash: 'definition-failed',
      actor: 'user:ui',
      intent: 'edit train',
    })

    await wrapper.setProps({
      cell: {
        ...failedCell,
        version_id: 'version-fixed',
        definition_hash: 'definition-fixed',
        source: 'class Train:\n    pass\n',
        verdict: {
          direct: { state: 'unsynced', causes: ['definition-changed'] },
          transitive: { state: 'unsynced', causes: ['definition-changed'] },
        },
        logs: [],
      },
    })
    await wrapper.get('[data-run-cell]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('run', {
      target: 'train',
      branch: 'main',
      force: false,
      actor: 'user:ui',
      intent: 'run train',
    })

    await wrapper.setProps({
      cell: {
        ...failedCell,
        version_id: 'version-fixed',
        definition_hash: 'definition-fixed',
        source: 'class Train:\n    pass\n',
        verdict: {
          direct: { state: 'synced', causes: [] },
          transitive: { state: 'synced', causes: [] },
        },
        logs: [],
      },
    })
    expect(wrapper.find('[data-run-failure]').exists()).toBe(false)
    expect(wrapper.text()).toContain('synced')
  })

  it('wires run, force-run, cancel, and request errors with UI attribution', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'unsynced', causes: ['definition-changed'] },
        transitive: { state: 'unsynced', causes: ['definition-changed'] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const rpc = vi.fn(async () => ({}))
    const client = {
      rpc,
      subscribeRunLogs: vi.fn((_runId, handler) => {
        handler({
          channel: 'run-log',
          kind: 'chunk',
          run_id: 'run-1',
          chunk: { run_id: 'run-1', stream: 'stdout', seq: 0, bytes: 'epoch 1\n' },
        })
        return { close: vi.fn() }
      }),
    } as unknown as FlowSessionClient
    const wrapper = mount(LiveCell, { props: { cell, client, branch: 'main' } })

    await wrapper.get('[data-run-cell]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenLastCalledWith('run', {
      target: 'train',
      branch: 'main',
      force: false,
      actor: 'user:ui',
      intent: 'run train',
    })

    await wrapper.get('[data-force-run-cell]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenLastCalledWith('run', {
      target: 'train',
      branch: 'main',
      force: true,
      actor: 'user:ui',
      intent: 'force run train',
    })

    await wrapper.setProps({ cell: { ...cell, run_id: 'run-1' } })
    expect(wrapper.get('[data-running-badge]').text()).toBe('Running')
    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe('console')
    expect(wrapper.text()).toContain('epoch 1')
    await wrapper.get('[data-cancel-cell]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenLastCalledWith('cancel', { run_id: 'run-1' })

    rpc.mockRejectedValueOnce(new Error('cancel unavailable'))
    await wrapper.get('[data-cancel-cell]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-run-error]').text()).toContain('cancel unavailable')

    await wrapper.setProps({ cell })
    rpc.mockRejectedValueOnce(new Error('run unavailable'))
    await wrapper.get('[data-run-cell]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-run-error]').text()).toContain('run unavailable')
  })

  it('releases the pending request when streamed run state takes over', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'unsynced', causes: ['definition-changed'] },
        transitive: { state: 'unsynced', causes: ['definition-changed'] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const client = {
      rpc: vi.fn(() => new Promise<never>(() => {})),
      subscribeRunLogs: vi.fn(() => ({ close: vi.fn() })),
    } as unknown as FlowSessionClient
    const wrapper = mount(LiveCell, { props: { cell, client, branch: 'main' } })

    await wrapper.get('[data-run-cell]').trigger('click')
    expect(wrapper.get<HTMLButtonElement>('[data-run-cell]').element.disabled).toBe(true)

    await wrapper.setProps({ cell: { ...cell, run_id: 'run-streamed' } })
    await wrapper.setProps({ cell })

    expect(wrapper.get<HTMLButtonElement>('[data-run-cell]').element.disabled).toBe(false)
    expect(wrapper.get<HTMLButtonElement>('[data-force-run-cell]').element.disabled).toBe(false)
  })

  it('shows every output plus code, logs, and a live console tab', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: { params: { lr: 0.1 } },
      verdict: {
        direct: { state: 'unsynced', causes: ['definition-changed'] },
        transitive: { state: 'unsynced', causes: ['definition-changed'] },
      },
      outputs: [
        {
          name: 'model',
          kind: 'frame',
          content_hash: 'content-hash',
          preview: { schema: 1, kind: 'model', blocks: [{ type: 'kv', items: [] }] },
        },
        { name: 'metrics', kind: 'metric', content_hash: null, preview: null },
      ],
      logs: [{ run_id: 'old-run', stream: 'stdout', seq: 0, bytes: 'saved log\n' }],
      run_id: 'run-1',
    }
    const close = vi.fn()
    const client = {
      assetPage: vi.fn(async () => ({
        columns: ['score'],
        rows: [{ score: 0.95 }],
        offset: 0,
        total_rows: 1,
      })),
      editParams: vi.fn(async () => ({ changed: true })),
      subscribeRunLogs: vi.fn((_runId, handler) => {
        handler({
          channel: 'run-log',
          kind: 'chunk',
          run_id: 'run-1',
          chunk: { run_id: 'run-1', stream: 'stdout', seq: 1, bytes: 'live log\n' },
        })
        return { close }
      }),
    } as unknown as FlowSessionClient
    const wrapper = mount(LiveCell, { props: { cell, client } })

    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).toEqual([
      'model',
      'metrics',
      'code',
      'logs',
      'console',
    ])
    expect(wrapper.text()).toContain('code or parameters changed')
    const parameterInput = wrapper.find('[data-param-inspector] input')
    await parameterInput.setValue('0.2')
    await wrapper.find('[data-param-inspector]').trigger('submit')
    await flushPromises()
    expect(client.editParams).toHaveBeenCalledWith('train', { lr: 0.2 }, 'definition-1')

    await wrapper.findAll('[role="tab"]')[2].trigger('click')
    expect(wrapper.get<HTMLTextAreaElement>('[data-code-editor]').element.value).toContain(
      'class Train:',
    )
    await wrapper.findAll('[role="tab"]')[4].trigger('click')
    expect(wrapper.text()).toContain('live log')
    await wrapper.findAll('[role="tab"]')[0].trigger('click')
    await wrapper.find('[data-expand-page]').trigger('click')
    await flushPromises()
    expect(client.assetPage).toHaveBeenCalledWith('train.model')
    expect(wrapper.text()).toContain('0.95')

    wrapper.unmount()
    expect(close).toHaveBeenCalled()
  })
})

describe('LiveFlowSession', () => {
  const branchOperationState = (): LiveSessionState => {
    const candidateLane: LiveBranch = {
      branch_id: 'branch-candidate',
      name: 'candidate',
      parent_branch_id: 'branch-main',
      fork_step: 1,
      archived: false,
      sweep_group: null,
    }
    const candidateTransaction: JournalTransaction = {
      ...transaction(2),
      branch: candidateLane.branch_id,
      actor: 'user:ui',
      intent: 'tune candidate',
    }
    return sessionState(
      {
        flow_id: 'flow',
        name: 'demo',
        branch: 'main',
        step: 2,
        cells: [],
        sweeps: [],
      },
      [transaction(1), candidateTransaction],
      [mainLane, candidateLane],
    )
  }

  const branchDiff = () => ({
    left: 'main',
    right: 'candidate',
    differences: [
      {
        uid: '01JRAWINTERNALCELLIDENTIFIER',
        cell: 'train',
        divergence: 'definition',
        left_version: 'version-main',
        right_version: 'version-candidate',
        left_params: { learning_rate: 0.1 },
        right_params: { learning_rate: 0.2 },
        left_outputs: { score: '11111111111111111111111111111111' },
        right_outputs: { score: '22222222222222222222222222222222' },
      },
    ],
  })

  it('evaluates scratch expressions on the active branch and renders preview primitives', async () => {
    const rpc = vi.fn(async () => ({
      state: 'succeeded',
      result: '<Frame 2 x 2>',
      result_type: 'DataFrame',
      stdout: 'inspecting frame\n',
      stderr: '',
      touched: ['prepare.frame'],
      preview: {
        schema: 1,
        kind: 'frame',
        blocks: [
          {
            type: 'table',
            columns: ['customer', 'score'],
            rows: [
              ['Ada', 0.95],
              ['Lin', 0.91],
            ],
            total_rows: 2,
          },
        ],
      },
    }))
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-scratch-input]').setValue('prepare.frame.head(2)')
    await wrapper.get('[data-run-scratch]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('eval', {
      code: 'prepare.frame.head(2)',
      branch: 'branch-main',
    })
    const result = wrapper.get('[data-scratch-result]')
    expect(result.text()).toContain('customer')
    expect(result.text()).toContain('Ada')
    expect(result.text()).toContain('0.91')
    expect(wrapper.get('[data-scratch-console]').text()).toContain('inspecting frame')
    expect(wrapper.get<HTMLInputElement>('[data-scratch-input]').element.value).toBe('')
  })

  it('renders scratch evaluation errors without discarding the expression', async () => {
    const rpc = vi.fn(async () => {
      throw new FlowRpcError(-32010, "NameError: name 'missing' is not defined", null, 400)
    })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-scratch-input]').setValue('missing')
    await wrapper.get('[data-run-scratch]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-scratch-error]').text()).toBe(
      "NameError: name 'missing' is not defined",
    )
    expect(wrapper.get<HTMLInputElement>('[data-scratch-input]').element.value).toBe('missing')
    expect(wrapper.find('[data-scratch-result]').exists()).toBe(false)
  })

  it('renders branch diff parameters and output hashes without exposing cell uids', async () => {
    const rpc = vi.fn(async () => branchDiff())
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-open-branch-diff]').trigger('click')
    await wrapper.get('[data-diff-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('diff', {
      left: 'branch-main',
      right: 'branch-candidate',
    })
    const row = wrapper.get('[data-diff-row]')
    expect(row.text()).toContain('train')
    expect(row.text()).toContain('parameters and definition')
    expect(row.text()).toContain('{"learning_rate":0.1}')
    expect(row.text()).toContain('{"learning_rate":0.2}')
    expect(row.text()).toContain('111111111111')
    expect(row.text()).toContain('222222222222')
    expect(wrapper.text()).not.toContain('01JRAWINTERNALCELLIDENTIFIER')
  })

  it('keeps the comparison open and surfaces diff request failures', async () => {
    const rpc = vi.fn(async () => {
      throw new FlowRpcError(-32004, 'branch not found: candidate', null, 404)
    })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-open-branch-diff]').trigger('click')
    await wrapper.get('[data-diff-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('diff', {
      left: 'branch-main',
      right: 'branch-candidate',
    })
    expect(wrapper.get('[data-diff-error]').text()).toBe('branch not found: candidate')
    expect(wrapper.find('[data-branch-diff]').exists()).toBe(true)
    expect(wrapper.find('[data-diff-row]').exists()).toBe(false)
  })

  it('adopts a changed cell from the comparison into the baseline with UI attribution', async () => {
    const rpc = vi
      .fn()
      .mockResolvedValueOnce(branchDiff())
      .mockResolvedValueOnce({ cell: 'train', from: 'candidate', branch: 'main', adopted: true })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-open-branch-diff]').trigger('click')
    await wrapper.get('[data-diff-form]').trigger('submit')
    await flushPromises()
    await wrapper.get('[data-adopt-cell]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('adopt', {
      slug: 'train',
      from_branch: 'branch-candidate',
      branch: 'branch-main',
      actor: 'user:ui',
      intent: 'adopt train from candidate into main',
    })
    expect(wrapper.get('[data-adopt-success]').text()).toBe(
      'Adopted train from candidate into main.',
    )
  })

  it('keeps the diff open and surfaces daemon adopt conflicts on the changed cell', async () => {
    const rpc = vi
      .fn()
      .mockResolvedValueOnce(branchDiff())
      .mockRejectedValueOnce(
        new FlowRpcError(
          -32009,
          'adopt conflict for train: both branches edited it since their fork point',
          { kind: 'definition', cell: 'train' },
          400,
        ),
      )
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-open-branch-diff]').trigger('click')
    await wrapper.get('[data-diff-form]').trigger('submit')
    await flushPromises()
    await wrapper.get('[data-adopt-cell]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-adopt-error]').text()).toContain('adopt conflict for train')
    expect(wrapper.find('[data-branch-diff]').exists()).toBe(true)
    expect(wrapper.find('[data-adopt-success]').exists()).toBe(false)
  })

  it('switches branches when a different lane head is selected and surfaces failures', async () => {
    const rpc = vi
      .fn()
      .mockResolvedValueOnce({ branch: 'candidate' })
      .mockRejectedValueOnce(new FlowRpcError(-32009, 'worktree is locked', null, 400))
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })
    const candidateHead = wrapper.get('[data-stop-key="branch-candidate@2-2"]')

    await candidateHead.trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('switch', {
      branch: 'branch-candidate',
      actor: 'user:ui',
      intent: 'switch to candidate',
    })
    expect(wrapper.find('[data-transaction-detail]').exists()).toBe(false)

    await candidateHead.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-branch-error]').text()).toBe('worktree is locked')
  })

  it('shows a fork slice and restores the untouched trunk slice when switching lanes', async () => {
    const candidateLane: LiveBranch = {
      branch_id: 'branch-candidate',
      name: 'candidate',
      parent_branch_id: 'branch-main',
      fork_step: 1,
      archived: false,
      sweep_group: null,
    }
    const cell = (source: string, version: string): LiveCellRecord => ({
      uid: 'cell-train',
      slug: 'train',
      version_id: version,
      definition_hash: `definition-${version}`,
      source,
      manifest: {},
      verdict: {
        direct: { state: 'unmaterialized', causes: ['never-run'] },
        transitive: { state: 'unmaterialized', causes: ['never-run'] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    })
    const trunkCell = cell('class Train:\n    learning_rate = 0.1\n', 'trunk')
    const candidateCell = cell('class Train:\n    learning_rate = 0.2\n', 'candidate')
    const rpc = vi.fn(async () => ({ branch: 'candidate' }))
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 1,
            cells: [trunkCell],
            sweeps: [],
          },
          [transaction(1)],
          [mainLane, candidateLane],
        ),
      },
    })

    expect(wrapper.findAll('[data-rail-lane]')).toHaveLength(2)
    await wrapper.get('[data-stop-key="branch-candidate@1-1"]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenLastCalledWith('switch', {
      branch: 'branch-candidate',
      actor: 'user:ui',
      intent: 'switch to candidate',
    })

    await wrapper.setProps({
      state: sessionState(
        {
          flow_id: 'flow',
          name: 'demo',
          branch: 'candidate',
          step: 2,
          cells: [candidateCell],
          sweeps: [],
        },
        [
          transaction(1),
          { ...transaction(2), branch: 'branch-candidate', intent: 'edit train on candidate' },
        ],
        [mainLane, candidateLane],
      ),
    })
    await wrapper.get('[data-cell-slug="train"] [role="tab"]:nth-child(1)').trigger('click')
    expect(wrapper.get<HTMLTextAreaElement>('[data-code-editor]').element.value).toContain(
      'learning_rate = 0.2',
    )

    await wrapper.get('[data-stop-key="branch-main@1-1"]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenLastCalledWith('switch', {
      branch: 'branch-main',
      actor: 'user:ui',
      intent: 'switch to main',
    })

    await wrapper.setProps({
      state: sessionState(
        {
          flow_id: 'flow',
          name: 'demo',
          branch: 'main',
          step: 2,
          cells: [trunkCell],
          sweeps: [],
        },
        [
          transaction(1),
          { ...transaction(2), branch: 'branch-candidate', intent: 'edit train on candidate' },
        ],
        [mainLane, candidateLane],
      ),
    })
    expect(wrapper.get<HTMLTextAreaElement>('[data-code-editor]').element.value).toContain(
      'learning_rate = 0.1',
    )
  })

  it('forks from the selected stop with its parent and historical step', async () => {
    const rpc = vi
      .fn()
      .mockRejectedValueOnce(new FlowRpcError(-32602, 'branch already exists', null, 400))
      .mockResolvedValueOnce({ branch: 'candidate', fork_step: 1 })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[data-stop-key="branch-main@1-1"]').trigger('click')
    await wrapper.get('[data-fork-from-stop]').trigger('click')
    await wrapper.get('[name="fork-name"]').setValue('candidate-two')
    await wrapper.get('[data-fork-form]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-fork-form] [role="alert"]').text()).toBe('branch already exists')
    expect(wrapper.find('[data-fork-form]').exists()).toBe(true)

    await wrapper.get('[data-fork-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('fork', {
      name: 'candidate-two',
      parent: 'branch-main',
      step: 1,
      actor: 'user:ui',
      intent: 'fork candidate-two from main',
    })
    expect(wrapper.find('[data-fork-form]').exists()).toBe(false)
  })

  it('renames the active branch inline with UI attribution', async () => {
    const rpc = vi
      .fn()
      .mockRejectedValueOnce(new FlowRpcError(-32602, 'branch name is in use', null, 400))
      .mockResolvedValueOnce({ branch: 'branch-main', name: 'trunk' })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: branchOperationState(),
      },
    })

    await wrapper.get('[aria-label="Rename branch"]').trigger('click')
    await wrapper.get('[name="branch-name"]').setValue('trunk')
    await wrapper.get('[data-branch-rename]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-branch-error]').text()).toBe('branch name is in use')
    expect(wrapper.find('[data-branch-rename]').exists()).toBe(true)

    await wrapper.get('[data-branch-rename]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('rename', {
      branch: 'branch-main',
      name: 'trunk',
      actor: 'user:ui',
      intent: 'rename main to trunk',
    })
    expect(wrapper.find('[data-branch-rename]').exists()).toBe(false)
  })

  it('shows rewind impact before sending the confirmed rewind', async () => {
    let preflightAttempts = 0
    let rewindAttempts = 0
    const rpc = vi.fn(async (method: string) => {
      if (method === 'preflight') {
        preflightAttempts += 1
        if (preflightAttempts === 1) {
          throw new FlowRpcError(-32602, 'stop is no longer available', null, 400)
        }
        return {
          branch: 'main',
          to_step: 1,
          recompute: [
            { cell: 'train', cost_seconds: 2.5 },
            { cell: 'evaluate', cost_seconds: null },
          ],
          irrecoverable: ['plot.figure'],
        }
      }
      rewindAttempts += 1
      if (rewindAttempts === 1) {
        throw new FlowRpcError(-32009, 'branch changed during review', null, 400)
      }
      return { branch: 'main', to_step: 1, step: 3 }
    })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 2,
            cells: [],
            sweeps: [],
          },
          [transaction(1), transaction(2)],
        ),
      },
    })

    await wrapper.get('[data-stop-key="branch-main@1-1"]').trigger('click')
    await wrapper.get('[data-rewind-preflight]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenCalledTimes(1)
    expect(rpc).toHaveBeenCalledWith('preflight', { branch: 'branch-main', step: 1 })
    expect(wrapper.get('[data-branch-error]').text()).toBe('stop is no longer available')

    await wrapper.get('[data-rewind-preflight]').trigger('click')
    await flushPromises()

    const confirmation = wrapper.get('[data-rewind-confirmation]')
    expect(confirmation.text()).toContain('2 cells will need recomputation')
    expect(confirmation.text()).toContain('estimated cost unknown')
    expect(confirmation.text()).toContain('Irrecoverable: plot.figure')

    await confirmation.get('[data-confirm-rewind]').trigger('click')
    await flushPromises()

    expect(confirmation.get('[role="alert"]').text()).toBe('branch changed during review')
    expect(wrapper.find('[data-rewind-confirmation]').exists()).toBe(true)

    await confirmation.get('[data-confirm-rewind]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('rewind', {
      branch: 'branch-main',
      step: 1,
      actor: 'user:ui',
      intent: 'rewind main to step 1',
    })
    expect(wrapper.find('[data-rewind-confirmation]').exists()).toBe(false)
  })

  it('creates a cell through RPC and waits for journal acceptance before rendering its card', async () => {
    const rpc = vi.fn(async () => ({ slug: 'report', definition_hash: 'definition-report' }))
    const client = { rpc } as unknown as FlowSessionClient
    const initialSnapshot: LiveSessionSnapshot = {
      flow_id: 'flow',
      name: 'demo',
      branch: 'main',
      step: 2,
      cells: [],
      sweeps: [],
    }
    const wrapper = mount(LiveFlowSession, {
      props: { client, state: sessionState(initialSnapshot, [transaction(2)]) },
    })

    await wrapper.get('[data-new-cell]').trigger('click')
    await wrapper.get('[name="new-cell-slug"]').setValue('report')
    await wrapper.get('[data-new-cell-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('cells_new', {
      slug: 'report',
      actor: 'user:ui',
      intent: 'create report',
    })
    expect(wrapper.findAll('[data-live-canvas-card]')).toHaveLength(0)
    expect(wrapper.get('[data-create-pending-acceptance]').text()).toContain('journal acceptance')

    const report: LiveCellRecord = {
      uid: 'cell-report',
      slug: 'report',
      version_id: 'version-report',
      definition_hash: 'definition-report',
      source: 'class Report:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'unmaterialized', causes: ['never-run'] },
        transitive: { state: 'unmaterialized', causes: ['never-run'] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const acceptance: JournalTransaction = {
      ...transaction(3),
      actor: 'user:ui',
      intent: 'create report',
      ops: [
        {
          op: 'cell_accepted',
          uid: report.uid,
          version_id: report.version_id,
          slug: report.slug,
          source_hash: 'source-report',
          bound_hash: 'bound-report',
          definition_hash: report.definition_hash,
          manifest: {},
          flags: [],
          parent_version: null,
          author: 'user:ui',
          copied_from: null,
        },
      ],
    }
    await wrapper.setProps({
      state: sessionState({ ...initialSnapshot, step: 3, cells: [report] }, [
        transaction(2),
        acceptance,
      ]),
    })

    expect(wrapper.get('[data-cell-slug="report"] h3').text()).toBe('report')
    expect(wrapper.find('[data-new-cell-form]').exists()).toBe(false)
  })

  it('keeps the new-cell form open when creation is rejected', async () => {
    const client = {
      rpc: vi.fn(async () => {
        throw new FlowRpcError(-32602, 'slug must be snake_case', null, 400)
      }),
    } as unknown as FlowSessionClient
    const wrapper = mount(LiveFlowSession, {
      props: {
        client,
        state: sessionState({
          flow_id: 'flow',
          name: 'demo',
          branch: 'main',
          step: 1,
          cells: [],
          sweeps: [],
        }),
      },
    })

    await wrapper.get('[data-new-cell]').trigger('click')
    await wrapper.get('[name="new-cell-slug"]').setValue('Not Valid')
    await wrapper.get('[data-new-cell-form]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-new-cell-form] [role="alert"]').text()).toBe(
      'slug must be snake_case',
    )
    expect(wrapper.find('[data-create-pending-acceptance]').exists()).toBe(false)
    expect(wrapper.findAll('[data-live-canvas-card]')).toHaveLength(0)
  })

  it('pulses the active rail and streams a running card console from event state', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'unsynced', causes: ['definition-changed'] },
        transitive: { state: 'unsynced', causes: ['definition-changed'] },
      },
      outputs: [],
      logs: [],
      run_id: 'run-streamed',
    }
    const client = {
      subscribeRunLogs: vi.fn((_runId, handler) => {
        handler({
          channel: 'run-log',
          kind: 'chunk',
          run_id: 'run-streamed',
          chunk: { run_id: 'run-streamed', stream: 'stdout', seq: 0, bytes: 'working\n' },
        })
        return { close: vi.fn() }
      }),
    } as unknown as FlowSessionClient
    const wrapper = mount(LiveFlowSession, {
      props: {
        client,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 2,
            cells: [cell],
            sweeps: [],
          },
          [transaction(2)],
        ),
      },
    })

    expect(wrapper.find('.rail-ping').exists()).toBe(true)
    expect(wrapper.get('[data-running-badge]').text()).toBe('Running')
    expect(wrapper.text()).toContain('working')

    await wrapper.setProps({
      state: sessionState(
        {
          flow_id: 'flow',
          name: 'demo',
          branch: 'main',
          step: 2,
          cells: [{ ...cell, run_id: null }],
          sweeps: [],
        },
        [transaction(2)],
      ),
    })
    expect(wrapper.find('.rail-ping').exists()).toBe(false)
    expect(wrapper.text()).toContain('working')
  })

  it('surfaces journaled cache hits and failures on both cards and rail stops', async () => {
    const cacheCell: LiveCellRecord = {
      uid: 'cell-cache',
      slug: 'features',
      version_id: 'version-cache',
      definition_hash: 'definition-cache',
      source: 'class Features:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const failedCell: LiveCellRecord = {
      ...cacheCell,
      uid: 'cell-failed',
      slug: 'train',
      version_id: 'version-failed',
      definition_hash: 'definition-failed',
      verdict: {
        direct: { state: 'failed', causes: ['materialization-failed'] },
        transitive: { state: 'failed', causes: ['materialization-failed'] },
      },
      logs: [
        {
          run_id: 'run-failed',
          stream: 'stderr',
          seq: 0,
          bytes: 'Traceback: training exploded\n',
        },
      ],
    }
    const cacheHit: JournalTransaction = {
      ...transaction(3),
      intent: 'run features',
      ops: [
        {
          op: 'memo_hit',
          uid: 'cell-cache',
          version_id: 'version-cache',
          memo_key: 'memo-cache',
          mat_id: 'mat-cache',
        },
      ],
    }
    const failure: JournalTransaction = {
      ...transaction(4),
      intent: 'run train',
      ops: [
        {
          op: 'run_recorded',
          mat_id: 'mat-failed',
          version_id: 'version-failed',
          memo_key: 'memo-failed',
          state: 'failed',
          inputs: {},
          outputs: {},
          identity_dependent: false,
          env_lock_hash: null,
          cost_seconds: null,
          log_ref: 'log-failed',
          started_step: 4,
          finished_step: 4,
        },
      ],
    }
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: {} as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 4,
            cells: [cacheCell, failedCell],
            sweeps: [],
          },
          [cacheHit, failure],
        ),
      },
    })

    expect(wrapper.get('[data-cell-slug="features"] [data-cache-skip]').text()).toContain(
      'no kernel execution',
    )
    const failedCard = wrapper.get('[data-cell-slug="train"]')
    expect(failedCard.get('[data-run-failure]').text()).toContain('latest materialization failed')
    expect(failedCard.text()).toContain('Traceback: training exploded')
    expect(wrapper.get('[data-stop-status="cache-hit"]').text()).toContain('cache hit')
    expect(wrapper.get('[data-stop-status="failed"]').text()).toContain('failed')
  })

  it('does not surface run outcomes from another branch on active-branch cards', () => {
    const cell: LiveCellRecord = {
      uid: 'cell-1',
      slug: 'train',
      version_id: 'version-1',
      definition_hash: 'definition-1',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }
    const fork: LiveBranch = {
      branch_id: 'branch-fork',
      name: 'fork',
      parent_branch_id: 'branch-main',
      fork_step: 2,
      archived: false,
      sweep_group: null,
    }
    const forkCacheHit: JournalTransaction = {
      ...transaction(3),
      branch: 'branch-fork',
      ops: [
        {
          op: 'memo_hit',
          uid: cell.uid,
          version_id: cell.version_id,
          memo_key: 'memo-fork',
          mat_id: 'mat-fork',
        },
      ],
    }
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: {} as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 3,
            cells: [cell],
            sweeps: [],
          },
          [forkCacheHit],
          [mainLane, fork],
        ),
      },
    })

    expect(wrapper.find('[data-cache-skip]').exists()).toBe(false)
  })

  it('shows a freshly initialized demo as unmaterialized cards on one trunk lane', () => {
    const slugs = ['data', 'features', 'train', 'evaluate', 'plot', 'note']
    const cells: LiveCellRecord[] = slugs.map((slug, index) => ({
      uid: `cell-${index}`,
      slug,
      version_id: `version-${index}`,
      definition_hash: `definition-${index}`,
      source: `class ${slug}:\n    pass\n`,
      manifest: {},
      verdict: {
        direct: { state: 'unmaterialized', causes: ['never-run'] },
        transitive: { state: 'unmaterialized', causes: ['never-run'] },
      },
      outputs: [],
      logs: [],
      run_id: null,
    }))
    const initialize: JournalTransaction = {
      ...transaction(1),
      actor: 'system:init',
      intent: 'initialize flow',
      ops: [
        {
          op: 'flow_init',
          flow_id: 'flow',
          name: 'demo',
          language: 'python',
          branch_id: 'branch-main',
          branch_name: 'main',
        },
      ],
    }
    const scaffold: JournalTransaction = {
      ...transaction(2),
      actor: 'system:init',
      intent: 'scaffold demo flow',
      settled: false,
      ops: cells.map((cell) => ({
        op: 'cell_accepted' as const,
        uid: cell.uid,
        version_id: cell.version_id,
        slug: cell.slug,
        source_hash: `source-${cell.uid}`,
        bound_hash: `bound-${cell.uid}`,
        definition_hash: cell.definition_hash,
        manifest: {},
        flags: [],
        parent_version: null,
        author: 'system:init',
        copied_from: null,
      })),
    }
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: {} as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 2,
            cells,
            sweeps: [],
          },
          [initialize, scaffold],
        ),
      },
    })

    expect(wrapper.findAll('[data-rail-lane]')).toHaveLength(1)
    expect(wrapper.findAll('[data-rail-stop]')).toHaveLength(2)
    expect(wrapper.text()).toContain('initialize flow')
    expect(wrapper.text()).toContain('scaffold demo flow')
    const cards = wrapper.findAll('[data-live-canvas-card]')
    expect(cards).toHaveLength(6)
    expect(cards.map((card) => card.get('h3').text())).toEqual(slugs)
    expect(cards.every((card) => card.text().includes('unmaterialized'))).toBe(true)
  })

  it('renders agent transactions in catch-up grouped by actor and intent', () => {
    const catchUpTransactions = [
      { ...transaction(5), intent: 'build agent cell' },
      { ...transaction(6), intent: 'build agent cell' },
    ]
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: {} as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 6,
            cells: [],
            sweeps: [],
          },
          catchUpTransactions,
        ),
      },
    })

    const groups = wrapper.findAll('[data-catchup-group]')
    expect(groups).toHaveLength(1)
    expect(groups[0].text()).toContain('build agent cell')
    expect(groups[0].text()).toContain('agent:test')
    expect(groups[0].text()).toContain('2 transactions')
  })

  it('compares sweep variants by parameters and per-output content hashes', () => {
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: {} as FlowSessionClient,
        state: sessionState({
          flow_id: 'flow',
          name: 'demo',
          branch: 'main',
          step: 8,
          cells: [],
          sweeps: [
            {
              group: 'learning-rate',
              parent: 'main',
              fork_step: 2,
              variants: [
                {
                  branch: 'sweep/lr/1',
                  branch_id: 'branch-1',
                  params: { train: { lr: 0.2 } },
                  output_hashes: { 'train.score': 'abcdef0123456789' },
                },
              ],
            },
          ],
        }),
      },
    })

    const comparison = wrapper.find('[data-sweep-comparison]')
    expect(comparison.text()).toContain('learning-rate')
    expect(comparison.text()).toContain('sweep/lr/1')
    expect(comparison.text()).toContain('train.score: abcdef01')
  })

  it('fills sweep comparison rows incrementally as journal-refreshed snapshots arrive', async () => {
    const initialSnapshot: LiveSessionSnapshot = {
      flow_id: 'flow',
      name: 'demo',
      branch: 'main',
      step: 8,
      cells: [],
      sweeps: [
        {
          group: 'learning-rate',
          parent: 'main',
          fork_step: 2,
          variants: [
            {
              branch: 'sweep/lr/1',
              branch_id: 'branch-1',
              params: { train: { lr: 0.2 } },
              output_hashes: {},
            },
            {
              branch: 'sweep/lr/2',
              branch_id: 'branch-2',
              params: { train: { lr: 0.3 } },
              output_hashes: {},
            },
          ],
        },
      ],
    }
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc: vi.fn() } as unknown as FlowSessionClient,
        state: sessionState(initialSnapshot),
      },
    })

    expect(wrapper.findAll('[data-sweep-state="waiting"]')).toHaveLength(2)

    await wrapper.setProps({
      state: sessionState({
        ...initialSnapshot,
        step: 9,
        sweeps: [
          {
            ...initialSnapshot.sweeps[0],
            variants: [
              {
                ...initialSnapshot.sweeps[0].variants[0],
                output_hashes: { 'train.score': 'abcdef0123456789' },
              },
              initialSnapshot.sweeps[0].variants[1],
            ],
          },
        ],
      }),
    })

    expect(wrapper.findAll('[data-sweep-state="complete"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-sweep-state="waiting"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('train.score: abcdef01')
  })

  it('hands a sweep winner to the adopt flow and surfaces conflicts', async () => {
    const rpc = vi
      .fn()
      .mockResolvedValueOnce({ adopted: true })
      .mockRejectedValueOnce(
        new FlowRpcError(-32009, 'adopt conflict for train: parent changed', null, 409),
      )
    const snapshot: LiveSessionSnapshot = {
      flow_id: 'flow',
      name: 'demo',
      branch: 'main',
      step: 8,
      cells: [],
      sweeps: [
        {
          group: 'learning-rate',
          parent: 'main',
          fork_step: 2,
          variants: [
            {
              branch: 'sweep/lr/1',
              branch_id: 'branch-1',
              params: { train: { lr: 0.2 } },
              output_hashes: { 'train.score': 'abcdef0123456789' },
            },
          ],
        },
      ],
    }
    const wrapper = mount(LiveFlowSession, {
      props: { client: { rpc } as unknown as FlowSessionClient, state: sessionState(snapshot) },
    })

    await wrapper.get('[data-adopt-sweep-winner]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenLastCalledWith('adopt', {
      slug: 'train',
      from_branch: 'branch-1',
      branch: 'main',
      actor: 'user:ui',
      intent: 'adopt train from sweep/lr/1 into main',
    })
    expect(wrapper.get('[data-sweep-adopt-success]').text()).toContain('Adopted train')

    await wrapper.get('[data-adopt-sweep-winner]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-sweep-adopt-error]').text()).toContain('adopt conflict for train')
  })

  it('renders live lanes and output-first cards, then shows stop metadata without changing the canvas', async () => {
    const initialize: JournalTransaction = {
      ...transaction(1),
      intent: 'initialize data cell',
      ops: [
        {
          op: 'cell_accepted',
          uid: 'cell-data',
          version_id: 'version-data',
          slug: 'data',
          source_hash: 'source-data',
          bound_hash: 'bound-data',
          definition_hash: 'definition-data',
          manifest: {},
          flags: [],
          parent_version: null,
          author: 'agent:test',
          copied_from: null,
        },
      ],
    }
    const candidate: JournalTransaction = {
      ...transaction(2),
      branch: 'branch-candidate',
      actor: 'user:ui',
      intent: 'tune candidate',
    }
    const lanes: LiveBranch[] = [
      mainLane,
      {
        branch_id: 'branch-candidate',
        name: 'candidate',
        parent_branch_id: 'branch-main',
        fork_step: 1,
        archived: false,
        sweep_group: null,
      },
    ]
    const cell: LiveCellRecord = {
      uid: 'cell-data',
      slug: 'data',
      version_id: 'version-data',
      definition_hash: 'definition-data',
      source: 'class Data:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'unmaterialized', causes: ['never-run'] },
        transitive: { state: 'unmaterialized', causes: ['never-run'] },
      },
      outputs: [{ name: 'frame', kind: 'frame', content_hash: null, preview: null }],
      logs: [],
      run_id: null,
    }
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: {} as FlowSessionClient,
        state: sessionState(
          {
            flow_id: 'flow',
            name: 'demo',
            branch: 'main',
            step: 3,
            cells: [cell],
            sweeps: [],
          },
          [initialize, candidate],
          lanes,
        ),
      },
    })

    expect(wrapper.findAll('[data-rail-lane]')).toHaveLength(2)
    expect(
      wrapper.findAll('[data-rail-lane]').map((lane) => lane.attributes('data-branch-id')),
    ).toEqual(['branch-main', 'branch-candidate'])
    expect(wrapper.findAll('[data-rail-stop]')).toHaveLength(2)
    expect(wrapper.findAll('[data-live-canvas-card]')).toHaveLength(1)
    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).toEqual([
      'frame',
      'code',
      'logs',
    ])
    expect(wrapper.get('[data-live-canvas]').text()).toContain('unmaterialized')

    await wrapper.findAll('[data-rail-stop]')[0].trigger('click')

    const detail = wrapper.get('[data-transaction-detail]')
    expect(detail.text()).toContain('initialize data cell')
    expect(detail.text()).toContain('agent:test')
    expect(detail.text()).toContain('Affected cells: data')
    expect(detail.text()).toContain('cell accepted')
    expect(wrapper.findAll('[data-live-canvas-card]')).toHaveLength(1)
    expect(wrapper.get('[data-live-canvas]').text()).toContain('data')
  })

  it('manages environment packages and clears the restart banner after a kernel restart', async () => {
    let restartRequired = false
    const packages: Record<string, string> = { cloudpickle: '3.1.1' }
    const rpc = vi.fn(async (method: string, params?: Record<string, unknown>) => {
      if (method === 'env_add') {
        packages.lightgbm = '4.6.0'
        restartRequired = true
        return { restart_required: true, restart_packages: ['lightgbm'] }
      }
      if (method === 'env_remove') {
        delete packages[String(params?.package)]
        return { restart_required: restartRequired }
      }
      if (method === 'kernel_restart') {
        restartRequired = false
        return { restarted: true, handshake: {} }
      }
      if (method === 'env_status') {
        return {
          lock_hash: 'lock-new',
          live_lock_hash: 'lock-new',
          branch_lock_mismatch: false,
          background_deferred: false,
          restart_required: restartRequired,
          restart_packages: restartRequired ? ['lightgbm'] : [],
          packages: { ...packages },
        }
      }
      throw new Error(`unexpected RPC: ${method}`)
    })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: sessionState({
          flow_id: 'flow',
          name: 'demo',
          branch: 'main',
          step: 1,
          cells: [],
          sweeps: [],
        }),
      },
    })

    await wrapper.get('[data-open-env]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-env-package]').text()).toContain('cloudpickle')

    await wrapper.get('[name="env-package"]').setValue('lightgbm')
    await wrapper.get('[data-env-add-form]').trigger('submit')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('env_add', {
      package: 'lightgbm',
      actor: 'user:ui',
      intent: 'add environment package lightgbm',
    })
    expect(wrapper.get('[data-env-restart-banner]').text()).toContain(
      'Restart kernel to apply environment changes',
    )
    expect(wrapper.findAll('[data-env-package]').map((entry) => entry.text())).toEqual([
      'cloudpickle3.1.1Remove',
      'lightgbm4.6.0Remove',
    ])

    await wrapper.get('[aria-label="Remove lightgbm"]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenCalledWith('env_remove', {
      package: 'lightgbm',
      actor: 'user:ui',
      intent: 'remove environment package lightgbm',
    })
    expect(wrapper.text()).not.toContain('lightgbm4.6.0')

    await wrapper.get('[data-restart-kernel]').trigger('click')
    await flushPromises()
    expect(rpc).toHaveBeenCalledWith('kernel_restart', {
      actor: 'user:ui',
      intent: 'restart kernel',
    })
    expect(wrapper.find('[data-env-restart-banner]').exists()).toBe(false)
  })

  it('promotes a materialized output and renders journaled upload queue transitions', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-train',
      slug: 'train',
      version_id: 'version-train',
      definition_hash: 'definition-train',
      source: 'class Train:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [{ name: 'score', kind: 'metric', content_hash: 'score-hash', preview: null }],
      logs: [],
      run_id: null,
      computed_under_older_env: true,
    }
    const materialized: JournalTransaction = {
      ...transaction(2),
      intent: 'run train',
      ops: [
        {
          op: 'run_recorded',
          mat_id: 'mat-train',
          version_id: cell.version_id,
          memo_key: 'memo-train',
          state: 'succeeded',
          inputs: {},
          outputs: {},
          identity_dependent: false,
          env_lock_hash: 'lock-old',
          cost_seconds: 0.1,
          log_ref: null,
          started_step: 2,
          finished_step: 2,
        },
      ],
    }
    const uploadTransaction = (
      step: number,
      state: 'queued' | 'uploading' | 'done' | 'failed',
      error: string | null = null,
    ): JournalTransaction => ({
      ...transaction(step),
      actor: 'system:uploads',
      intent: `upload ${state}`,
      ops: [
        {
          op: 'upload_state',
          mat_id: 'mat-train',
          output: 'score',
          state,
          attempts: state === 'queued' ? 0 : 1,
          error,
        },
      ],
    })
    const rpc = vi.fn(async () => ({ cell: 'train', output: 'score', state: 'queued' }))
    const snapshot: LiveSessionSnapshot = {
      flow_id: 'flow',
      name: 'demo',
      branch: 'main',
      step: 2,
      cells: [cell],
      sweeps: [],
    }
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: sessionState(snapshot, [materialized]),
      },
    })

    expect(wrapper.get('[data-older-env-badge]').text()).toContain('older environment')
    await wrapper.get('[data-promote-output]').trigger('click')
    await flushPromises()

    expect(rpc).toHaveBeenCalledWith('promote', {
      slug: 'train',
      output: 'score',
      branch: 'main',
      actor: 'user:ui',
      intent: 'promote train.score',
    })
    expect(wrapper.get('[data-promote-awaiting]').text()).toContain('journal acceptance')

    for (const [index, state] of (['queued', 'uploading', 'done'] as const).entries()) {
      const updates = [materialized, uploadTransaction(index + 3, state)]
      await wrapper.setProps({
        state: sessionState({ ...snapshot, step: index + 3 }, updates),
      })
      expect(wrapper.get('[data-upload-state]').attributes('data-state')).toBe(state)
      expect(wrapper.get('[data-upload-state]').text()).toContain(`Publication ${state}`)
    }

    await wrapper.setProps({
      state: sessionState({ ...snapshot, step: 6 }, [
        materialized,
        uploadTransaction(6, 'failed', 'tracker unavailable'),
      ]),
    })
    expect(wrapper.get('[data-upload-state]').attributes('data-state')).toBe('failed')
    expect(wrapper.get('[data-upload-error]').text()).toBe('tracker unavailable')
    expect(wrapper.get('[data-promote-output]').text()).toBe('Retry publication')
  })

  it('surfaces environment and promotion request failures in place', async () => {
    const cell: LiveCellRecord = {
      uid: 'cell-note',
      slug: 'note',
      version_id: 'version-note',
      definition_hash: 'definition-note',
      source: 'class Note:\n    pass\n',
      manifest: {},
      verdict: {
        direct: { state: 'synced', causes: [] },
        transitive: { state: 'synced', causes: [] },
      },
      outputs: [{ name: 'text', kind: 'note', content_hash: 'text-hash', preview: null }],
      logs: [],
      run_id: null,
    }
    const rpc = vi.fn(async (method: string) => {
      if (method === 'env_status') {
        return {
          lock_hash: null,
          live_lock_hash: null,
          branch_lock_mismatch: false,
          background_deferred: false,
          restart_required: false,
          restart_packages: [],
          packages: {},
        }
      }
      if (method === 'env_add') throw new Error('package resolution failed')
      if (method === 'promote') throw new Error('materialized output is unavailable')
      throw new Error(`unexpected RPC: ${method}`)
    })
    const wrapper = mount(LiveFlowSession, {
      props: {
        client: { rpc } as unknown as FlowSessionClient,
        state: sessionState({
          flow_id: 'flow',
          name: 'demo',
          branch: 'main',
          step: 1,
          cells: [cell],
          sweeps: [],
        }),
      },
    })

    await wrapper.get('[data-open-env]').trigger('click')
    await flushPromises()
    await wrapper.get('[name="env-package"]').setValue('broken')
    await wrapper.get('[data-env-add-form]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[data-env-error]').text()).toBe('package resolution failed')

    await wrapper.get('[data-promote-output]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-promote-error]').text()).toBe('materialized output is unavailable')
  })
})
