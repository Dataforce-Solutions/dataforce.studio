from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .api import DaemonServer


def main() -> None:
    parser = argparse.ArgumentParser(prog="lumlflow daemon")
    parser.add_argument("--flow-dir", type=Path, required=True)
    parser.add_argument("--headless", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(
        DaemonServer(arguments.flow_dir, watch_worktree=not arguments.headless).serve()
    )


if __name__ == "__main__":
    main()
