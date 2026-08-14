from __future__ import annotations

import os
import time
from pathlib import Path


def replace_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.01 * (2**attempt))
