"""Verified user-level MCP locations and narrowly scoped config writers."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import tomli_w

from lumlflow import __version__
from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.errors import FlowError

SERVER_NAME = "lumlflow"
MANAGED_ENV = "LUMLFLOW_MANAGED"

Platform = Literal["linux", "darwin", "win32"]
PathBase = Literal["home", "appdata", "codex_home"]


class ConfigShape(StrEnum):
    MCP_SERVERS = "mcpServers"
    VSCODE_SERVERS = "servers"
    OPENCODE = "mcp"
    TOML = "toml"


class EntryState(StrEnum):
    NOT_SET_UP = "not set up"
    SET_UP = "set up"
    OUT_OF_DATE = "out of date"
    BROKEN = "broken"


class HarnessConfigError(FlowError):
    pass


@dataclass(frozen=True)
class ConfigPath:
    base: PathBase
    relative: str
    platforms: tuple[Platform, ...] = ()

    def resolve(
        self,
        *,
        home: Path,
        platform: Platform,
        environment: Mapping[str, str],
    ) -> Path | None:
        if self.platforms and platform not in self.platforms:
            return None
        if self.base == "appdata":
            root = Path(environment.get("APPDATA", home / "AppData" / "Roaming"))
        elif self.base == "codex_home":
            root = Path(environment.get("CODEX_HOME", home / ".codex"))
        else:
            root = home
        return root / self.relative


@dataclass(frozen=True)
class Harness:
    id: str
    display_name: str
    binaries: tuple[str, ...]
    detection_paths: tuple[ConfigPath, ...]
    config_paths: tuple[ConfigPath, ...]
    shape: ConfigShape | None
    cwd_is_project: bool | None
    environment_marker: str | None
    shell: bool
    post_write_hint: str
    config_hint: str
    verification: tuple[str, ...]
    stdio_type: str | None = None
    tools: tuple[str, ...] | None = None

    @property
    def writer(self) -> ConfigShape | None:
        return self.shape

    def config_path(
        self,
        *,
        home: Path | None = None,
        platform: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> Path | None:
        resolved_home = home or Path.home()
        resolved_platform = _platform(platform)
        resolved_environment = environment if environment is not None else os.environ
        for location in self.config_paths:
            path = location.resolve(
                home=resolved_home,
                platform=resolved_platform,
                environment=resolved_environment,
            )
            if path is not None:
                return path
        return None


_DOCS_SCHEME = "https://"

# Each writable row records the current vendor documentation that establishes
# its user-level path and shape. Marker sources are included only where a vendor
# documents a variable inherited by commands the agent runs.
HARNESSES: list[Harness] = [
    Harness(
        id="claude-code",
        display_name="Claude Code",
        binaries=("claude",),
        detection_paths=(ConfigPath("home", ".claude"),),
        config_paths=(ConfigPath("home", ".claude.json"),),
        shape=ConfigShape.MCP_SERVERS,
        cwd_is_project=True,
        environment_marker="CLAUDECODE",
        shell=True,
        post_write_hint="approve the server when Claude Code asks",
        config_hint="~/.claude.json",
        verification=(
            f"{_DOCS_SCHEME}code.claude.com/docs/en/mcp#mcp-installation-scopes",
            f"{_DOCS_SCHEME}code.claude.com/docs/en/plugin-hints",
        ),
    ),
    Harness(
        id="claude-desktop",
        display_name="Claude Desktop",
        binaries=(),
        detection_paths=(
            ConfigPath(
                "home",
                "Library/Application Support/Claude",
                ("darwin",),
            ),
            ConfigPath("appdata", "Claude", ("win32",)),
        ),
        config_paths=(
            ConfigPath(
                "home",
                "Library/Application Support/Claude/claude_desktop_config.json",
                ("darwin",),
            ),
            ConfigPath(
                "appdata",
                "Claude/claude_desktop_config.json",
                ("win32",),
            ),
        ),
        shape=ConfigShape.MCP_SERVERS,
        cwd_is_project=False,
        environment_marker=None,
        shell=False,
        post_write_hint="restart Claude Desktop",
        config_hint="Claude Desktop's claude_desktop_config.json",
        verification=(
            f"{_DOCS_SCHEME}py.sdk.modelcontextprotocol.io/get-started/real-host/#claude-desktop",
        ),
    ),
    Harness(
        id="cursor",
        display_name="Cursor",
        binaries=("cursor-agent", "cursor"),
        detection_paths=(ConfigPath("home", ".cursor"),),
        config_paths=(ConfigPath("home", ".cursor/mcp.json"),),
        shape=ConfigShape.MCP_SERVERS,
        cwd_is_project=True,
        environment_marker="CURSOR_AGENT",
        shell=True,
        post_write_hint="restart Cursor",
        config_hint="~/.cursor/mcp.json",
        verification=(
            f"{_DOCS_SCHEME}docs.cursor.com/context/model-context-protocol#configuration-locations",
            f"{_DOCS_SCHEME}docs.cursor.com/en/agent/terminal#disable-heavy-prompts-for-agent-sessions",
        ),
    ),
    Harness(
        id="windsurf",
        display_name="Windsurf",
        binaries=("windsurf",),
        detection_paths=(ConfigPath("home", ".codeium/windsurf"),),
        config_paths=(ConfigPath("home", ".codeium/windsurf/mcp_config.json"),),
        shape=ConfigShape.MCP_SERVERS,
        cwd_is_project=True,
        environment_marker=None,
        shell=False,
        post_write_hint="restart Windsurf",
        config_hint="~/.codeium/windsurf/mcp_config.json",
        verification=(
            f"{_DOCS_SCHEME}docs.windsurf.com/windsurf/cascade/mcp#mcp-config-json",
        ),
    ),
    Harness(
        id="vscode",
        display_name="VS Code (Copilot)",
        binaries=("code",),
        detection_paths=(
            ConfigPath("home", ".config/Code/User", ("linux",)),
            ConfigPath("home", "Library/Application Support/Code/User", ("darwin",)),
            ConfigPath("appdata", "Code/User", ("win32",)),
        ),
        config_paths=(
            ConfigPath("home", ".config/Code/User/mcp.json", ("linux",)),
            ConfigPath(
                "home", "Library/Application Support/Code/User/mcp.json", ("darwin",)
            ),
            ConfigPath("appdata", "Code/User/mcp.json", ("win32",)),
        ),
        shape=ConfigShape.VSCODE_SERVERS,
        cwd_is_project=True,
        environment_marker=None,
        shell=False,
        post_write_hint="restart VS Code",
        config_hint="the user profile's mcp.json",
        verification=(
            f"{_DOCS_SCHEME}code.visualstudio.com/docs/agent-customization/mcp-servers#_configure-the-mcpjson-file",
            f"{_DOCS_SCHEME}learn.microsoft.com/microsoft-365/admin/manage/mrc-mcp#configure-your-editor",
        ),
        stdio_type="stdio",
    ),
    Harness(
        id="codex",
        display_name="Codex CLI",
        binaries=("codex",),
        detection_paths=(ConfigPath("codex_home", ""),),
        config_paths=(ConfigPath("codex_home", "config.toml"),),
        shape=ConfigShape.TOML,
        cwd_is_project=True,
        environment_marker=None,
        shell=True,
        post_write_hint="restart Codex",
        config_hint="$CODEX_HOME/config.toml (normally ~/.codex/config.toml)",
        verification=(
            f"{_DOCS_SCHEME}developers.openai.com/codex/config-basic/#configuration-precedence",
            f"{_DOCS_SCHEME}developers.openai.com/codex/mcp/#configure-with-configtoml",
            f"{_DOCS_SCHEME}developers.openai.com/codex/config-advanced/#config-and-state-locations",
        ),
    ),
    Harness(
        id="gemini",
        display_name="Gemini CLI",
        binaries=("gemini",),
        detection_paths=(ConfigPath("home", ".gemini"),),
        config_paths=(ConfigPath("home", ".gemini/settings.json"),),
        shape=ConfigShape.MCP_SERVERS,
        cwd_is_project=True,
        environment_marker="GEMINI_CLI",
        shell=True,
        post_write_hint="restart Gemini CLI",
        config_hint="~/.gemini/settings.json",
        verification=(
            f"{_DOCS_SCHEME}github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md#settings-files",
            f"{_DOCS_SCHEME}github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md#configure-the-mcp-server-in-settingsjson",
            f"{_DOCS_SCHEME}github.com/google-gemini/gemini-cli/blob/main/docs/reference/commands.md#shell-mode-and-passthrough-commands-",
        ),
    ),
    Harness(
        id="opencode",
        display_name="OpenCode",
        binaries=("opencode",),
        detection_paths=(ConfigPath("home", ".config/opencode"),),
        config_paths=(ConfigPath("home", ".config/opencode/opencode.json"),),
        shape=ConfigShape.OPENCODE,
        cwd_is_project=True,
        environment_marker=None,
        shell=True,
        post_write_hint="restart OpenCode",
        config_hint="~/.config/opencode/opencode.json",
        verification=(
            f"{_DOCS_SCHEME}opencode.ai/docs/config/#global",
            f"{_DOCS_SCHEME}opencode.ai/docs/mcp-servers/#local",
        ),
        stdio_type="local",
    ),
    Harness(
        id="copilot",
        display_name="Copilot CLI",
        binaries=("copilot",),
        detection_paths=(ConfigPath("home", ".copilot"),),
        config_paths=(ConfigPath("home", ".copilot/mcp-config.json"),),
        shape=ConfigShape.MCP_SERVERS,
        cwd_is_project=True,
        environment_marker=None,
        shell=True,
        post_write_hint="restart Copilot CLI",
        config_hint="~/.copilot/mcp-config.json",
        verification=(
            f"{_DOCS_SCHEME}docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers#editing-the-configuration-file",
            f"{_DOCS_SCHEME}docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#mcp-server-configuration",
        ),
        stdio_type="local",
        tools=("*",),
    ),
    Harness(
        id="jetbrains-ai",
        display_name="JetBrains AI Assistant",
        binaries=("idea", "pycharm", "webstorm"),
        detection_paths=(
            ConfigPath("home", ".config/JetBrains", ("linux",)),
            ConfigPath("home", "Library/Application Support/JetBrains", ("darwin",)),
            ConfigPath("appdata", "JetBrains", ("win32",)),
        ),
        config_paths=(),
        shape=None,
        cwd_is_project=None,
        environment_marker=None,
        shell=False,
        post_write_hint="add the snippet in JetBrains AI Assistant",
        config_hint="Settings > Tools > AI Assistant > Model Context Protocol (MCP)",
        verification=(
            f"{_DOCS_SCHEME}jetbrains.com/help/ai-assistant/mcp.html#connect-to-an-mcp-server",
        ),
    ),
]

HARNESS_REGISTRY = HARNESSES


@dataclass(frozen=True)
class WriteResult:
    path: Path
    changed: bool
    entry: dict[str, Any]


def harness_by_id(harness_id: str) -> Harness:
    for harness in HARNESSES:
        if harness.id == harness_id:
            return harness
    raise HarnessConfigError(f"unknown agent harness `{harness_id}`")


def resolve_executable(
    running_executable: str | Path, *, search_path: str | None = None
) -> str:
    effective_path = search_path if search_path is not None else os.environ.get("PATH")
    if shutil.which(SERVER_NAME, path=effective_path) is not None:
        return SERVER_NAME
    return str(Path(running_executable).resolve())


def detected_harnesses(
    *,
    home: Path | None = None,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    search_path: str | None = None,
) -> list[Harness]:
    return [
        harness
        for harness in HARNESSES
        if is_detected(
            harness,
            home=home,
            platform=platform,
            environment=environment,
            search_path=search_path,
        )
    ]


def is_detected(
    harness: Harness,
    *,
    home: Path | None = None,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    search_path: str | None = None,
) -> bool:
    resolved_home = home or Path.home()
    resolved_platform = _platform(platform)
    resolved_environment = environment if environment is not None else os.environ
    path = search_path if search_path is not None else resolved_environment.get("PATH")
    if any(shutil.which(binary, path=path) for binary in harness.binaries):
        return True
    return any(
        resolved is not None and resolved.exists()
        for location in harness.detection_paths
        if (
            resolved := location.resolve(
                home=resolved_home,
                platform=resolved_platform,
                environment=resolved_environment,
            )
        )
        is not None
    )


def desired_entry(
    harness: Harness,
    *,
    executable: str,
    version: str = __version__,
) -> dict[str, Any]:
    marker = {MANAGED_ENV: version}
    if harness.shape == ConfigShape.OPENCODE:
        return {
            "type": harness.stdio_type or "local",
            "command": [executable, "mcp"],
            "environment": marker,
        }
    entry: dict[str, Any] = {"command": executable, "args": ["mcp"]}
    if harness.stdio_type is not None:
        entry = {"type": harness.stdio_type, **entry}
    entry["env"] = marker
    if harness.tools is not None:
        entry["tools"] = list(harness.tools)
    return entry


def config_snippet(
    harness: Harness,
    *,
    executable: str,
    version: str = __version__,
) -> str:
    shape = harness.shape or ConfigShape.MCP_SERVERS
    document = _document_with_entry(
        shape, desired_entry(harness, executable=executable, version=version)
    )
    return _serialize(document, shape).decode("utf-8")


def read_config(
    harness: Harness,
    *,
    home: Path | None = None,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    config_path = _config_path(
        harness,
        home=home,
        platform=platform,
        environment=environment,
        override=path,
    )
    if not config_path.exists():
        return {}
    return _parse(config_path.read_bytes(), harness.shape, config_path)


def entry_state(
    harness: Harness,
    *,
    executable: str,
    version: str = __version__,
    home: Path | None = None,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    path: Path | None = None,
    search_path: str | None = None,
) -> EntryState:
    document = read_config(
        harness,
        home=home,
        platform=platform,
        environment=environment,
        path=path,
    )
    section = _section(document, harness.shape, create=False)
    owned = [(name, entry) for name, entry in section.items() if is_owned(name, entry)]
    if not owned:
        return EntryState.NOT_SET_UP
    desired = desired_entry(harness, executable=executable, version=version)
    if owned != [(SERVER_NAME, desired)]:
        return EntryState.OUT_OF_DATE
    resolved_environment = environment if environment is not None else os.environ
    environment_path = resolved_environment.get("PATH")
    effective_search_path = search_path if search_path is not None else environment_path
    if any(
        not _entry_command_exists(entry, effective_search_path) for _, entry in owned
    ):
        return EntryState.BROKEN
    return EntryState.SET_UP


def write_config(
    harness: Harness,
    *,
    executable: str,
    version: str = __version__,
    home: Path | None = None,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    path: Path | None = None,
) -> WriteResult:
    config_path = _config_path(
        harness,
        home=home,
        platform=platform,
        environment=environment,
        override=path,
    )
    existing = config_path.read_bytes() if config_path.exists() else None
    desired = desired_entry(harness, executable=executable, version=version)
    rendered = _render_config_update(harness, desired, existing, config_path)
    if rendered is None:
        return WriteResult(path=config_path, changed=False, entry=desired)
    backup = config_path.with_name(f"{config_path.name}.bak")
    if existing is not None and not backup.exists():
        atomic_write_bytes(backup, existing)
    latest = config_path.read_bytes() if config_path.exists() else None
    rendered = _render_config_update(harness, desired, latest, config_path)
    if rendered is None:
        return WriteResult(path=config_path, changed=False, entry=desired)
    atomic_write_bytes(config_path, rendered)
    return WriteResult(path=config_path, changed=True, entry=desired)


def is_owned(name: str, entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    env = entry.get("env") or entry.get("environment")
    if isinstance(env, dict) and MANAGED_ENV in env:
        return True
    return name == SERVER_NAME and _is_lumlflow_command(_entry_command(entry))


def _config_path(
    harness: Harness,
    *,
    home: Path | None,
    platform: str | None,
    environment: Mapping[str, str] | None,
    override: Path | None,
) -> Path:
    if harness.shape is None:
        raise HarnessConfigError(
            f"{harness.display_name} is detect-only; paste the snippet in "
            f"{harness.config_hint}"
        )
    config_path = override or harness.config_path(
        home=home, platform=platform, environment=environment
    )
    if config_path is None:
        raise HarnessConfigError(
            f"{harness.display_name} has no verified user-level config on this platform"
        )
    return config_path


def _parse(
    raw: bytes,
    shape: ConfigShape | None,
    path: Path,
) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        if shape == ConfigShape.TOML:
            parsed = tomllib.loads(text)
        elif shape in {ConfigShape.OPENCODE, ConfigShape.VSCODE_SERVERS}:
            parsed = json.loads(_strip_trailing_commas(_strip_json_comments(text)))
        else:
            parsed = json.loads(text)
    except (
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as error:
        raise HarnessConfigError(
            f"cannot update {path}: the config file does not parse"
        ) from error
    if not isinstance(parsed, dict):
        raise HarnessConfigError(
            f"cannot update {path}: the config root is not a table"
        )
    return parsed


def _render_config_update(
    harness: Harness,
    desired: dict[str, Any],
    existing: bytes | None,
    path: Path,
) -> bytes | None:
    document = _parse(existing, harness.shape, path) if existing is not None else {}
    section = _section(document, harness.shape, create=True)
    owned = [(name, entry) for name, entry in section.items() if is_owned(name, entry)]
    if owned == [(SERVER_NAME, desired)]:
        return None
    if SERVER_NAME in section and not is_owned(SERVER_NAME, section[SERVER_NAME]):
        raise HarnessConfigError(
            f"cannot set up {harness.display_name}: `{SERVER_NAME}` already names "
            f"an unmanaged server in {path}"
        )
    for name, _entry in owned:
        del section[name]
    section[SERVER_NAME] = desired
    return _serialize(document, harness.shape)


def _strip_json_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if char == "/" and next_char == "/":
            output.extend((" ", " "))
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if char == "/" and next_char == "*":
            output.extend((" ", " "))
            index += 2
            while index < len(text):
                if text[index : index + 2] == "*/":
                    output.extend((" ", " "))
                    index += 2
                    break
                output.append(text[index] if text[index] in "\r\n" else " ")
                index += 1
            else:
                raise ValueError("unterminated JSON comment")
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _strip_trailing_commas(text: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            output.append(char)
            continue
        if char == ",":
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index < len(text) and text[next_index] in "}]":
                continue
        output.append(char)
    return "".join(output)


def _section(
    document: dict[str, Any],
    shape: ConfigShape | None,
    *,
    create: bool,
) -> dict[str, Any]:
    if shape is None:
        raise HarnessConfigError("this harness has no writable config shape")
    key = "mcp_servers" if shape == ConfigShape.TOML else str(shape.value)
    value = document.get(key)
    if value is None and create:
        value = {}
        document[key] = value
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HarnessConfigError(f"the `{key}` config value is not a table")
    return value


def _document_with_entry(shape: ConfigShape, entry: dict[str, Any]) -> dict[str, Any]:
    key = "mcp_servers" if shape == ConfigShape.TOML else shape.value
    return {key: {SERVER_NAME: entry}}


def _serialize(document: dict[str, Any], shape: ConfigShape | None) -> bytes:
    if shape == ConfigShape.TOML:
        return tomli_w.dumps(document).encode("utf-8")
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _entry_command(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    command = entry.get("command")
    if isinstance(command, str):
        return command
    if isinstance(command, list) and command and isinstance(command[0], str):
        return command[0]
    return None


def _is_lumlflow_command(command: str | None) -> bool:
    if command is None:
        return False
    return command.replace("\\", "/").rsplit("/", 1)[-1].lower() in {
        "lumlflow",
        "lumlflow.exe",
    }


def _entry_command_exists(entry: object, search_path: str | None) -> bool:
    command = _entry_command(entry)
    if command is None:
        return False
    if Path(command).is_absolute() or "/" in command or "\\" in command:
        return Path(command).is_file()
    return shutil.which(command, path=search_path) is not None


def _platform(platform: str | None) -> Platform:
    value = platform or sys.platform
    if value.startswith("win") or value.startswith("cygwin"):
        return "win32"
    if value == "darwin":
        return "darwin"
    return "linux"
