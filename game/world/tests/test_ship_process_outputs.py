"""Pure physical-source and conservation tests for 42 fitted process motors."""
import random
import unittest

from world.ship_process_outputs import (
    AIR_TRAINS, AIR_HANDLERS, SPINE_FANS, WATER_MACHINES, BEARING_PUMPS,
    METRICS, FIELD, ProcessOutputError, check_receipt, step_process_output,
    proves_process_output, machine_depressurized, attributed_fire_discharge,
)


class PositiveProcessOutputTests(unittest.TestCase):
    def test_exact_42_original_sites_and_no_welding_or_uninstalled_machines(self):
        self.assertEqual(len(METRICS), 42)
        self.assertEqual(len(BEARING_PUMPS), 24)
        self.assertEqual(len(AIR_HANDLERS), 8)
        self.assertEqual(len(WATER_MACHINES), 4)
        self.assertEqual(set(AIR_TRAINS), {"ECLSS-A", "ECLSS-B"})
        self.assertEqual(set(SPINE_FANS), {"SPINE-AIR-FWD", "SPINE-AIR-AFT"})
        self.assertFalse(proves_process_output(
            "SHOP-CNC-MILL", {FIELD: {}}, observed_s=10))

    def test_real_media_credit_only_in_current_individual_epoch(self):
        for name in METRICS:
            if name in BEARING_PUMPS:
                continue
            with self.subTest(name=name):
                first = step_process_output(
                    name, None, dt_s=10, now_s=10, delivered_kg=0.125)
                self.assertTrue(proves_process_output(
                    name, {FIELD: first}, observed_s=10))
                self.assertFalse(proves_process_output(
                    name, {FIELD: first}, observed_s=20))
                off = step_process_output(
                    name, first, dt_s=10, now_s=20, delivered_kg=0)
                self.assertEqual(off["total"], first["total"])
                self.assertEqual(off["amount"], 0)
                self.assertFalse(proves_process_output(
                    name, {FIELD: off}, observed_s=20))
                with self.assertRaises(ProcessOutputError):
                    step_process_output(
                        name, off, dt_s=10, now_s=20, delivered_kg=0.5)

    def test_bearing_wetted_loop_pressure_flow_and_bleed_down(self):
        for name in BEARING_PUMPS:
            with self.subTest(name=name):
                charged = step_process_output(
                    name, None, dt_s=10, now_s=10, driven=True)
                self.assertEqual(charged["pressure_bar"], 4.0)
                self.assertGreater(charged["amount"], 0)
                self.assertFalse(machine_depressurized(
                    name, {FIELD: charged}))
                self.assertTrue(proves_process_output(
                    name, {FIELD: charged}, observed_s=10))
                cut = step_process_output(
                    name, charged, dt_s=10, now_s=20, driven=False)
                self.assertEqual(cut["pressure_bar"], 0)
                self.assertEqual(cut["amount"], 0)
                self.assertEqual(cut["total"], charged["total"])
                self.assertTrue(machine_depressurized(
                    name, {FIELD: cut}))
                self.assertFalse(proves_process_output(
                    name, {FIELD: cut}, observed_s=20))
                with self.assertRaises(ProcessOutputError):
                    step_process_output(name, cut, dt_s=10, now_s=30,
                                        driven=False, delivered_kg=1)

    def test_fire_main_shared_header_does_not_credit_both_sources(self):
        solo = attributed_fire_discharge(
            ["FIRE-PUMP-FWD"], 2.5, demand_present=True)
        self.assertEqual(solo["FIRE-PUMP-FWD"], 2.5)
        self.assertEqual(solo["FIRE-PUMP-AFT"], 0)
        two = attributed_fire_discharge(
            ["FIRE-PUMP-FWD", "FIRE-PUMP-AFT"], 2.5,
            demand_present=True)
        self.assertEqual(sum(two.values()), 0)
        self.assertEqual(sum(attributed_fire_discharge(
            [], 0, demand_present=True).values()), 0)
        with self.assertRaises(ProcessOutputError):
            attributed_fire_discharge(
                ["FIRE-PUMP-FWD"], 2.5, demand_present=False)
        with self.assertRaises(ProcessOutputError):
            attributed_fire_discharge(
                ["FIRE-PUMP-FWD", "FIRE-PUMP-FWD"], 2.5,
                demand_present=True)

    def test_existing_water_transfers_meter_real_a_b_mass_and_isolate_loss(self):
        from world.ship_water_recycling import initial_water, step_water
        stocks = {"normal": 162000.0, "reserve": 70000.0,
                  "sanitary": 0.0, "industrial": 0.0, "hazardous": 0.0}
        hardware = {
            "potable": True, "process": {"A": True, "B": True},
            "fixed": {"grey": True, "black": True},
            "oxygen": False,
            "bins": {name: {"A": True, "B": True}
                     for name in ("sanitary", "industrial", "hazardous")},
        }
        water, stocks, both = step_water(
            initial_water(), 86400, stocks=stocks, hardware=hardware)
        self.assertGreater(both["processed_A_kg"], 0)
        self.assertGreater(both["processed_B_kg"], 0)
        self.assertAlmostEqual(
            both["processed_kg"],
            both["processed_A_kg"] + both["processed_B_kg"])
        hardware["process"]["A"] = False
        water, stocks, failover = step_water(
            water, 10, stocks=stocks, hardware=hardware)
        self.assertEqual(failover["processed_A_kg"], 0)
        self.assertGreater(failover["processed_B_kg"], 0)
        a = step_process_output(
            "WATER-PROC-A", None, dt_s=10, now_s=10,
            delivered_kg=failover["processed_A_kg"])
        b = step_process_output(
            "WATER-PROC-B", None, dt_s=10, now_s=10,
            delivered_kg=failover["processed_B_kg"])
        self.assertFalse(proves_process_output(
            "WATER-PROC-A", {FIELD: a}, observed_s=10))
        self.assertTrue(proves_process_output(
            "WATER-PROC-B", {FIELD: b}, observed_s=10))

    def test_corrupt_receipts_do_not_create_motor_proof(self):
        original = step_process_output(
            "ECLSS-A", None, dt_s=10, now_s=10, delivered_kg=0.04)
        for bad in (
            {**original, "amount": float("nan")},
            {**original, "amount": -1},
            {**original, "total": 0},
            {**original, "metric": "fake_induction_kg"},
            {**original, "pressure_bar": 4},
        ):
            with self.assertRaises(ProcessOutputError):
                check_receipt("ECLSS-A", bad)
        with self.assertRaises(ProcessOutputError):
            step_process_output(
                "ECLSS-A", original, dt_s=10, now_s=20,
                delivered_kg=0.04, driven=True)

    def test_seeded_source_loss_cannot_reverse_cumulative_output(self):
        rng = random.Random(4219)
        for name in METRICS:
            row = None
            prev = 0.0
            for tick in range(1, 91):
                powered = rng.randrange(4) != 0
                row = step_process_output(
                    name, row, dt_s=10, now_s=10*tick,
                    driven=bool(powered) if name in BEARING_PUMPS else False,
                    delivered_kg=(0 if name in BEARING_PUMPS or not powered
                                  else rng.random() * 0.04))
                self.assertGreaterEqual(row["total"], prev)
                self.assertGreaterEqual(row["amount"], 0)
                prev = row["total"]


if __name__ == "__main__":
    unittest.main()
