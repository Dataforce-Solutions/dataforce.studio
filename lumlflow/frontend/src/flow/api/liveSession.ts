import type { FlowSessionClient, JournalHandlers, StreamSubscription } from './client'
import { groupTransactionsByIntent, type CatchUpGroup } from './catchup'
import type {
  FlowOp,
  JournalMessage,
  JournalTransaction,
  KernelMessage,
  LiveBranch,
  LiveSessionSnapshot,
  LiveTreeSnapshot,
} from './types'

export interface LiveJournalStop {
  key: string
  branch: string
  step: number
  kind: 'checkpoint' | 'run'
  label: string
  detail: string
  txCount: number
  failed: boolean
  cached: boolean
  laneHead: boolean
  affectedCells: string[]
  transactions: JournalTransaction[]
}

export interface LiveSessionState {
  snapshot: LiveSessionSnapshot
  lanes: LiveBranch[]
  transactions: JournalTransaction[]
  stops: LiveJournalStop[]
  catchUpGroups: CatchUpGroup[]
  cursor: number
}

export interface LiveSessionModelHandlers {
  change?(state: LiveSessionState): void
  kernel?(message: KernelMessage): void
  error?(error: Error): void
}

interface StepGroup {
  step: number
  transactions: JournalTransaction[]
}

const hasFailure = (transactions: JournalTransaction[]): boolean =>
  transactions.some((transaction) =>
    transaction.ops.some((op) => op.op === 'run_recorded' && op.state === 'failed'),
  )

const hasMemoHit = (transactions: JournalTransaction[]): boolean =>
  transactions.some((transaction) => transaction.ops.some((op) => op.op === 'memo_hit'))

const isLandmark = (transactions: JournalTransaction[]): boolean =>
  transactions.some(
    (transaction) =>
      transaction.settled ||
      transaction.ops.some(
        (op) => op.op === 'branch_created' || op.op === 'branch_renamed' || op.op === 'renamed',
      ),
  )

const groupedByBranchAndStep = (transactions: JournalTransaction[]): Map<string, StepGroup[]> => {
  const groups = new Map<string, StepGroup[]>()
  for (const transaction of transactions) {
    const branchGroups = groups.get(transaction.branch) ?? []
    const last = branchGroups.at(-1)
    if (last?.step === transaction.step) last.transactions.push(transaction)
    else branchGroups.push({ step: transaction.step, transactions: [transaction] })
    groups.set(transaction.branch, branchGroups)
  }
  return groups
}

const cellNameIndexes = (
  transactions: JournalTransaction[],
): { byUid: Map<string, string>; byVersion: Map<string, string> } => {
  const byUid = new Map<string, string>()
  const byVersion = new Map<string, string>()
  for (const transaction of transactions) {
    for (const operation of transaction.ops) {
      if (operation.op === 'cell_accepted') {
        byUid.set(operation.uid, operation.slug)
        byVersion.set(operation.version_id, operation.slug)
      } else if (operation.op === 'renamed') {
        byUid.set(operation.uid, operation.new_slug)
      }
    }
  }
  return { byUid, byVersion }
}

const affectedCellNames = (
  transactions: JournalTransaction[],
  byUid: Map<string, string>,
  byVersion: Map<string, string>,
): string[] => {
  const names = new Set<string>()
  for (const transaction of transactions) {
    for (const operation of transaction.ops) {
      if (operation.op === 'cell_accepted') names.add(operation.slug)
      else if (operation.op === 'renamed') names.add(operation.new_slug)
      else if (operation.op === 'run_recorded') {
        const name = byVersion.get(operation.version_id)
        if (name) names.add(name)
      } else if ('uid' in operation && operation.uid !== null) {
        const name = byUid.get(operation.uid)
        if (name) names.add(name)
      }
    }
  }
  return [...names]
}

export const foldJournalStops = (
  transactions: JournalTransaction[],
  branches: LiveBranch[] = [],
): LiveJournalStop[] => {
  const stops: LiveJournalStop[] = []
  const visibleBranches = branches.filter(({ archived }) => !archived)
  const visibleBranchIds = new Set(visibleBranches.map(({ branch_id }) => branch_id))
  const visibleTransactions = branches.length
    ? transactions.filter(({ branch }) => visibleBranchIds.has(branch))
    : transactions
  const { byUid, byVersion } = cellNameIndexes(transactions)
  for (const [branch, groups] of groupedByBranchAndStep(visibleTransactions)) {
    let routine: StepGroup[] = []
    const addStop = (
      stopGroups: StepGroup[],
      kind: LiveJournalStop['kind'],
      laneHead: boolean,
    ): void => {
      const stopTransactions = stopGroups.flatMap((group) => group.transactions)
      if (!stopTransactions.length) return
      const actors = [...new Set(stopTransactions.map(({ actor }) => actor))]
      const affectedCells = affectedCellNames(stopTransactions, byUid, byVersion)
      const lastGroup = stopGroups.at(-1)
      if (!lastGroup) return
      const failed = hasFailure(stopTransactions)
      const cached = hasMemoHit(stopTransactions)
      const baseLabel =
        stopTransactions.length === 1
          ? stopTransactions[0].intent
          : `${stopTransactions.length} edits · ${actors.join(', ')}`
      stops.push({
        key: `${branch}@${stopGroups[0].step}-${lastGroup.step}`,
        branch,
        step: lastGroup.step,
        kind,
        label: failed ? `${baseLabel} · failed` : cached ? `${baseLabel} · cache hit` : baseLabel,
        detail: [actors.join(', '), affectedCells.slice(0, 3).join(', ')]
          .filter(Boolean)
          .join(' · '),
        txCount: stopTransactions.length,
        failed,
        cached,
        laneHead,
        affectedCells,
        transactions: stopTransactions,
      })
    }

    groups.forEach((group, index) => {
      const last = index === groups.length - 1
      if (isLandmark(group.transactions) || last) {
        addStop(routine, 'run', false)
        routine = []
        addStop([group], 'checkpoint', last)
      } else {
        routine.push(group)
      }
    })
  }

  const branchesWithStops = new Set(stops.map(({ branch }) => branch))
  const branchNames = new Map(visibleBranches.map(({ branch_id, name }) => [branch_id, name]))
  for (const branch of visibleBranches) {
    if (branchesWithStops.has(branch.branch_id) || branch.parent_branch_id === null) continue
    stops.push({
      key: `${branch.branch_id}@${branch.fork_step}-${branch.fork_step}`,
      branch: branch.branch_id,
      step: branch.fork_step,
      kind: 'checkpoint',
      label: branch.name,
      detail: `forked from ${branchNames.get(branch.parent_branch_id) ?? '?'}`,
      txCount: 0,
      failed: false,
      cached: false,
      laneHead: true,
      affectedCells: [],
      transactions: [],
    })
  }
  return stops.sort(
    (left, right) => left.step - right.step || left.branch.localeCompare(right.branch),
  )
}

const updateBranches = (branches: LiveBranch[], operations: FlowOp[]): LiveBranch[] => {
  const next = branches.map((branch) => ({ ...branch }))
  for (const operation of operations) {
    if (operation.op === 'branch_created') {
      const existing = next.find(({ branch_id }) => branch_id === operation.branch_id)
      if (existing) continue
      next.push({
        branch_id: operation.branch_id,
        name: operation.name,
        parent_branch_id: operation.parent,
        fork_step: operation.fork_step,
        archived: false,
        sweep_group: operation.sweep_group,
      })
    } else if (operation.op === 'branch_archived') {
      const archived = next.find(({ branch_id }) => branch_id === operation.branch_id)
      if (archived) archived.archived = true
    } else if (operation.op === 'branch_renamed') {
      const renamed = next.find(({ branch_id }) => branch_id === operation.branch_id)
      if (renamed) renamed.name = operation.new_name
    }
  }
  return next
}

export class LiveSessionModel {
  private subscription: StreamSubscription | null = null
  private closed = false
  private refreshing = false
  private refreshPending = false
  private readonly streamedRunIds = new Map<string, string>()
  private readonly streamObservedSlugs = new Set<string>()
  private currentState: LiveSessionState

  private constructor(
    private readonly client: FlowSessionClient,
    snapshot: LiveSessionSnapshot,
    tree: LiveTreeSnapshot,
    private readonly handlers: LiveSessionModelHandlers,
  ) {
    this.currentState = {
      snapshot,
      lanes: tree.branches,
      transactions: [],
      stops: [],
      catchUpGroups: [],
      cursor: 0,
    }
  }

  static async connect(
    client: FlowSessionClient,
    handlers: LiveSessionModelHandlers = {},
  ): Promise<LiveSessionModel> {
    const snapshot = await client.snapshot()
    const tree = (await client.rpc('tree', {
      branch: snapshot.branch,
    })) as unknown as LiveTreeSnapshot
    const model = new LiveSessionModel(client, snapshot, tree, handlers)
    model.subscription = client.connect(model.journalHandlers(), 0)
    return model
  }

  get state(): LiveSessionState {
    return this.currentState
  }

  close(): void {
    this.closed = true
    this.subscription?.close()
    this.subscription = null
  }

  private journalHandlers(): JournalHandlers {
    return {
      transaction: (message) => this.receiveTransaction(message),
      kernel: (message) => this.receiveKernel(message),
      error: (error) => this.handlers.error?.(error),
    }
  }

  private receiveKernel(message: KernelMessage): void {
    const slug = typeof message.payload.slug === 'string' ? message.payload.slug : null
    if (slug && message.run_id && message.event === 'started') {
      this.streamObservedSlugs.add(slug)
      this.streamedRunIds.set(slug, message.run_id)
    } else if (message.event === 'materialized' || message.event === 'failed') {
      const finishedSlug =
        slug ?? [...this.streamedRunIds].find(([, runId]) => runId === message.run_id)?.[0] ?? null
      if (finishedSlug) {
        this.streamObservedSlugs.add(finishedSlug)
        this.streamedRunIds.delete(finishedSlug)
      }
    }
    this.currentState = {
      ...this.currentState,
      snapshot: this.withStreamedRuns(this.currentState.snapshot),
    }
    this.handlers.kernel?.(message)
    this.handlers.change?.(this.currentState)
    void this.refreshSnapshot()
  }

  private withStreamedRuns(snapshot: LiveSessionSnapshot): LiveSessionSnapshot {
    if (!this.streamObservedSlugs.size) return snapshot
    return {
      ...snapshot,
      cells: snapshot.cells.map((cell) =>
        this.streamObservedSlugs.has(cell.slug)
          ? { ...cell, run_id: this.streamedRunIds.get(cell.slug) ?? null }
          : cell,
      ),
    }
  }

  private receiveTransaction(message: JournalMessage): void {
    if (message.cursor <= this.currentState.cursor) return
    const transactions = [...this.currentState.transactions, message.transaction]
    const lanes = updateBranches(this.currentState.lanes, message.transaction.ops)
    const activeBranch = this.currentState.lanes.find(
      ({ name }) => name === this.currentState.snapshot.branch,
    )
    const activeRename = message.transaction.ops.find(
      (operation): operation is Extract<FlowOp, { op: 'branch_renamed' }> =>
        operation.op === 'branch_renamed' && operation.branch_id === activeBranch?.branch_id,
    )
    this.currentState = {
      ...this.currentState,
      snapshot: activeRename
        ? { ...this.currentState.snapshot, branch: activeRename.new_name }
        : this.currentState.snapshot,
      lanes,
      transactions,
      stops: foldJournalStops(transactions, lanes),
      catchUpGroups: groupTransactionsByIntent(transactions),
      cursor: message.cursor,
    }
    this.handlers.change?.(this.currentState)
    if (message.cursor > this.currentState.snapshot.step) void this.refreshSnapshot()
  }

  private async refreshSnapshot(): Promise<void> {
    if (this.closed) return
    if (this.refreshing) {
      this.refreshPending = true
      return
    }
    this.refreshing = true
    try {
      const snapshot = await this.client.snapshot()
      if (this.closed || snapshot.step < this.currentState.snapshot.step) return
      this.currentState = { ...this.currentState, snapshot: this.withStreamedRuns(snapshot) }
      this.handlers.change?.(this.currentState)
    } catch (error) {
      this.handlers.error?.(error instanceof Error ? error : new Error(String(error)))
    } finally {
      this.refreshing = false
      if (this.refreshPending) {
        this.refreshPending = false
        void this.refreshSnapshot()
      }
    }
  }
}
