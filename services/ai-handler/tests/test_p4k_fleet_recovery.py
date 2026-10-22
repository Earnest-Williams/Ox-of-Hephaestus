"""Fast contract checks for the P4k forty-session recovery roster."""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from ox_ai.runtime.fleet_recovery import (
    FLEET_COUNT, FLEET_ROLES, validated_fleet_roster,
)


def roster():
    return {
        role: {
            "username": "OxFleet" + role[-2:],
            "character_dbref": f"#{2000+i}",
            "name": f"Fleet Recovery Crew {i:02d}",
            "duty": "Inspect assigned station without inventing world authority",
        }
        for i, role in enumerate(FLEET_ROLES)
    }


class FleetRosterContractTests(unittest.TestCase):
    def test_exact_forty_body_and_account_boundary(self):
        members = validated_fleet_roster(roster())
        self.assertEqual(len(members), FLEET_COUNT)
        self.assertEqual(len({x["character_dbref"] for x in members.values()}), 40)
        self.assertEqual(len({x["username"] for x in members.values()}), 40)

    def test_reject_missing_fleet_member_and_foreign_slot(self):
        members = roster()
        del members["fleet39"]
        with self.assertRaises(ValueError):
            validated_fleet_roster(members)
        members["fleetXX"] = members["fleet38"]
        with self.assertRaises(ValueError):
            validated_fleet_roster(members)

    def test_reject_identity_swaps_or_multiple_accounts_for_same_body(self):
        members = roster()
        members["fleet07"]["character_dbref"] = members["fleet08"]["character_dbref"]
        with self.assertRaises(PermissionError):
            validated_fleet_roster(members)
        members = roster()
        members["fleet09"]["username"] = members["fleet10"]["username"]
        with self.assertRaises(PermissionError):
            validated_fleet_roster(members)
        members = roster()
        members["fleet03"]["name"] = members["fleet02"]["name"]
        with self.assertRaises(PermissionError):
            validated_fleet_roster(members)

    def test_reject_untyped_or_extra_roster_fields(self):
        members = roster()
        members["fleet01"]["character_dbref"] = 400
        with self.assertRaises(ValueError):
            validated_fleet_roster(members)
        members = roster()
        members["fleet00"]["privileged"] = True
        with self.assertRaises(ValueError):
            validated_fleet_roster(members)


if __name__ == "__main__":
    unittest.main()
