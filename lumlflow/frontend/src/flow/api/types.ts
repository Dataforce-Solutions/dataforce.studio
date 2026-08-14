export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue }

export interface InputRecord {
  uid: string
  output: string
  content_hash: string
  mat_id: string
}

export interface OutputRecord {
  content_hash: string
  kind: string
  size: number
  preview_ref: string | null
  value_ref: string | null
  luml_ref: LumlReference | null
  native_type: 'model' | 'dataset' | 'experiment' | null
  metadata: Record<string, JsonValue>
  persisted: boolean
}

export interface LumlReference {
  collection: string
  artifact_id: string
  version: string
  digest: string
}

export type FlowOp =
  | {
      op: 'flow_init'
      flow_id: string
      name: string
      language: string
      branch_id: string
      branch_name: string
    }
  | {
      op: 'cell_accepted'
      uid: string
      version_id: string
      slug: string
      source_hash: string
      bound_hash: string
      definition_hash: string
      manifest: Record<string, JsonValue>
      flags: string[]
      parent_version: string | null
      author: string | null
      copied_from: string | null
    }
  | { op: 'cell_removed'; uid: string }
  | { op: 'selection_set'; uid: string; version_id: string; pinned: boolean }
  | {
      op: 'branch_created'
      branch_id: string
      name: string
      parent: string | null
      fork_step: number
      sweep_group: string | null
    }
  | { op: 'branch_archived'; branch_id: string }
  | { op: 'branch_renamed'; branch_id: string; old_name: string; new_name: string }
  | {
      op: 'worktree_bound'
      path: string
      branch_id: string
      actor: string | null
      lock_holder: string | null
    }
  | { op: 'rewound'; to_step: number }
  | { op: 'adopted'; uid: string; from_branch: string; version_id: string }
  | { op: 'renamed'; uid: string; old_slug: string; new_slug: string }
  | {
      op: 'run_recorded'
      mat_id: string
      version_id: string
      memo_key: string
      state: 'running' | 'succeeded' | 'failed' | 'cancelled'
      inputs: Record<string, InputRecord>
      outputs: Record<string, OutputRecord>
      identity_dependent: boolean
      env_lock_hash: string | null
      cost_seconds: number | null
      log_ref: string | null
      started_step: number | null
      finished_step: number | null
    }
  | { op: 'memo_hit'; uid: string; version_id: string; memo_key: string; mat_id: string | null }
  | { op: 'env_changed'; lock_hash: string; summary: string }
  | { op: 'upload_recorded'; mat_id: string; output: string; luml_ref: Record<string, JsonValue> }
  | {
      op: 'upload_state'
      mat_id: string
      output: string
      state: 'queued' | 'uploading' | 'done' | 'failed'
      attempts: number
      error: string | null
    }
  | {
      op: 'promoted'
      mat_id: string
      output: string
      native_type: 'model' | 'dataset' | 'experiment'
    }
  | {
      op: 'flag_set'
      flag: string
      enabled: boolean
      uid: string | null
      version_id: string | null
    }
  | { op: 'secret_ref_added'; name: string; reference: string }

export interface JournalTransaction {
  step: number
  ts: string
  actor: string
  intent: string
  offline: boolean
  settled: boolean
  branch: string
  ops: FlowOp[]
}

export interface JournalMessage {
  channel: 'journal'
  kind: 'transaction'
  cursor: number
  transaction: JournalTransaction
}

export interface KernelMessage {
  channel: 'journal'
  kind: 'kernel'
  event: string
  run_id: string | null
  payload: Record<string, JsonValue>
}

export interface LogChunk {
  run_id: string
  stream: 'stdout' | 'stderr'
  seq: number
  bytes: string
  slug?: string
}

export interface RunLogMessage {
  channel: 'run-log'
  kind: 'chunk'
  run_id: string
  chunk: LogChunk
}

export type JournalStreamMessage = JournalMessage | KernelMessage

export interface StalenessVerdict {
  state: 'synced' | 'unsynced' | 'unmaterialized' | 'failed'
  causes: string[]
}

export interface PreviewPayload {
  schema: number
  kind: string
  blocks: Record<string, JsonValue>[]
  truncated?: boolean
}

export interface AssetPage {
  columns: string[]
  rows: Record<string, JsonValue>[]
  offset: number
  total_rows: number
}

export interface LiveOutput {
  name: string
  kind: string
  content_hash: string | null
  preview: PreviewPayload | null
}

export interface LiveCell {
  uid: string
  slug: string
  version_id: string
  definition_hash: string
  source: string
  manifest: Record<string, JsonValue>
  verdict: { direct: StalenessVerdict; transitive: StalenessVerdict }
  outputs: LiveOutput[]
  logs: LogChunk[]
  run_id: string | null
  computed_under_older_env?: boolean
}

export interface UploadQueueState {
  state: 'queued' | 'uploading' | 'done' | 'failed'
  attempts: number
  error: string | null
}

export interface SweepVariant {
  branch: string
  branch_id: string
  params: Record<string, JsonValue>
  output_hashes: Record<string, string | null>
}

export interface SweepComparison {
  group: string
  parent: string
  fork_step: number
  variants: SweepVariant[]
}

export interface LiveSessionSnapshot {
  flow_id: string
  name: string
  branch: string
  step: number
  cells: LiveCell[]
  sweeps: SweepComparison[]
}

export interface LiveBranch {
  branch_id: string
  name: string
  parent_branch_id: string | null
  fork_step: number
  archived: boolean
  sweep_group: string | null
}

export interface LiveTreeSnapshot {
  branch: string
  branches: LiveBranch[]
  cells: Record<string, JsonValue>[]
}
