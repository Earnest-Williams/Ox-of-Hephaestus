"""Inspect or control the game's private database from ``game/``.

python -m server.conf.oxpg status | start | stop | where
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .cluster import ClusterError, find_binaries, is_running, layout_for, stop
from .cluster import ensure_running

DEFAULT_DATA_DIR: Path = Path(__file__).resolve().parents[2] / "pgdata"


def main() -> int:
    command: str = sys.argv[1] if len(sys.argv) == 2 else ""
    data_dir: Path = Path(os.environ.get("OX_PG_DATA_DIR", str(DEFAULT_DATA_DIR)))
    layout = layout_for(data_dir)
    database: str = os.environ.get("OX_PG_DATABASE", "ox")
    try:
        if command == "start":
            binaries = ensure_running(layout, database)
            print("running: PostgreSQL", binaries.major, "at", layout.socket_dir)
        elif command == "stop":
            stop(layout)
            print("stopped")
        elif command == "status":
            binaries = find_binaries()
            state: str = (
                "running"
                if (layout.data_dir / "PG_VERSION").is_file()
                and is_running(layout, binaries)
                else "stopped"
            )
            print(state + ": PostgreSQL", binaries.major, "from", binaries.bin_dir)
        elif command == "where":
            print("data:", layout.data_dir)
            print("socket:", layout.socket_dir)
            print("log:", layout.log_file)
        else:
            print(__doc__.strip())
            return 2
    except ClusterError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
