"""The 91-family physical inventory exists in Evennia, not just JSON."""
from evennia.utils.test_resources import EvenniaTestCase

from world.full_ship_operations import (
    install_candidate, load_candidate, state, set_component_condition,
)
from world.ship_world import build_canonical_ship
from world.models import CanonicalShipState
from world.ship_equipment_family_audit import audit_fitted_equipment


class InstalledEquipmentFamilyClosure(EvenniaTestCase):
    def test_all_eight_hundred_and_eight_original_units_installed_at_actual_sites(self):
        build_canonical_ship()
        install_candidate(operator_approved=True)
        source=load_candidate()
        audit=audit_fitted_equipment(source)
        reference={item["id"]:item for item in source["equipment"]}
        fitted={
            row.source_id:row for row in
            CanonicalShipState.objects.filter(category="equipment")
        }
        self.assertEqual(len(fitted),808)
        self.assertEqual(set(fitted),set(reference))
        self.assertEqual(len(audit["by_kind"]),91)
        for name,row in fitted.items():
            original=reference[name]
            self.assertEqual(row.key,"equipment:"+name)
            self.assertEqual(row.space_id,original["space_id"])
            self.assertEqual(row.reference["kind"],original["kind"])
            self.assertEqual(row.reference["id"],name)
            self.assertEqual(row.source_model,"0.5-candidate")
        # Rebuilding never silently relocates or repairs a failed system.
        set_component_condition(
            "equipment","HAB-01-CAB-01-FANCOIL","failed",operator=True)
        self.assertFalse(install_candidate(operator_approved=True)["installed"])
        self.assertEqual(state("equipment","HAB-01-CAB-01-FANCOIL").condition,
                         "failed")
        self.assertEqual(
            state("equipment","HAB-01-CAB-01-FANCOIL").space_id,
            "HAB-01-CAB-01")
