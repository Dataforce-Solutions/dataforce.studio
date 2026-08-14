from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import EnvChangedOp, JsonValue


class EnvironmentManager:
    def __init__(self, store: FlowStore) -> None:
        self.store = store
        self.flow_dir = store.flow_dir
        self.live_lock_path = store.store_dir / "kernel" / "env-lock-hash"
        self.restart_required = False
        self.restart_packages: tuple[str, ...] = ()
        if self._venv_python() is not None and self.live_lock_hash is None:
            self._record_live_lock_hash(self.branch_lock_hash)

    @property
    def branch_lock_hash(self) -> str | None:
        lock_path = self.flow_dir / "uv.lock"
        return sha256_bytes(lock_path.read_bytes()) if lock_path.is_file() else None

    @property
    def live_lock_hash(self) -> str | None:
        try:
            value = self.live_lock_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        return value or None

    @property
    def branch_lock_mismatch(self) -> bool:
        branch_hash = self.branch_lock_hash
        live_hash = self.live_lock_hash
        return (
            branch_hash is not None
            and live_hash is not None
            and branch_hash != live_hash
        )

    def ensure_environment(self) -> None:
        if not (self.flow_dir / "pyproject.toml").is_file():
            return
        if self._venv_python() is None:
            self._run_uv("sync")
            self._record_live_lock_hash(self.branch_lock_hash)
        elif self.live_lock_hash is None:
            self._record_live_lock_hash(self.branch_lock_hash)

    async def add(self, package: str, *, actor: str, intent: str | None) -> None:
        normalized = package.strip()
        if not normalized:
            raise ValueError("env add requires a package")
        await asyncio.to_thread(self._apply_change, "add", normalized)
        self._commit_change(f"add {normalized}", actor=actor, intent=intent)

    async def remove(self, package: str, *, actor: str, intent: str | None) -> None:
        normalized = package.strip()
        if not normalized:
            raise ValueError("env remove requires a package")
        await asyncio.to_thread(self._apply_change, "remove", normalized)
        self._commit_change(f"remove {normalized}", actor=actor, intent=intent)

    def installed_packages(self) -> dict[str, str]:
        python = self._venv_python()
        if python is None:
            return {}
        script = (
            "import importlib.metadata as m,json;"
            "print(json.dumps({"
            "(d.metadata.get('Name') or '').lower().replace('_','-'):d.version "
            "for d in m.distributions() if d.metadata.get('Name')}))"
        )
        completed = subprocess.run(
            [os.fspath(python), "-c", script],
            cwd=self.flow_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout or "{}")
        if not isinstance(payload, dict):
            raise RuntimeError("flow environment returned invalid package metadata")
        return {
            _normalize_package_name(str(name)): str(version)
            for name, version in payload.items()
        }

    def compare_loaded_packages(self, loaded: dict[str, str]) -> None:
        installed = self.installed_packages()
        changed = sorted(
            name
            for raw_name, loaded_version in loaded.items()
            if (name := _normalize_package_name(raw_name))
            and installed.get(name) != loaded_version
        )
        self.restart_packages = tuple(changed)
        self.restart_required = bool(changed)

    def kernel_restarted(self) -> None:
        self.restart_required = False
        self.restart_packages = ()

    def status(self, *, include_packages: bool = False) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "lock_hash": self.branch_lock_hash,
            "live_lock_hash": self.live_lock_hash,
            "branch_lock_mismatch": self.branch_lock_mismatch,
            "background_deferred": self.branch_lock_mismatch,
            "restart_required": self.restart_required,
            "restart_packages": list(self.restart_packages),
        }
        if include_packages:
            result["packages"] = cast(JsonValue, self.installed_packages())
        return result

    def _commit_change(self, summary: str, *, actor: str, intent: str | None) -> None:
        lock_hash = self.branch_lock_hash
        if lock_hash is None:
            raise RuntimeError("uv did not produce uv.lock")
        self._record_live_lock_hash(lock_hash)
        self.store.commit(
            actor=actor,
            intent=intent or f"update environment: {summary}",
            ops=[EnvChangedOp(lock_hash=lock_hash, summary=summary)],
        )

    def _record_live_lock_hash(self, lock_hash: str | None) -> None:
        if lock_hash is None:
            return
        atomic_write(self.live_lock_path, f"{lock_hash}\n".encode())

    def _run_uv(self, command: str, *arguments: str) -> None:
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv is required to manage the flow environment")
        subprocess.run(
            [uv, command, *arguments, "--project", os.fspath(self.flow_dir)],
            cwd=self.flow_dir,
            check=True,
        )

    def _apply_change(self, command: str, package: str) -> None:
        self._run_uv(command, package)
        self._run_uv("sync")

    def _venv_python(self) -> Path | None:
        candidates = (
            self.flow_dir / ".venv" / "Scripts" / "python.exe",
            self.flow_dir / ".venv" / "bin" / "python",
        )
        return next((path for path in candidates if path.is_file()), None)


def _normalize_package_name(name: str) -> str:
    return name.casefold().replace("_", "-").replace(".", "-")
