from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class StoreModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlowInitOp(StoreModel):
    op: Literal["flow_init"] = "flow_init"
    flow_id: str
    name: str
    language: str = "python"
    branch_id: str
    branch_name: str = "main"


class CellAcceptedOp(StoreModel):
    op: Literal["cell_accepted"] = "cell_accepted"
    uid: str
    version_id: str
    slug: str
    source_hash: str
    bound_hash: str
    definition_hash: str
    manifest: dict[str, JsonValue]
    flags: list[str] = Field(default_factory=list)
    parent_version: str | None = None
    author: str | None = None
    copied_from: str | None = None


class CellRemovedOp(StoreModel):
    op: Literal["cell_removed"] = "cell_removed"
    uid: str


class SelectionSetOp(StoreModel):
    op: Literal["selection_set"] = "selection_set"
    uid: str
    version_id: str
    pinned: bool = False


class BranchCreatedOp(StoreModel):
    op: Literal["branch_created"] = "branch_created"
    branch_id: str
    name: str
    parent: str | None = None
    fork_step: int
    sweep_group: str | None = None


class BranchArchivedOp(StoreModel):
    op: Literal["branch_archived"] = "branch_archived"
    branch_id: str


class BranchRenamedOp(StoreModel):
    op: Literal["branch_renamed"] = "branch_renamed"
    branch_id: str
    old_name: str
    new_name: str


class WorktreeBoundOp(StoreModel):
    op: Literal["worktree_bound"] = "worktree_bound"
    path: str
    branch_id: str
    actor: str | None = None
    lock_holder: str | None = None


class RewoundOp(StoreModel):
    op: Literal["rewound"] = "rewound"
    to_step: int


class AdoptedOp(StoreModel):
    op: Literal["adopted"] = "adopted"
    uid: str
    from_branch: str
    version_id: str


class RenamedOp(StoreModel):
    op: Literal["renamed"] = "renamed"
    uid: str
    old_slug: str
    new_slug: str


class InputRecord(StoreModel):
    uid: str
    output: str
    content_hash: str
    mat_id: str


class LumlReference(StoreModel):
    collection: str
    artifact_id: str
    version: str
    digest: str


class OutputRecord(StoreModel):
    content_hash: str
    kind: str
    size: int = Field(ge=0)
    preview_ref: str | None = None
    value_ref: str | None = None
    luml_ref: LumlReference | None = None
    native_type: Literal["model", "dataset", "experiment"] | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    persisted: bool = False


class RunRecordedOp(StoreModel):
    op: Literal["run_recorded"] = "run_recorded"
    mat_id: str
    version_id: str
    memo_key: str
    state: Literal["running", "succeeded", "failed", "cancelled"]
    inputs: dict[str, InputRecord] = Field(default_factory=dict)
    outputs: dict[str, OutputRecord] = Field(default_factory=dict)
    identity_dependent: bool = False
    env_lock_hash: str | None = None
    cost_seconds: float | None = None
    log_ref: str | None = None
    started_step: int | None = None
    finished_step: int | None = None


class MemoHitOp(StoreModel):
    op: Literal["memo_hit"] = "memo_hit"
    uid: str
    version_id: str
    memo_key: str
    mat_id: str | None = None


class EnvChangedOp(StoreModel):
    op: Literal["env_changed"] = "env_changed"
    lock_hash: str
    summary: str


class UploadRecordedOp(StoreModel):
    op: Literal["upload_recorded"] = "upload_recorded"
    mat_id: str
    output: str
    luml_ref: LumlReference


class UploadStateOp(StoreModel):
    op: Literal["upload_state"] = "upload_state"
    mat_id: str
    output: str
    state: Literal["queued", "uploading", "done", "failed"]
    attempts: int = Field(ge=0)
    error: str | None = None


class PromotedOp(StoreModel):
    op: Literal["promoted"] = "promoted"
    mat_id: str
    output: str
    native_type: Literal["model", "dataset", "experiment"]


class FlagSetOp(StoreModel):
    op: Literal["flag_set"] = "flag_set"
    flag: str
    enabled: bool = True
    uid: str | None = None
    version_id: str | None = None


class SecretRefAddedOp(StoreModel):
    op: Literal["secret_ref_added"] = "secret_ref_added"
    name: str
    reference: str


FlowOp = Annotated[
    FlowInitOp
    | CellAcceptedOp
    | CellRemovedOp
    | SelectionSetOp
    | BranchCreatedOp
    | BranchArchivedOp
    | BranchRenamedOp
    | WorktreeBoundOp
    | RewoundOp
    | AdoptedOp
    | RenamedOp
    | RunRecordedOp
    | MemoHitOp
    | EnvChangedOp
    | UploadRecordedOp
    | UploadStateOp
    | PromotedOp
    | FlagSetOp
    | SecretRefAddedOp,
    Field(discriminator="op"),
]


class Transaction(StoreModel):
    step: int = Field(ge=1)
    ts: str
    actor: str
    intent: str
    offline: bool = False
    settled: bool = False
    branch: str
    ops: list[FlowOp] = Field(min_length=1)


class AssetVersion(StoreModel):
    version_id: str
    uid: str
    slug: str
    source_hash: str
    bound_hash: str
    definition_hash: str
    manifest: dict[str, JsonValue]
    parent_version_id: str | None = None
    author: str | None = None
    created_step: int


class Branch(StoreModel):
    branch_id: str
    name: str
    parent_branch_id: str | None = None
    fork_step: int
    archived: bool = False
    sweep_group: str | None = None


class Selection(StoreModel):
    branch_id: str
    uid: str
    version_id: str
    pinned: bool = False


class Baseline(StoreModel):
    branch_id: str
    uid: str
    mat_id: str


class Materialization(StoreModel):
    mat_id: str
    version_id: str
    memo_key: str
    state: Literal["running", "succeeded", "failed", "cancelled"]
    branch_id: str
    inputs: dict[str, InputRecord] = Field(default_factory=dict)
    outputs: dict[str, OutputRecord] = Field(default_factory=dict)
    identity_dependent: bool = False
    env_lock_hash: str | None = None
    cost_seconds: float | None = None
    log_ref: str | None = None
    started_step: int | None = None
    finished_step: int | None = None


class Worktree(StoreModel):
    path: str
    branch_id: str
    actor: str | None = None
    lock_holder: str | None = None


class ValuePin(StoreModel):
    content_hash: str
    reason: str
    expires_step: int | None = None
