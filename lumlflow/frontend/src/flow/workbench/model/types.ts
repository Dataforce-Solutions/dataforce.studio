/**
 * View model for the flow workbench design system.
 *
 * These are the shapes the daemon will eventually serve (ui-draft.md §10: no
 * derived truth in the frontend — staleness verdicts, preflight costs, and
 * divergence kinds arrive computed). Fixtures therefore author these shapes
 * directly; there is deliberately no derivation engine here.
 *
 * Vocabulary rules that are part of the contract, not taste:
 * - Cells are addressed by slug and branches by name. No positional numbers,
 *   and internal ids (uid, content hash, memo key) never appear in any
 *   user-facing string.
 * - `unmaterialized` is its own status, never a flavor of stale: the asset has
 *   no baseline anywhere, and claiming a change against a missing baseline is
 *   a claim the runtime refuses to make.
 * - Staleness causes are rendered in words ("parent `features` rematerialized"),
 *   never as bare enum values.
 */

export type Slug = string
export type BranchName = string

/** The four-word authoring vocabulary: what leaves the flow vs. stays inline. */
export type DeclaredType = 'model' | 'dataset' | 'experiment' | 'asset'

/**
 * Inferred kind of a materialized value — drives the renderer registry.
 * The registry is open at runtime; `unknown` is the documented fallback,
 * rendered as a key-value grid, never an error.
 */
export type AssetKind =
  | 'frame'
  | 'plot'
  | 'metric'
  | 'note'
  | 'eval'
  | 'model'
  | 'dataset'
  | 'experiment'
  | 'checkpoint'
  | 'image'
  | 'text'
  | 'html'
  | 'unknown'

export type CellStatus = 'materialized' | 'running' | 'stale' | 'unmaterialized' | 'failed'

export type StaleKind =
  | 'definition-changed'
  | 'deps-rewired'
  | 'parent-rematerialized'
  | 'lib-changed'

export interface StaleInfo {
  kind: StaleKind
  /** Human words shown on the chip, e.g. 'parent `features` rematerialized'. */
  cause: string
  /** Stale only under the transitive view — subdued tint, hidden by default. */
  transitive?: boolean
}

export interface ActorRef {
  kind: 'agent' | 'user'
  label: string
}

export interface ProvenanceInfo {
  createdBy: ActorRef
  lastEditedBy: ActorRef
  /** Intent string of the transaction that authored the current version. */
  intent: string
  step: number
  /** Mixed-editing window: render the flag, never a confident wrong name. */
  attributionUncertain?: boolean
}

export interface TimingInfo {
  costSeconds: number
  /** Memo hit — a hit is not a 0-second run, and saying so keeps the cache legible. */
  cached?: boolean
  /** Recorded lock hash differs from the live env. */
  olderEnv?: boolean
  finishedAgo?: string
}

/** Accepted-but-flagged version (broken declaration, unknown reference). */
export interface CellFlagInfo {
  message: string
  didYouMean?: string
}

export interface CellErrorInfo {
  author: 'agent' | 'user'
  summary: string
  traceback: string
  /** Folded history entry: a later version by the same author repaired it. */
  repairedAttempts?: number
}

export type ParamValue = string | number | boolean | null | ParamValue[]

// ---------------------------------------------------------------------------
// Preview payloads — the kernel-free tier every renderer draws from
// ---------------------------------------------------------------------------

export interface FramePreview {
  type: 'frame'
  columns: string[]
  dtypes: string[]
  rows: (string | number | null)[][]
  totalRows: number
}

export interface PlotPreview {
  type: 'plot'
  title: string
  kind: 'line' | 'scatter' | 'bar' | 'hist'
  series: { label: string; points: [number, number][]; color?: string }[]
  xLabel: string
  yLabel: string
}

export interface MetricPreview {
  type: 'metric'
  name: string
  value: number
  higherIsBetter: boolean
  /** Change against the previous materialization on this branch, if any. */
  delta?: number
}

export interface NotePreview {
  type: 'note'
  markdown: string
}

export interface ModelPreview {
  type: 'model'
  flavor: string
  sizeBytes: number
  headlineMetric?: { name: string; value: number; higherIsBetter: boolean }
  config: Record<string, ParamValue>
  /** Slug of the cell output holding the full experiment, when one exists. */
  experimentRef?: string
}

export interface ExperimentPreview {
  type: 'experiment'
  runName: string
  mainMetric: { name: string; value: number; higherIsBetter: boolean }
  config: Record<string, ParamValue>
  curves: { name: string; points: [number, number][] }[]
  /** Present once the daemon uploaded it — links out to the tracker. */
  trackerRef?: string
}

export interface EvalPreview {
  type: 'eval'
  datasetRef: string
  sampleCount: number
  scores: Record<string, number>
}

export interface DatasetPreview {
  type: 'dataset'
  schema: { name: string; dtype: string }[]
  head: (string | number | null)[][]
  totalRows: number
  sizeBytes: number
}

export interface FilePreview {
  type: 'file'
  fileName: string
  sizeBytes: number
  contentType: string
}

export interface TextPreview {
  type: 'text'
  text: string
}

/** Fallback for open-registry kinds the frontend has no renderer for. */
export interface KvPreview {
  type: 'kv'
  entries: Record<string, string | number | boolean>
  /** Set when the preview schema version is newer than this frontend. */
  newerFormatNote?: string
}

export type PreviewValue =
  | FramePreview
  | PlotPreview
  | MetricPreview
  | NotePreview
  | ModelPreview
  | ExperimentPreview
  | EvalPreview
  | DatasetPreview
  | FilePreview
  | TextPreview
  | KvPreview

// ---------------------------------------------------------------------------
// Cells
// ---------------------------------------------------------------------------

export interface CellOutput {
  name: string
  declared: DeclaredType
  kind: AssetKind
  preview: PreviewValue
  /** Value was never persisted → download becomes materialize-and-download. */
  neverPersisted?: boolean
}

export interface FlowCell {
  slug: Slug
  /** First line of the class docstring. */
  doc: string
  /** Reference strings exactly as authored: 'features.train_split'. */
  consumes: string[]
  params: Record<string, ParamValue>
  source: string
  outputs: CellOutput[]
  /** Defaults to the ranking in registry.ts when absent. */
  primaryOutput?: string
  status: CellStatus
  stale?: StaleInfo
  provenance: ProvenanceInfo
  timing?: TimingInfo
  /** Persistent logs of the current materialization. */
  logs?: string
  /** Live console lines while running. */
  console?: string[]
  error?: CellErrorInfo
  flag?: CellFlagInfo
  /** Edit landed on a moved head → overwrite / fork-my-edit menu. */
  conflict?: boolean
  /** Saved to the store, projection to files deferred by the worktree lock. */
  pendingProjection?: boolean
  /** volatility: external — grouped under "inputs" in the left panel. */
  externalInput?: boolean
  /** Per-asset eager toggle (reactivity setting). */
  eager?: boolean
  /** Note cells render prose and skip the op row's run controls. */
  isNote?: boolean
}

// ---------------------------------------------------------------------------
// Branches and the journal
// ---------------------------------------------------------------------------

export interface BranchInfo {
  name: BranchName
  parent: BranchName | null
  forkedAtStep: number | null
  headStep: number
  lastIntent: string
  /** Fully materialized and consistent — a quality badge, never a gate. */
  settled: boolean
  /** Agent currently registered on this branch. */
  agent?: ActorRef
  archived?: boolean
  sweepGroup?: string
  headlineMetric?: { name: string; value: number }
  /** Bound to the single v1 worktree. */
  checkedOut?: boolean
}

export type JournalKind =
  | 'edit'
  | 'run'
  | 'fork'
  | 'adopt'
  | 'rename'
  | 'delete'
  | 'promote'
  | 'agent-begin'
  | 'agent-end'
  | 'offline'
  | 'env'

export interface JournalEntry {
  step: number
  time: string
  branch: BranchName
  actor: ActorRef
  intent: string
  kind: JournalKind
  /** One rendered line: 'edited `features` · 3 cells marked stale'. */
  summary: string
  /** Folded failed attempts: 'v3→v4 · 1 failed attempt'. */
  failedAttempts?: number
  settled?: boolean
}

// ---------------------------------------------------------------------------
// Session, env, settings
// ---------------------------------------------------------------------------

export type FlowState = 'running' | 'idle' | 'unpaired' | 'kernel-not-started' | 'daemon-down'

export interface PairedAgent {
  label: string
  branch: BranchName
  state: 'working' | 'idle'
  /** For idle agents: time since the last transaction. Never a fabricated status. */
  idleFor?: string
  /** Latest transaction intent — the "current agent task" line. */
  task?: string
}

export interface WorkbenchSession {
  flowName: string
  workspacePath: string
  state: FlowState
  paired?: PairedAgent
  worktreeBranch: BranchName
  /** Held by an agent session: checkout/rewind/adopt wait, edits defer projection. */
  worktreeLocked?: boolean
  /** "N changes since you were here" — a marker, not an inbox. */
  changesBehind?: number
  diskUsage?: string
}

export interface PackageInfo {
  name: string
  version: string
  /** Installed into the env but not yet active in the running kernel. */
  pendingRestart?: boolean
}

export interface EnvState {
  pythonVersion: string
  packages: PackageInfo[]
  /** Branch lockfile differs from the live venv. */
  mismatch?: boolean
}

export interface FlowSettings {
  reactivity: 'lazy' | 'auto'
  /** Assets cheaper than this auto-materialize when reactivity is 'auto'. */
  autoThresholdSeconds: number
  onEnvChange: 'ask' | 'restart' | 'never'
}

// ---------------------------------------------------------------------------
// Run preflight
// ---------------------------------------------------------------------------

export interface Preflight {
  cached: Slug[]
  recompute: { slug: Slug; seconds: number }[]
  totalSeconds: number
}

// ---------------------------------------------------------------------------
// The whole fixture a page consumes
// ---------------------------------------------------------------------------

export interface WorkbenchFixture {
  session: WorkbenchSession
  settings: FlowSettings
  env: EnvState
  branches: BranchInfo[]
  cellsByBranch: Record<BranchName, FlowCell[]>
  journal: JournalEntry[]
}
