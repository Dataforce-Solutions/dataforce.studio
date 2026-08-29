"""Flow discovery and the one per-user daemon record."""

import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from lumlflow import __version__
from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.dsl.tree import EXCLUDED_DIRS
from lumlflow.flow.errors import FlowAmbiguous, FlowNotFound
from lumlflow.flow.store.flowstore import FLOW_SUFFIX, store_dir

STATE_DIR_ENV = "LUMLFLOW_STATE_DIR"
LOGS_DIRNAME = "logs"
RECORD_NAME = "daemon.json"
LOCK_NAME = "daemon.lock"
LOG_NAME = "daemon.log"

_NETWORK_FILESYSTEMS = frozenset(
    {
        "9p",
        "afs",
        "cifs",
        "fuse.sshfs",
        "ncpfs",
        "nfs",
        "nfs4",
        "smbfs",
    }
)
_MOUNT_ESCAPE = re.compile(r"\\([0-7]{3})")

EntryKind = Literal["flow", "dir", "file"]


@dataclass(frozen=True)
class FlowRef:
    """A flow as verbs address it: by name, or by path when names collide."""

    name: str
    path: Path
    relpath: str

    @property
    def has_store(self) -> bool:
        return store_dir(self.path).is_dir()


@dataclass(frozen=True)
class Entry:
    """One line of the workspace browser. A flow is a document, never a folder."""

    name: str
    path: str
    kind: EntryKind
    size: int | None = None


@dataclass(frozen=True)
class DaemonRecord:
    pid: int
    instance_id: str
    port: int
    token: str
    web_host: str
    web_port: int
    tracker_store: str
    version: str

    def to_json(self) -> bytes:
        return json.dumps(self.__dict__, sort_keys=True).encode("utf-8")


def find_flows(root: Path) -> list[FlowRef]:
    """Every flow under the workspace, nested ones included, in path order."""
    root = root.resolve()
    found: list[FlowRef] = []
    for dirpath, dirnames, _ in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        flows = [name for name in dirnames if name.endswith(FLOW_SUFFIX)]
        # A flow is monolithic: the walk stops at its door rather than
        # descending into cells and the store.
        dirnames[:] = [name for name in dirnames if name not in flows]
        for name in flows:
            path = here / name
            found.append(
                FlowRef(
                    name=name[: -len(FLOW_SUFFIX)],
                    path=path,
                    relpath=path.relative_to(root).as_posix(),
                )
            )
    return found


def select_flow(
    root: Path, *, name: str | None = None, cwd: Path | None = None
) -> FlowRef:
    """Which flow a flow-scoped verb means.

    Named wins — by name, by path under the workspace, or by its own absolute
    path for a flow the workspace does not contain; else the flow the caller is
    standing in; else the workspace's only flow. Anything else is a question,
    and the answer names the candidates rather than guessing at one.
    """
    if name is not None:
        return _addressed(root, name)
    flows = find_flows(root)
    inside = _containing_flow(flows, cwd) if cwd is not None else None
    if inside is not None:
        return inside
    if not flows:
        raise FlowNotFound(f"no flow in {root}. create one with `lumlflow init`")
    if len(flows) > 1:
        raise FlowAmbiguous(f"which flow? {_candidates(flows)}. name one with `--flow`")
    return flows[0]


def flow_here(root: Path, cwd: Path) -> FlowRef | None:
    """The flow a caller is standing in — how a verb addresses one unasked."""
    return _containing_flow(find_flows(root), cwd)


def listing(root: Path, relative: str = "") -> dict[str, Any]:
    """The workspace browser's directory listing — under the launch dir, or above it.

    Upward is how a flow the launch directory does not contain is reached, so
    this browses like a file manager: `parent` is the directory above, and a
    listing outside the workspace spells its own path and its entries' paths
    absolutely, which is what the browser hands back to list or to open them.
    """
    root = root.resolve()
    directory = _within(root, relative)
    if not directory.is_dir():
        raise FlowNotFound(f"there is no directory `{relative}`")
    try:
        children = sorted(directory.iterdir(), key=lambda path: path.name.lower())
    except OSError as unreadable:
        raise FlowNotFound(f"`{directory}` cannot be read") from unreadable
    listed = [
        _entry(child, root) for child in children if child.name not in EXCLUDED_DIRS
    ]
    listed.sort(key=lambda entry: (entry.kind == "file", entry.name.lower()))
    inside = directory.is_relative_to(root)
    return {
        "root": str(root),
        "path": _addressable(root, directory),
        # A workspace is one venv and one set of helpers, so a directory above
        # the launch one is browsable context and never part of it.
        "outside": not inside,
        "parent": str(directory.parent) if directory.parent != directory else None,
        "entries": [entry.__dict__ for entry in listed],
    }


class WorkspaceLock:
    """The OS-released lock held by the daemon for its entire lifetime."""

    def __init__(self) -> None:
        self.path = lock_path()
        self._handle: int | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.set_inheritable(handle, False)
        if not _lock(handle):
            os.close(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        _unlock(handle)
        os.close(handle)


def state_dir() -> Path:
    """Where the daemon's records live, per platform, overridable for tests."""
    override = os.environ.get(STATE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or "~/AppData/Local"
        return Path(base).expanduser() / "lumlflow"
    if platform.system() == "Darwin":
        return Path("~/Library/Application Support/lumlflow").expanduser()
    base = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(base).expanduser() / "lumlflow"


def record_path() -> Path:
    return state_dir() / RECORD_NAME


def lock_path() -> Path:
    return state_dir() / LOCK_NAME


def log_path() -> Path:
    return state_dir() / LOGS_DIRNAME / LOG_NAME


def read_record() -> DaemonRecord | None:
    """The daemon registered for this user, if the record is readable."""
    path = record_path()
    try:
        body = json.loads(path.read_bytes())
        return DaemonRecord(**body)
    except (OSError, ValueError, TypeError):
        return None


def write_record(record: DaemonRecord) -> None:
    atomic_write_bytes(record_path(), record.to_json())
    record_path().chmod(0o600)


def clear_record(*, instance_id: str | None = None) -> None:
    """Deregister only the daemon instance that asked, or a known stale row."""
    record = read_record()
    if record is None or instance_id is None or record.instance_id == instance_id:
        record_path().unlink(missing_ok=True)


def new_record(
    *,
    instance_id: str,
    port: int,
    token: str,
    web_host: str,
    web_port: int,
    tracker_store: str,
) -> DaemonRecord:
    return DaemonRecord(
        pid=os.getpid(),
        instance_id=instance_id,
        port=port,
        token=token,
        web_host=web_host,
        web_port=web_port,
        tracker_store=tracker_store,
        version=__version__,
    )


def lock_held() -> bool:
    """Whether the OS says a daemon owns the singleton lock."""
    probe = WorkspaceLock()
    if not probe.acquire():
        return True
    probe.release()
    return False


def state_dir_is_local(directory: Path | None = None) -> bool:
    path = (directory or state_dir()).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32" and str(path.resolve()).startswith("\\\\"):
        return False
    filesystem = _filesystem_type(path.resolve())
    return filesystem is None or filesystem.casefold() not in _NETWORK_FILESYSTEMS


def network_filesystem_warning(directory: Path | None = None) -> str | None:
    path = (directory or state_dir()).expanduser().resolve()
    if state_dir_is_local(path):
        return None
    return (
        f"warning: {path} is on a network filesystem; file locks are unreliable there"
    )


def _filesystem_type(path: Path) -> str | None:
    """The Linux mount type for a path; unknown platforms are treated as local."""
    mountinfo = Path("/proc/self/mountinfo")
    try:
        lines = mountinfo.read_text("utf-8").splitlines()
    except OSError:
        return None
    matches: list[tuple[int, str]] = []
    for line in lines:
        before, separator, after = line.partition(" - ")
        if not separator:
            continue
        fields = before.split()
        trailing = after.split()
        if len(fields) < 5 or not trailing:
            continue
        mount = Path(_unescape_mount(fields[4]))
        if path == mount or path.is_relative_to(mount):
            matches.append((len(mount.parts), trailing[0]))
    return max(matches, default=(0, None))[1]


def _unescape_mount(value: str) -> str:
    return _MOUNT_ESCAPE.sub(lambda match: chr(int(match.group(1), 8)), value)


def _lock(handle: int) -> bool:
    try:
        if sys.platform == "win32":
            msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle: int) -> None:
    try:
        if sys.platform == "win32":
            os.lseek(handle, 0, os.SEEK_SET)
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        pass


def _named(flows: list[FlowRef], name: str) -> FlowRef:
    wanted = name.removesuffix(FLOW_SUFFIX).strip("/")
    matches = [
        flow
        for flow in flows
        if wanted in (flow.name, flow.relpath, flow.relpath.removesuffix(FLOW_SUFFIX))
    ]
    if not matches:
        raise FlowNotFound(
            f"no flow called `{name}`"
            + (f". this workspace has {_candidates(flows)}" if flows else "")
        )
    if len(matches) > 1:
        raise FlowAmbiguous(
            f"`{name}` names more than one flow: {_paths(matches)}. "
            "use the path to say which"
        )
    return matches[0]


def _containing_flow(flows: list[FlowRef], cwd: Path) -> FlowRef | None:
    here = cwd.resolve()
    return next(
        (flow for flow in flows if here == flow.path or here.is_relative_to(flow.path)),
        None,
    )


def _within(root: Path, relative: str) -> Path:
    """Resolve a browser path — relative to the workspace, or absolute.

    Leaving the workspace is the point: a flow the launch directory does not
    contain is reached by climbing to it. What no path may do is enter a flow,
    which is one entry in this listing and a workbench to open, never a folder
    to walk into.
    """
    if not relative:
        return root
    asked = Path(relative)
    target = (asked if asked.is_absolute() else root / asked).resolve()
    flow = _flow_crossed(root, target)
    if flow is not None:
        raise FlowNotFound(f"`{flow}` is a flow. open it rather than browsing it")
    return target


def _flow_crossed(root: Path, target: Path) -> str | None:
    """A `.flow` directory on the way to `target`, below where it parts company
    with the workspace — the stretch the browser navigated, and the only
    stretch it is in any position to refuse."""
    shared = Path(*os.path.commonprefix([root.parts, target.parts]))
    return next(
        (
            part
            for part in target.relative_to(shared).parts
            if part.endswith(FLOW_SUFFIX)
        ),
        None,
    )


def _addressable(root: Path, directory: Path) -> str:
    """What the browser hands back to list this directory again: root-relative
    inside the workspace — the spelling every existing caller uses — and the
    absolute path above it, which has no root-relative spelling."""
    if not directory.is_relative_to(root):
        return str(directory)
    return directory.relative_to(root).as_posix() if directory != root else ""


def _addressed(root: Path, name: str) -> FlowRef:
    """A flow by name, by path under the workspace, or by its own absolute path.

    The absolute spelling is how the browser opens a flow from above the launch
    directory: it addresses the flow itself, so nothing has to invent a
    root-relative name for a directory the workspace does not contain.
    """
    asked = Path(name)
    if not asked.is_absolute():
        return _named(find_flows(root), name)
    path = asked.resolve()
    if path.is_relative_to(root):
        return _named(find_flows(root), path.relative_to(root).as_posix())
    return _outside_flow(path)


def _outside_flow(path: Path) -> FlowRef:
    """A flow that lives outside the workspace, addressed by where it is."""
    if not (path.is_dir() and path.name.endswith(FLOW_SUFFIX)):
        raise FlowNotFound(f"there is no flow at `{path}`")
    return FlowRef(
        name=path.name[: -len(FLOW_SUFFIX)], path=path, relpath=path.as_posix()
    )


def _entry(path: Path, root: Path) -> Entry:
    # The workspace itself is one of the entries a listing above it holds, and
    # it spells itself the way its neighbours do rather than as an empty path.
    relative = (
        path.relative_to(root).as_posix()
        if path.is_relative_to(root) and path != root
        else str(path)
    )
    if path.is_dir():
        kind: EntryKind = "flow" if path.name.endswith(FLOW_SUFFIX) else "dir"
        return Entry(name=path.name, path=relative, kind=kind)
    try:
        size = path.stat().st_size
    except OSError:
        size = None
    return Entry(name=path.name, path=relative, kind="file", size=size)


def _candidates(flows: list[FlowRef]) -> str:
    return ", ".join(f"`{flow.name}`" for flow in flows)


def _paths(flows: list[FlowRef]) -> str:
    return ", ".join(f"`{flow.relpath}`" for flow in flows)
