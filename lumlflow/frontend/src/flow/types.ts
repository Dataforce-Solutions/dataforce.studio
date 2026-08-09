/**
 * Object model for the Flow workbench concepts.
 *
 * Read this before building a concept — the type names encode design decisions
 * that were argued out before any UI existed. The two that trip people up:
 *
 * 1. `DivergenceKind`. Two branches differ at an asset either because someone
 *    *edited* it (definition divergence: source/params changed) or merely because
 *    something upstream changed (materialization divergence: same code, different
 *    inputs). Definition divergence is rare and structural; materialization
 *    divergence is transitively closed and therefore covers most of the graph.
 *    A UI that renders them the same way is unreadable past ~5 branches.
 *
 * 2. `assetId` vs `name`. Agents rename things constantly. Identity is the id;
 *    the name is a display property that can change between versions.
 */

export type AssetId = string
export type VersionId = string
export type BranchId = string
export type AgentId = string
export type OutputName = string

export type AssetKind =
  | 'source' // raw data pulled in from outside the flow
  | 'frame' // tabular data
  | 'plot' // a figure
  | 'note' // prose; the non-code cell
  | 'model' // a fitted model
  | 'experiment' // training run: config, curves, checkpoints
  | 'eval' // evaluation run: scores, traces
  | 'metric' // a scalar or series derived for reporting

/** Assets whose materialization is not a pure function of their declared inputs. */
export type Volatility = 'pure' | 'seeded' | 'nondeterministic' | 'external'

export interface OutputDef {
  name: OutputName
  kind: AssetKind
  /**
   * Content hash of the materialized value. Early cutoff compares these, not
   * version ids: an edit that changes `run` but not `checkpoint` must not
   * invalidate consumers that only read `checkpoint`.
   */
  contentHash: string
}

export interface AssetDefinition {
  assetId: AssetId
  /** Display name at this version. Changes on rename; `assetId` does not. */
  name: string
  kind: AssetKind
  /** Upstream assets, by stable id. */
  deps: AssetId[]
  params: Record<string, ParamValue>
  /** Python source of `materialize()`, shown in the code panel. */
  source: string
  /** First line of the class docstring; the prose a `note` asset renders. */
  doc: string
  volatility: Volatility
  outputs: OutputDef[]
}

export type ParamValue = string | number | boolean | null | ParamValue[]

export interface AssetVersion {
  versionId: VersionId
  assetId: AssetId
  definition: AssetDefinition
  /** hash(AST-normalized source + params). Identical source ⇒ identical hash. */
  definitionHash: string
  /** Step in the event log at which this version was authored. */
  createdAtStep: number
  authoredBy: AgentId
  /** Intent of the transaction that produced this version. Drives grouping. */
  intent: string
  /** Failed attempts stay in history but collapse out of default views. */
  status: 'ok' | 'failed'
  failureMessage?: string
}

export interface Materialization {
  versionId: VersionId
  /** Version ids of the upstream materializations consumed. */
  inputVersionIds: VersionId[]
  state: MaterializationState
  /** Wall-clock seconds the materialization took, or would take to recompute. */
  costSeconds: number
  cached: boolean
  /** Rendered value, keyed by output name. */
  values: Record<OutputName, ArtifactValue>
  metrics?: Record<string, number>
}

export type MaterializationState =
  | 'materialized'
  | 'running'
  | 'invalidating' // reactlog: a distinct phase, edges tear down here
  | 'unsynced'
  | 'never'
  | 'failed'

/** Why an asset shows as unsynced. Non-transitive, per Dagster: an asset is not
 *  unsynced merely because an ancestor is — only when a *direct* parent
 *  rematerialized with a new content hash, or its own definition changed. */
export type UnsyncedCause = 'definition-changed' | 'deps-rewired' | 'parent-rematerialized'

export interface Branch {
  branchId: BranchId
  name: string
  parentBranchId: BranchId | null
  /** Step at which this branch forked from its parent. */
  forkedAtStep: number
  /** One selected version per asset. Assets absent from the map are not in this slice. */
  selection: Record<AssetId, VersionId>
  /**
   * Assets pinned at fork time rather than tracking the parent. Pin-at-fork is
   * the default; this records what the pin was so divergent pins across
   * branches can be detected and warned about.
   */
  pins: Record<AssetId, VersionId>
  color: string
  archived: boolean
  /** Set when this branch was created by a sweep rather than by hand. */
  sweepGroup?: string
}

// ---------------------------------------------------------------------------
// Rendered artifact values
// ---------------------------------------------------------------------------

export type ArtifactValue =
  | FrameValue
  | PlotValue
  | NoteValue
  | ModelValue
  | ExperimentValue
  | EvalValue
  | MetricValue

export interface FrameValue {
  type: 'frame'
  columns: string[]
  dtypes: string[]
  rows: (string | number | null)[][]
  totalRows: number
}

export interface PlotValue {
  type: 'plot'
  title: string
  /** Rendered as a simple inline SVG; concepts should not need a chart library. */
  series: { label: string; points: [number, number][]; color?: string }[]
  xLabel: string
  yLabel: string
  kind: 'line' | 'scatter' | 'bar' | 'hist'
}

export interface NoteValue {
  type: 'note'
  markdown: string
}

export interface ModelValue {
  type: 'model'
  flavor: string
  paramCount: number
  sizeBytes: number
  signature: string
}

export interface ExperimentValue {
  type: 'experiment'
  runName: string
  config: Record<string, ParamValue>
  curves: { name: string; points: [number, number][] }[]
  finalMetrics: Record<string, number>
  checkpointRef: string
}

export interface EvalValue {
  type: 'eval'
  datasetRef: string
  sampleCount: number
  scores: Record<string, number>
  /** Traces belong to an eval, not to the graph — they are not assets. */
  traces: { sampleId: string; prompt: string; output: string; score: number; latencyMs: number }[]
}

export interface MetricValue {
  type: 'metric'
  name: string
  value: number
  higherIsBetter: boolean
}

// ---------------------------------------------------------------------------
// Event log — drives live playback
// ---------------------------------------------------------------------------

export type FlowOp =
  | { op: 'create-asset'; assetId: AssetId; version: AssetVersion }
  | { op: 'edit-asset'; assetId: AssetId; version: AssetVersion }
  | { op: 'rename-asset'; assetId: AssetId; from: string; to: string }
  | { op: 'delete-asset'; assetId: AssetId }
  | { op: 'rewire-asset'; assetId: AssetId; depsBefore: AssetId[]; depsAfter: AssetId[] }
  | { op: 'materialize'; assetId: AssetId; versionId: VersionId; result: Materialization }
  | { op: 'fork-branch'; branchId: BranchId; fromBranchId: BranchId; name: string }
  | { op: 'accept-upstream'; branchId: BranchId; assetId: AssetId; versionId: VersionId }

/**
 * A batch of ops that lands atomically, carrying the author's intent.
 *
 * The intent string is not decoration: "grouped by intent" is not computable
 * from raw mutation events, so the agent supplies it per transaction — the
 * commit message for a graph edit. Concept 3's grouping and the difference
 * table's change chips both read it.
 */
export interface Transaction {
  txId: string
  step: number
  branchId: BranchId
  author: AgentId
  intent: string
  ops: FlowOp[]
  /** True once every asset in the branch is materialized and consistent.
   *  reactlog's idle marks — the only states worth time-travelling to. */
  settled: boolean
}

export interface Agent {
  agentId: AgentId
  label: string
  color: string
  /** Where this agent is working right now, for presence rendering. */
  activeBranchId: BranchId | null
  activeAssetId: AssetId | null
}

// ---------------------------------------------------------------------------
// Session / project
// ---------------------------------------------------------------------------

export interface FlowSession {
  sessionId: string
  name: string
  projectName: string
  scenario: 'churn' | 'llm-eval'
  createdAt: string
  assets: Record<AssetId, AssetVersion[]>
  materializations: Record<VersionId, Materialization>
  branches: Record<BranchId, Branch>
  agents: Record<AgentId, Agent>
  transactions: Transaction[]
  /** Branch shown when the session opens. */
  headBranchId: BranchId
}

// ---------------------------------------------------------------------------
// Derived views — computed by engine.ts, never hand-authored in fixtures
// ---------------------------------------------------------------------------

export type DivergenceKind =
  | 'none'
  /** Someone edited this asset: source or params differ between slices. */
  | 'definition'
  /** Same code, different upstream inputs. Transitively closed downstream. */
  | 'materialization'

export interface AssetDivergence {
  assetId: AssetId
  kind: DivergenceKind
  /** versionId per branch, for the branches under comparison. */
  byBranch: Record<BranchId, VersionId | null>
}

export interface IntegrityWarning {
  kind: 'divergent-pin' | 'dataset-mismatch' | 'scoring-mismatch' | 'nondeterministic-input'
  /** Short line rendered inline above a comparison. */
  message: string
  assetId?: AssetId
  affectedBranchIds: BranchId[]
}

export interface PreflightCost {
  /** Assets that would materialize from cache — instant. */
  cachedAssetIds: AssetId[]
  /** Assets that would recompute, with their cost. */
  recomputeAssetIds: AssetId[]
  totalSeconds: number
}
