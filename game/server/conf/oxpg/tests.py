"""Game-managed PostgreSQL launcher tests (ADR 0010).

From game/:  python -m unittest server.conf.oxpg.tests -v

Pure tests use fake ``pg_ctl``/``initdb`` scripts. The live test runs only
when real PostgreSQL programs exist and the user is not root.
"""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from . import cluster


def _fake_bin(root: Path, version_line: str) -> Path:
    bin_dir: Path = root / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("pg_ctl", "initdb"):
        tool: Path = bin_dir / name
        tool.write_text("#!/bin/sh\necho '" + version_line + "'\n", encoding="utf-8")
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return bin_dir


class LayoutTests(unittest.TestCase):
    def test_socket_sits_beside_data_when_short(self) -> None:
        layout: cluster.Layout = cluster.layout_for(Path("/srv/ox/game/server/pgdata"))
        self.assertEqual(layout.socket_dir, Path("/srv/ox/game/server/pgdata.sock"))
        self.assertEqual(layout.log_file.name, "pgdata.log")

    def test_long_paths_fall_back_to_a_stable_short_socket(self) -> None:
        deep: Path = Path("/") / ("d" * 120) / "pgdata"
        first: cluster.Layout = cluster.layout_for(deep)
        second: cluster.Layout = cluster.layout_for(deep)
        self.assertEqual(first.socket_dir, second.socket_dir)
        self.assertTrue(first.socket_dir.name.startswith("ox-pg-"))
        limit: int = cluster.MAX_SOCKET_DIR_BYTES
        self.assertLessEqual(len(os.fsencode(first.socket_dir)), limit)


class BinaryDiscoveryTests(unittest.TestCase):
    def test_version_is_read_from_pg_ctl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            line: str = "pg_ctl (PostgreSQL) 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)"
            bin_dir: Path = _fake_bin(Path(tmp), line)
            found: cluster.Binaries = cluster.find_binaries({"OX_PG_BIN": str(bin_dir)})
            self.assertEqual(found, cluster.Binaries(bin_dir, 16))

    def test_explicit_folder_without_programs_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(cluster.ClusterError):
                cluster.find_binaries({"OX_PG_BIN": tmp})

    def test_unparseable_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir: Path = _fake_bin(Path(tmp), "pg_ctl something else")
            with self.assertRaises(cluster.ClusterError):
                cluster.find_binaries({"OX_PG_BIN": str(bin_dir)})


class VersionGuardTests(unittest.TestCase):
    def test_folder_from_another_major_refuses_to_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root: Path = Path(tmp)
            bin_dir: Path = _fake_bin(root, "pg_ctl (PostgreSQL) 18.6")
            data: Path = root / "pgdata"
            data.mkdir()
            (data / "PG_VERSION").write_text("16\n", encoding="utf-8")
            layout: cluster.Layout = cluster.layout_for(data)
            previous: str | None = os.environ.get("OX_PG_BIN")
            os.environ["OX_PG_BIN"] = str(bin_dir)
            try:
                with self.assertRaisesRegex(cluster.ClusterError, "PostgreSQL 16"):
                    cluster.ensure_running(layout, "ox")
            finally:
                if previous is None:
                    del os.environ["OX_PG_BIN"]
                else:
                    os.environ["OX_PG_BIN"] = previous

    def test_stop_without_a_cluster_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cluster.stop(cluster.layout_for(Path(tmp) / "pgdata"))


def _real_binaries() -> cluster.Binaries | None:
    if os.geteuid() == 0:
        return None
    try:
        return cluster.find_binaries()
    except cluster.ClusterError:
        return None


@unittest.skipIf(_real_binaries() is None, "needs PostgreSQL programs, non-root")
class LiveClusterTests(unittest.TestCase):
    def test_initialise_start_reuse_stop_restart(self) -> None:
        import psycopg

        with tempfile.TemporaryDirectory() as tmp:
            layout: cluster.Layout = cluster.layout_for(Path(tmp) / "pgdata")
            binaries: cluster.Binaries = cluster.ensure_running(layout, "ox")
            try:
                self.assertTrue(cluster.is_running(layout, binaries))
                cluster.ensure_running(layout, "ox")  # idempotent
                with psycopg.connect(
                    host=str(layout.socket_dir), user=cluster.ROLE, dbname="ox"
                ) as conn:
                    row: object = conn.execute(
                        "SELECT current_setting('listen_addresses'),"
                        " current_setting('wal_level')"
                    ).fetchone()
                self.assertEqual(row, ("", "minimal"))
                cluster.stop(layout)
                self.assertFalse(cluster.is_running(layout, binaries))
                cluster.ensure_running(layout, "ox_second")
                with psycopg.connect(
                    host=str(layout.socket_dir), user=cluster.ROLE, dbname="ox"
                ) as conn:
                    names: list[tuple[str]] = conn.execute(
                        "SELECT datname FROM pg_database ORDER BY datname"
                    ).fetchall()
                self.assertIn(("ox_second",), names)
            finally:
                cluster.stop(layout)


if __name__ == "__main__":
    unittest.main()
