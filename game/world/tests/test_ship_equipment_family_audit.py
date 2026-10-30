"""Audit the original 808 installed equipment identities, all 91 kinds."""
import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from world.ship_equipment_family_audit import (
    audit_fitted_equipment, EquipmentFamilyAuditError,
    DISPOSITIONS, FANCOILS,
)


CANDIDATE = Path(__file__).resolve().parents[3] / (
    "design/ship/ox_full_ship_v0.5_candidate.json")


def reference():
    return json.loads(CANDIDATE.read_text(encoding="utf-8"))


class CompleteOriginalEquipmentAuditTests(unittest.TestCase):
    def test_all_families_present_and_no_hidden_unreviewed_kind(self):
        report = audit_fitted_equipment(reference())
        self.assertEqual((report["equipment"],report["families"]),(808,91))
        self.assertEqual(report["dispositions"], {
            "direct_physics": {"equipment": 349, "families": 37},
            "interface_or_custody": {"equipment": 159, "families": 26},
            "controlled_hardware": {"equipment": 300, "families": 28},
            "open_interaction": {"equipment": 0, "families": 0},
        })
        self.assertEqual(sum(
            row["count"] for row in report["by_kind"].values()), 808)
        self.assertEqual(set(report["by_kind"]),set.union(
            *(set(k) for k in DISPOSITIONS.values())))
        for kind,record in report["by_kind"].items():
            self.assertEqual(record["count"],len(record["ids"]))
            self.assertEqual(len(record["ids"]),len(set(record["ids"])))

    def test_open_portable_and_independent_packages_are_explicit(self):
        report=audit_fitted_equipment(reference())
        open_by_kind=Counter(row["kind"] for row in report["open_items"])
        self.assertEqual(dict(open_by_kind),{})
        self.assertEqual(report["open_items"],[])
        for name in ("EVA-CRAWLER-1","EVA-CRAWLER-2",
                     "DRUM-INSPECT-ROBOT-1","DRUM-INSPECT-ROBOT-2"):
            self.assertIn(name,report["by_kind"][
                "inspection_robot" if name.startswith("DRUM-INSPECT")
                else "eva_rail_crawler"]["ids"])
        self.assertEqual(report["by_kind"]["fan_coil"]["count"],40)
        self.assertEqual(report["by_kind"]["fan_coil"][
            "disposition"],"direct_physics")
        self.assertEqual(set(report["by_kind"]["fan_coil"]["ids"]),set(FANCOILS))
        self.assertEqual(report["by_kind"][
            "survival_craft_life_support"]["disposition"],"direct_physics")
        self.assertEqual(report["by_kind"][
            "survival_craft_life_support"]["count"],2)

    def test_unreviewed_kind_duplicate_and_uninstalled_room_refused(self):
        original=reference()
        changed=copy.deepcopy(original)
        changed["equipment"][0]["kind"]="hypothetical_teleporter"
        with self.assertRaises(EquipmentFamilyAuditError):
            audit_fitted_equipment(changed)
        changed=copy.deepcopy(original)
        changed["equipment"][0]["id"]=changed["equipment"][1]["id"]
        with self.assertRaises(EquipmentFamilyAuditError):
            audit_fitted_equipment(changed)
        changed=copy.deepcopy(original)
        changed["equipment"][0]["space_id"]="NONEXISTENT-BRIDGE"
        with self.assertRaises(EquipmentFamilyAuditError):
            audit_fitted_equipment(changed)

    def test_direct_source_id_must_remain_in_original_live_family(self):
        changed=reference()
        target=next(x for x in changed["equipment"]
                    if x["id"]=="HAB-01-CAB-01-FANCOIL")
        target["kind"]="cabin_panel"
        with self.assertRaises(EquipmentFamilyAuditError):
            audit_fitted_equipment(changed)


if __name__=="__main__":
    unittest.main()
