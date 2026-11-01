"""Game-managed private PostgreSQL cluster (ADR 0010).

The game owns one PostgreSQL cluster inside its own folder. Nothing listens on
a network port: clients use a Unix socket next to the data, with password-free
local authentication, so only the owning OS user can connect. The player never
installs a service, creates a role or edits a config file.

Lifecycle:

- ``ensure_running()`` initialises the folder on first use, starts the server
  if needed and creates the requested database. It is safe to call from the
  launcher, Portal, Server, test runner and probes at once: a file lock
  serialises them.
- ``stop()`` is called from Evennia's cold-stop hook. A ``reload`` leaves the
  database running.

Binaries come from, in order: ``OX_PG_BIN``; the system (PATH, then Debian and
PGDG install folders, highest major first); the optional ``embedded-postgres``
wheel. A data folder only opens under the major version that created it.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROLE: Final[str] = "ox"
PORT: Final[int] = 5432
# sun_path is 108 bytes on Linux; leave room for "/.s.PGSQL.5432" and NUL.
MAX_SOCKET_DIR_BYTES: Final[int] = 90
START_TIMEOUT_S: Final[int] = 60
# Single-player tuning. wal_level=minimal needs max_wal_senders=0: there are
# no replicas. Connections cover Evennia's reactor, its web thread pool (up
# to 20) and the test runner's maintenance connections.
SERVER_SETTINGS: Final[Mapping[str, str]] = {
    "listen_addresses": "''",
    "max_connections": "40",
    "shared_buffers": "16MB",
    "wal_level": "minimal",
    "max_wal_senders": "0",
    "log_destination": "'stderr'",
}
SETTINGS_MARKER: Final[str] = "# --- Ox game-managed settings (ADR 0010) ---"
DISTRO_FOLDERS: Final[tuple[tuple[Path, str], ...]] = (
    (Path("/usr/lib/postgresql"), "*/bin"),  # Debian/Ubuntu, GitHub runners
    (Path("/usr"), "pgsql-*/bin"),  # PGDG RPMs
)


class ClusterError(RuntimeError):
    """The private database cannot be found, created or started."""


@dataclass(frozen=True, slots=True)
class Layout:
    data_dir: Path
    socket_dir: Path
    log_file: Path
    lock_file: Path


@dataclass(frozen=True, slots=True)
class Binaries:
    bin_dir: Path
    major: int

    def tool(self, name: str) -> str:
        return str(self.bin_dir / name)


def layout_for(data_dir: Path) -> Layout:
    """Pure path arithmetic; settings call this without starting anything."""
    data: Path = data_dir.resolve()
    socket_dir: Path = data.parent / (data.name + ".sock")
    if len(os.fsencode(socket_dir)) > MAX_SOCKET_DIR_BYTES:
        digest: str = hashlib.sha256(os.fsencode(data)).hexdigest()[:12]
        socket_dir = Path(tempfile.gettempdir()) / ("ox-pg-" + digest)
    return Layout(
        data_dir=data,
        socket_dir=socket_dir,
        log_file=data.parent / (data.name + ".log"),
        lock_file=data.parent / (data.name + ".lock"),
    )


def _major_of(bin_dir: Path) -> int | None:
    pg_ctl: Path = bin_dir / "pg_ctl"
    if not (pg_ctl.is_file() and (bin_dir / "initdb").is_file()):
        return None
    try:
        reply: str = subprocess.run(
            [str(pg_ctl), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    # "pg_ctl (PostgreSQL) 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)"
    words: list[str] = reply.split()
    if "(PostgreSQL)" not in words:
        return None
    position: int = words.index("(PostgreSQL)") + 1
    if position >= len(words):
        return None
    head: str = words[position].split(".")[0]
    return int(head) if head.isdigit() else None


def _system_candidates() -> Iterator[Path]:
    on_path: str | None = shutil.which("pg_ctl")
    if on_path is not None:
        yield Path(on_path).resolve().parent
    for root, pattern in DISTRO_FOLDERS:
        if root.is_dir():
            yield from root.glob(pattern)


def _wheel_candidate() -> Path | None:
    try:
        import embedded_postgres  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return None
    # Run in place: the wheel's binaries find their libraries by a path
    # relative to the installed package, so they must never be copied.
    package: Path = Path(str(embedded_postgres.__file__)).parent
    bin_dir: Path = package / "pginstall" / "bin"
    return bin_dir if bin_dir.is_dir() else None


def find_binaries(env: Mapping[str, str] | None = None) -> Binaries:
    environment: Mapping[str, str] = os.environ if env is None else env
    explicit: str | None = environment.get("OX_PG_BIN")
    if explicit:
        major: int | None = _major_of(Path(explicit))
        if major is None:
            raise ClusterError("OX_PG_BIN has no initdb/pg_ctl: " + explicit)
        return Binaries(Path(explicit), major)
    found: list[Binaries] = []
    for candidate in _system_candidates():
        candidate_major: int | None = _major_of(candidate)
        if candidate_major is not None:
            found.append(Binaries(candidate, candidate_major))
    if found:
        return max(found, key=lambda b: b.major)
    wheel: Path | None = _wheel_candidate()
    if wheel is not None:
        wheel_major: int | None = _major_of(wheel)
        if wheel_major is not None:
            return Binaries(wheel, wheel_major)
    raise ClusterError(
        "PostgreSQL programs not found. Install them once: "
        "Fedora `sudo dnf install postgresql-server`, Ubuntu "
        "`sudo apt install postgresql`, or `pip install embedded-postgres`. "
        "No service needs enabling."
    )


@contextmanager
def _locked(layout: Layout) -> Iterator[None]:
    layout.lock_file.parent.mkdir(parents=True, exist_ok=True)
    with layout.lock_file.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _run(command: list[str], what: str, layout: Layout) -> None:
    result: subprocess.CompletedProcess[str] = subprocess.run(
        command, capture_output=True, text=True, timeout=START_TIMEOUT_S + 30
    )
    if result.returncode != 0:
        detail: str = (result.stderr or result.stdout).strip()
        raise ClusterError(
            what + " failed: " + detail + "\nLog: " + str(layout.log_file)
        )


def _initialise(layout: Layout, binaries: Binaries) -> None:
    if os.geteuid() == 0:
        raise ClusterError("PostgreSQL refuses to run as root; start Ox as a user")
    layout.data_dir.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            binaries.tool("initdb"),
            "--pgdata",
            str(layout.data_dir),
            "--username",
            ROLE,
            "--auth",
            "trust",
            "--encoding",
            "UTF8",
            "--no-locale",
            "--no-instructions",
        ],
        "initdb",
        layout,
    )
    lines: list[str] = ["", SETTINGS_MARKER]
    lines.extend(name + " = " + value for name, value in SERVER_SETTINGS.items())
    with (layout.data_dir / "postgresql.conf").open("a", encoding="utf-8") as conf:
        conf.write("\n".join(lines) + "\n")


def _data_major(layout: Layout) -> int:
    text: str = (layout.data_dir / "PG_VERSION").read_text(encoding="utf-8")
    return int(text.strip())


def is_running(layout: Layout, binaries: Binaries) -> bool:
    status: subprocess.CompletedProcess[str] = subprocess.run(
        [binaries.tool("pg_ctl"), "status", "--pgdata", str(layout.data_dir)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return status.returncode == 0


def _start(layout: Layout, binaries: Binaries) -> None:
    layout.socket_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # The socket folder is passed per start, so a moved checkout still works.
    options: str = "-k " + shlex.quote(str(layout.socket_dir))
    _run(
        [
            binaries.tool("pg_ctl"),
            "start",
            "--pgdata",
            str(layout.data_dir),
            "--log",
            str(layout.log_file),
            "--wait",
            "--timeout",
            str(START_TIMEOUT_S),
            "--options",
            options,
        ],
        "pg_ctl start",
        layout,
    )


def _ensure_database(layout: Layout, name: str) -> None:
    import psycopg
    from psycopg import sql

    with psycopg.connect(
        host=str(layout.socket_dir),
        port=PORT,
        user=ROLE,
        dbname="postgres",
        autocommit=True,
    ) as conn:
        row: object = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if row is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def ensure_running(layout: Layout, database: str) -> Binaries:
    """Initialise, start and create ``database`` as needed. Idempotent."""
    binaries: Binaries = find_binaries()
    with _locked(layout):
        if not (layout.data_dir / "PG_VERSION").is_file():
            _initialise(layout, binaries)
        data_major: int = _data_major(layout)
        if data_major != binaries.major:
            raise ClusterError(
                "Ship database was created by PostgreSQL "
                + str(data_major)
                + " but PostgreSQL "
                + str(binaries.major)
                + " is installed. Export with the old version's pg_dump and "
                "import into a fresh folder, or set OX_PG_BIN to the old "
                "version: " + str(layout.data_dir)
            )
        if not is_running(layout, binaries):
            _start(layout, binaries)
        _ensure_database(layout, database)
    return binaries


def stop(layout: Layout) -> None:
    """Fast shutdown if running; a missing folder or program is not an error."""
    if not (layout.data_dir / "PG_VERSION").is_file():
        return
    try:
        binaries: Binaries = find_binaries()
    except ClusterError:
        return
    with _locked(layout):
        if is_running(layout, binaries):
            _run(
                [
                    binaries.tool("pg_ctl"),
                    "stop",
                    "--pgdata",
                    str(layout.data_dir),
                    "--mode",
                    "fast",
                    "--wait",
                ],
                "pg_ctl stop",
                layout,
            )
