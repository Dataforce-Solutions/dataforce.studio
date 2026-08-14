from __future__ import annotations

import argparse
from pathlib import Path

from .rpc import KernelServer


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m lumlflow_kernel")
    parser.add_argument("--flow-dir", type=Path, required=True)
    transport = parser.add_mutually_exclusive_group(required=True)
    transport.add_argument("--socket", dest="socket_path", type=Path)
    transport.add_argument("--port", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--token")
    arguments = parser.parse_args()
    server = KernelServer(
        arguments.flow_dir,
        socket_path=arguments.socket_path,
        host=arguments.host,
        port=arguments.port,
        token=arguments.token,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
