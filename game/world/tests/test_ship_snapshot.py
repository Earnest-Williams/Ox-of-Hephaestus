"""Pure tests for the prebuilt-ship fingerprint (no database)."""

from __future__ import annotations

import unittest

from world import ship_snapshot


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_short(self) -> None:
        first: str = ship_snapshot.fingerprint()
        self.assertEqual(first, ship_snapshot.fingerprint())
        self.assertEqual(len(first), 16)
        self.assertTrue(set(first) <= set("0123456789abcdef"), first)

    def test_template_name_fits_postgres_identifier_limit(self) -> None:
        name: str = ship_snapshot.template_name("0" * 16)
        building: str = name + ship_snapshot.BUILDING_SUFFIX
        self.assertTrue(name.startswith(ship_snapshot.PREFIX))
        self.assertLessEqual(len(building.encode()), 63)

    def test_design_inputs_exist(self) -> None:
        for path in ship_snapshot._design_paths():
            self.assertTrue(path.is_file(), path)

    def test_build_refuses_any_other_database(self) -> None:
        import os

        previous: str | None = os.environ.get("OX_PG_DATABASE")
        os.environ["OX_PG_DATABASE"] = "ox"
        try:
            with self.assertRaises(SystemExit):
                ship_snapshot._build()
        finally:
            if previous is None:
                del os.environ["OX_PG_DATABASE"]
            else:
                os.environ["OX_PG_DATABASE"] = previous
