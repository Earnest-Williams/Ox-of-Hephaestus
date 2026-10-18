"""Persistent autonomous crew bodies do not vanish on client disconnect."""
from __future__ import annotations

from unittest.mock import Mock

from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship


class CrewPresenceTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()

    def test_unpuppet_keeps_physical_crew_at_actual_location(self):
        ari = self.ship["watch"]
        self.assertTrue(ari.move_to(self.ship["mess"], quiet=True))
        ari.at_post_unpuppet(account=None, session=None)
        self.assertEqual(ari.location, self.ship["mess"])
        self.assertEqual(ari.db.prelogout_location, self.ship["mess"])
        # Repuppet does not replace current position with original home.
        ari.at_pre_puppet(Mock(), session=None)
        self.assertEqual(ari.location, self.ship["mess"])
        self.assertEqual(ari.home, self.ship["engineering"])
        self.assertNotEqual(ari.location, ari.home)

    def test_unpuppet_preserves_persons_in_separate_departments(self):
        mara = self.ship["cargo"]
        teo = self.ship["environment"]
        mara.at_post_unpuppet()
        teo.at_post_unpuppet()
        self.assertEqual(mara.location, self.ship["cargo_hold"])
        self.assertEqual(teo.location, self.ship["environmental"])
        self.assertNotEqual(mara.location, teo.location)


if __name__ == "__main__":
    import unittest
    unittest.main()
