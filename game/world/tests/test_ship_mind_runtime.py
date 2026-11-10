"""G19 lead-mind world extension: measured draw, contacts and failover."""
from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace as Row

from world.ship_mind_power import (
    MindPowerError,
    default_design_path,
    load_design,
    proposed_world_rows,
    survey_reserve,
)
from world.ship_mind_runtime import (
    initial_mind_runtime,
    tick_mind_power,
    validate_mind_runtime,
)
from world.ship_mind_service import SERVICE_KEY, changed_service

def prepared():
    design = load_design()
    ship = json.loads(default_design_path().with_name(
        "ox_full_ship_v0.5_candidate.json").read_text(encoding="utf-8"))
    rows = {key: Row(**value) for key, value in proposed_world_rows(design).items()}
    for section, cat in (("service_nodes", "node"), ("service_edges", "edge"),
                         ("isolation_points", "isolator")):
        for value in ship[section]:
            if value.get("network") != "power":
                continue
            item = dict(key=cat + ":" + value["id"], category=cat,
                        source_id=value["id"], source_model="0.5-candidate",
                        reference=value, condition=value.get("current_condition",
                                                              "serviceable"),
                        setting=value.get("current_state", value.get("normal_state",
                                                                      "unverified")))
            rows[item["key"]] = Row(**item)
    for value in ship["equipment"]:
        item = dict(key="equipment:" + value["id"], category="equipment",
                    source_id=value["id"], source_model="0.5-candidate",
                    reference=value, condition=value.get("current_condition",
                                                          "serviceable"),
                    setting="unverified")
        rows[item["key"]] = Row(**item)
    taps = set()
    # Real original contacts must be separately energised by a qualified
    # operator; the proposed island fitter cannot close them.
    for island in design["islands"]:
        for feed in island["inputs"]:
            taps.add(feed["tap_node"])
            for name in feed["route_domains"]:
                if name.startswith("ISO-"):
                    rows["isolator:" + name].setting = "closed"
    g19 = {"nodes": {"PWR-MSB-A", "PWR-MSB-B"} | taps,
           "main_available_mw": 3.0, "producer_available_mw": 3.0,
           "requested_mw": 1.35}
    return design, rows, g19


def apply(rows, transfers):
    for old, new in transfers:
        assert rows["edge:" + old].setting == "available"
        assert rows["edge:" + new].setting == "standby"
        rows["edge:" + old].setting = "standby"
        rows["edge:" + new].setting = "available"


class MindRuntimePhysicsTests(unittest.TestCase):
    def setUp(self):
        self.design, self.rows, self.g19 = prepared()
        self.account = initial_mind_runtime(self.design)

    def step(self, seconds=10):
        self.account, contacts = tick_mind_power(
            self.design, self.account, rows=self.rows, g19_power=self.g19,
            seconds=seconds)
        apply(self.rows, contacts)
        return self.account["last"], contacts

    def test_cooling_auxiliaries_are_billed_without_admitting_compute(self):
        """A tripped processor's 50 W service supply uses its actual final feeder."""
        row = self.rows["equipment:MIND-01"]
        row.revision = 1
        row.condition = "faulted"
        record = changed_service(row, "cooldown")
        row.revision = record["row_revision"]
        row.details = {
            SERVICE_KEY: record,
            "physics_mind_thermal_trip": True,
            "physics_mind_trip_revision": row.revision,
        }
        last, _ = self.step()
        self.assertNotIn("MIND-01", last["powered"])
        self.assertEqual(last["cooling_only"], ["MIND-01"])
        self.assertAlmostEqual(last["delivered_heat_kj"]["MIND-01"], 0.5)
        self.assertAlmostEqual(last["grid_served_mw"], 0.01605)
        machine = self.design["islands"][0]["machines"][0]
        self.rows["isolator:" + machine["isolator"]].setting = "open"
        last, _ = self.step()
        self.assertEqual(last["cooling_only"], [])
        self.assertEqual(last["delivered_heat_kj"]["MIND-01"], 0)
        self.rows["isolator:" + machine["isolator"]].setting = "closed"
        row.revision += 1
        last, _ = self.step()
        self.assertEqual(last["cooling_only"], [])

    def test_thermal_latch_survives_a_generic_condition_change(self):
        """A normal condition flag alone cannot bypass a retained thermal latch."""
        row = self.rows["equipment:MIND-01"]
        row.details = {"physics_mind_thermal_trip": True}
        last, _ = self.step()
        self.assertNotIn("MIND-01", last["powered"])
        self.assertEqual(last["delivered_heat_kj"]["MIND-01"], 0)

    def test_unfitted_thermal_protection_interlocks_all_compute_loads(self):
        """Fitting a power circuit cannot start computers before protection exists."""
        account, _ = tick_mind_power(
            self.design,
            self.account,
            rows=self.rows,
            g19_power=self.g19,
            seconds=10,
            loads_enabled=False,
        )
        self.assertEqual(account["last"]["powered"], [])
        self.assertEqual(account["meter"]["grid_served_kwh"], 0)
        self.assertEqual(account["meter"]["reserve_served_kwh"], 0)
        self.assertEqual(sum(account["last"]["delivered_heat_kj"].values()), 0)

    def test_last_fractional_reserve_delivery_retains_every_joule_as_heat(self):
        """The final 0.005 kWh becomes 18 kJ despite loss of full-tick service."""
        bank = self.design["islands"][0]["local_reserve"]["id"]
        self.account["reserve"] = survey_reserve(
            self.design, self.account["reserve"], bank, capacity_kwh=0.5, charge_kwh=0.005
        )
        self.g19["nodes"].clear()
        last, _ = self.step()
        self.assertEqual(last["powered"], [])
        self.assertAlmostEqual(self.account["meter"]["reserve_served_kwh"], 0.005)
        self.assertAlmostEqual(sum(last["delivered_heat_kj"].values()), 18)
        self.assertEqual(last["delivered_heat_kj"]["MIND-01"], 9)
        self.assertEqual(last["delivered_heat_kj"]["MIND-02"], 9)
        last, _ = self.step()
        self.assertEqual(sum(last["delivered_heat_kj"].values()), 0)

    def test_nine_physical_compute_loads_are_billed_once(self):
        last, changed = self.step()
        self.assertEqual(last["powered"], [f"MIND-{n:02d}" for n in range(1, 10)])
        self.assertEqual(changed, ())
        self.assertAlmostEqual(last["grid_served_mw"], .018)
        self.assertEqual(last["grid_charge_mw"], 0)
        self.assertAlmostEqual(self.account["meter"]["grid_served_kwh"], .05)
        self.assertTrue(validate_mind_runtime(self.design, self.account))

    def test_power_has_no_unmeasured_emergency_reserve(self):
        self.g19["nodes"].clear()
        last, _ = self.step()
        self.assertEqual(last["powered"], [])
        self.assertEqual(len(last["unpowered"]), 9)
        self.assertEqual(self.account["meter"]["reserve_served_kwh"], 0)
        self.assertAlmostEqual(self.account["meter"]["unserved_kwh"], .05)

    def test_local_island_transfer_delayed_with_real_separate_contacts(self):
        island = self.design["islands"][0]
        primary = island["inputs"][0]
        self.rows["isolator:" + primary["breaker"]].setting = "open"
        # With measured energy to bridge source transfer, both machines stay
        # powered; the world does not parallel A and B or reclose A.
        self.account["reserve"] = survey_reserve(
            self.design, self.account["reserve"], island["local_reserve"]["id"],
            capacity_kwh=.5, charge_kwh=.5)
        first, contacts = self.step()
        self.assertEqual(contacts, ())
        self.assertEqual(len(first["powered"]), 9)
        self.assertIn(island["id"], self.account["pending"])
        self.assertEqual(self.rows["edge:" + primary["edge"]].setting, "available")
        second, contacts = self.step()
        self.assertEqual(contacts, ((primary["edge"], island["inputs"][1]["edge"]),))
        self.assertEqual(len(second["powered"]), 9)
        self.assertEqual(self.rows["edge:" + primary["edge"]].setting, "standby")
        self.assertEqual(self.rows["edge:" + island["inputs"][1]["edge"]].setting,
                         "available")
        third, contacts = self.step()
        self.assertEqual(contacts, ())
        self.assertEqual(len(third["powered"]), 9)
        self.assertEqual(self.rows["isolator:" + primary["breaker"]].setting, "open")
        self.assertAlmostEqual(self.account["meter"]["reserve_served_kwh"],
                               4 * 20 / 3600)

    def test_failed_main_a_triggers_b_source_transfer_in_all_five_islands(self):
        self.g19["nodes"] = {x for x in self.g19["nodes"]
                             if not x.endswith("A") and not x.startswith("NODE-DB-A")}
        for island in self.design["islands"]:
            self.account["reserve"] = survey_reserve(
                self.design, self.account["reserve"], island["local_reserve"]["id"],
                capacity_kwh=.5, charge_kwh=.5)
        first, contacts = self.step()
        self.assertEqual(len(first["powered"]), 9)
        self.assertEqual(contacts, ())
        second, contacts = self.step()
        self.assertEqual(len(contacts), 5)
        self.assertEqual(len(second["powered"]), 9)
        third, _ = self.step()
        self.assertEqual(len(third["powered"]), 9)

    def test_no_free_charge_and_surveyed_charger_draw_is_explicit(self):
        self.step()
        self.assertEqual(self.account["meter"]["grid_charge_kwh"], 0)
        for island in self.design["islands"]:
            reserve = island["local_reserve"]
            self.account["reserve"] = survey_reserve(
                self.design, self.account["reserve"], reserve["id"],
                capacity_kwh=.5, charge_kwh=0)
        last, _ = self.step()
        self.assertAlmostEqual(last["grid_served_mw"], .018)
        self.assertAlmostEqual(last["grid_charge_mw"], .010)
        self.assertAlmostEqual(self.account["meter"]["grid_charge_kwh"],
                               10 * 10 / 3600)
        self.assertTrue(validate_mind_runtime(self.design, self.account))
        # A disconnected charger cannot draw or inject power.
        charger = "ISO-CHARGE-" + self.design["islands"][0]["local_reserve"]["id"]
        self.rows["isolator:" + charger].setting = "open"
        last, _ = self.step()
        self.assertAlmostEqual(last["grid_charge_mw"], .008)

    def test_failed_primary_without_transfer_reserve_halts_only_its_island(self):
        island = self.design["islands"][2]
        self.rows["isolator:" + island["inputs"][0]["breaker"]].setting = "open"
        self.rows["isolator:" + island["inputs"][1]["breaker"]].setting = "open"
        last, contacts = self.step()
        self.assertEqual(contacts, ())
        self.assertEqual(len(last["powered"]), 7)
        self.assertEqual(len(last["unpowered"]), 2)
        self.assertNotIn(island["id"], self.account["pending"])

    def test_source_path_breaker_and_local_final_breaker_are_real(self):
        island = self.design["islands"][0]
        final = island["machines"][0]
        self.rows["isolator:" + final["isolator"]].setting = "open"
        result, _ = self.step()
        self.assertEqual(len(result["powered"]), 8)
        self.assertNotIn(final["id"], result["powered"])
        self.rows["isolator:" + final["isolator"]].setting = "closed"
        self.rows["equipment:" + island["converter"]].condition = "failed"
        result, _ = self.step()
        self.assertEqual(len(result["powered"]), 7)

    def test_every_new_fitted_hardware_failure_keeps_seven_on_measured_backup(self):
        # Sweep the *runtime* identity set, not only the candidate domain
        # names. Charge is explicit and private to each of five islands.
        surveyed = initial_mind_runtime(self.design)
        for island in self.design["islands"]:
            reserve = island["local_reserve"]
            surveyed["reserve"] = survey_reserve(
                self.design, surveyed["reserve"], reserve["id"],
                capacity_kwh=.5, charge_kwh=.5)
        for key in sorted(proposed_world_rows(self.design)):
            with self.subTest(failed=key):
                rows = dict(self.rows)
                row = copy.copy(rows[key])
                row.condition = "failed"
                rows[key] = row
                account, _ = tick_mind_power(
                    self.design, surveyed, rows=rows,
                    g19_power=self.g19, seconds=10)
                self.assertGreaterEqual(len(account["last"]["powered"]), 7)

    def test_failed_battery_terminal_cannot_supply_or_accept_charge(self):
        island = self.design["islands"][0]
        reserve = island["local_reserve"]
        self.account["reserve"] = survey_reserve(
            self.design, self.account["reserve"], reserve["id"],
            capacity_kwh=.5, charge_kwh=.25)
        self.rows["node:NODE-" + reserve["id"]].condition = "failed"
        self.g19["nodes"].clear()
        last, _ = self.step()
        self.assertNotIn(island["machines"][0]["id"], last["powered"])
        self.assertNotIn(island["machines"][1]["id"], last["powered"])
        self.assertEqual(self.account["meter"]["reserve_served_kwh"], 0)
        self.g19["nodes"] = prepared()[2]["nodes"]
        last, _ = self.step()
        self.assertEqual(last["grid_charge_mw"], 0)

    def test_latched_original_g19_contact_is_not_healthy_closed_power(self):
        island = self.design["islands"][0]
        feed = island["inputs"][0]
        original = next(x for x in feed["route_domains"] if x.startswith("ISO-"))
        contact = self.rows["isolator:" + original]
        self.assertEqual(contact.setting, "closed")
        contact.details = {"physics_power_trip_latched": True}
        last, _ = self.step()
        self.assertEqual(len(last["powered"]), 7)
        self.assertIn(island["id"], self.account["pending"])

    def test_grid_shortfall_never_credits_more_power_to_mind(self):
        self.g19["main_available_mw"] = 1.35
        last, _ = self.step()
        self.assertEqual(last["powered"], [])
        self.assertEqual(last["grid_served_mw"], 0)
        self.assertEqual(self.account["meter"]["grid_served_kwh"], 0)
        self.assertTrue(validate_mind_runtime(self.design, self.account))

    def test_damaged_source_and_stolen_runtime_row_fail_closed(self):
        rows = dict(self.rows)
        del rows["node:" + self.design["islands"][0]["distribution_node"]]
        with self.assertRaises(MindPowerError):
            tick_mind_power(self.design, self.account, rows=rows,
                            g19_power=self.g19, seconds=10)
        broken = copy.deepcopy(self.account)
        broken["meter"]["reserve_served_kwh"] = 200
        with self.assertRaises(MindPowerError):
            validate_mind_runtime(self.design, broken)

    def test_repeated_zero_or_oversized_ticks_are_forbidden(self):
        for duration in (0, 11, float("inf"), -1):
            with self.assertRaises(MindPowerError):
                tick_mind_power(self.design, self.account,
                                rows=self.rows, g19_power=self.g19,
                                seconds=duration)


if __name__ == "__main__":
    unittest.main()
