from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    output: str


Invoke = Callable[[Sequence[str]], CommandResult]


def run_gate(flow_dir: Path, invoke: Invoke) -> list[CommandResult]:
    cell_path = flow_dir / "cells" / "train_model.py"
    source = cell_path.read_text(encoding="utf-8")
    broken = source.replace(
        "return {", "raise RuntimeError('gate failure')\n        return {", 1
    )
    cell_path.write_text(broken, encoding="utf-8")
    failed = invoke(("run", "train_model"))
    inspected = invoke(("status",))
    cell_path.write_text(source, encoding="utf-8")
    fixed = invoke(("run", "train_model"))
    results = [failed, inspected, fixed]
    if failed.exit_code == 0 or inspected.exit_code != 0 or fixed.exit_code != 0:
        raise RuntimeError("Tier-0 edit/run/inspect/fix loop failed")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("flow_dir", type=Path)
    parser.add_argument("--lumlflow", default="lumlflow")
    arguments = parser.parse_args()

    def invoke(command: Sequence[str]) -> CommandResult:
        completed = subprocess.run(
            [arguments.lumlflow, *command],
            cwd=arguments.flow_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout)

    run_gate(arguments.flow_dir, invoke)


if __name__ == "__main__":
    main()
