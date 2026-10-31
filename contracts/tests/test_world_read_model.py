"""Contract-only regressions: no Evennia installation or API is implied."""

import copy
import unittest
from pydantic import ValidationError
from ox_contracts.world_read_model import parse_world_read_page, ModelIdentity


def base(scope="developer_actual"):
    return dict(
        schema_version="ox.world.read/1",
        world_id="OX-FULL-SHIP",
        models=dict(topology_version="0.4", engineering_version="0.5-candidate"),
        publication_seq=17,
        game_time_s=1020.0,
        page=dict(complete=True),
        scope=scope,
    )


def actual():
    return {
        **base(),
        "equipment": [
            dict(
                equipment_id="GEN-B",
                space_id="ENG-CONTROL",
                condition="serviceable",
                measurements=[dict(name="power_kw", unit="kW", value=200.0)],
            )
        ],
        "stocks": [
            dict(
                account_id="INV-REACTION",
                custodian="inventory",
                accounting="legacy_reference",
                quantity_kg=10000.0,
            ),
            dict(
                account_id="motion.propellant_kg",
                custodian="motion_ledger",
                accounting="operational_balance",
                quantity_kg=9500.0,
            ),
        ],
        "audit_events": [
            dict(
                event_id="PHY:17",
                kind="hull_alarm",
                occurred_game_s=1000.0,
                visibility="developer_only",
            )
        ],
    }


def observed():
    return {
        **base("actor_observed"),
        "character_id": "#57",
        "location_id": "ENG-CONTROL",
        "equipment": [
            dict(
                equipment_id="GEN-B",
                availability="stale",
                reported_condition="serviceable",
                evidence=dict(
                    source="local_panel", source_id="LP-ENG", observed_game_s=900.0
                ),
            )
        ],
        "exits": [
            dict(
                link_id="ACC-ENG-HAB",
                from_space_id="ENG-CONTROL",
                assessment="unknown",
                evidence=dict(
                    source="local_capability",
                    source_id="ACC-ENG-HAB",
                    observed_game_s=1019.0,
                ),
            )
        ],
        "addressed_events": [
            dict(
                event_id="ALARM:18",
                recipient_character_id="#57",
                kind="life_support_warning",
                occurred_game_s=1018.0,
                text="Low pressure in service corridor",
                datum_fields={"datum_zone": "PZ-HUB-SVC", "datum_pressure_kpa": 51.2},
                source="delivered_world_event",
            )
        ],
    }


class WorldReadContractTests(unittest.TestCase):
    def bad(self, data):
        with self.assertRaises((ValidationError, ValueError)):
            parse_world_read_page(data)

    def test_strict_roundtrips_and_scope(self):
        for payload in (actual(), observed()):
            model = parse_world_read_page(payload)
            self.assertEqual(model.scope, payload["scope"])
            self.assertEqual(
                type(model).model_validate_json(model.model_dump_json()), model
            )

    def test_schema_and_corrupt_measurement(self):
        for field, value in (
            ("schema_version", "ox.world.read/2"),
            ("scope", "operator"),
            ("game_time_s", float("nan")),
            ("publication_seq", -1),
        ):
            payload = actual()
            payload[field] = value
            self.bad(payload)
        payload = actual()
        payload["equipment"][0]["measurements"][0]["value"] = float("inf")
        self.bad(payload)
        payload = actual()
        payload["handler_memory"] = {}
        self.bad(payload)

    def test_legacy_fuel_is_not_spendable(self):
        self.assertEqual(len(parse_world_read_page(actual()).stocks), 2)
        for fuel in ("INV-REACTION", "INV-FTL-FUEL"):
            p = actual()
            p["stocks"][0]["account_id"] = fuel
            p["stocks"][0]["accounting"] = "operational_balance"
            self.bad(p)
        p = actual()
        p["stocks"][1]["account_id"] = "motion.dry_mass_kg"
        self.bad(p)
        p = actual()
        p["stocks"][1]["quantity_kg"] = float("inf")
        self.bad(p)

    def test_actor_privacy_and_observation_freshness(self):
        for mutate in (
            lambda p: p["addressed_events"][0].update(recipient_character_id="#58"),
            lambda p: p.update(audit_events=actual()["audit_events"]),
            lambda p: p["exits"][0].update(from_space_id="CMD-PRIMARY"),
            lambda p: p["exits"][0]["evidence"].update(source="direct_inspection"),
            lambda p: p["equipment"][0]["evidence"].update(observed_game_s=99999.0),
            lambda p: p["equipment"][0].update(availability="unavailable"),
            lambda p: p["equipment"][0]["evidence"].update(source="addressed_event"),
        ):
            p = observed()
            mutate(p)
            self.bad(p)
        p = observed()
        p["equipment"][0].update(availability="unavailable", reported_condition=None)
        p["equipment"][0]["evidence"]["observed_game_s"] = 1019.0
        parse_world_read_page(p)

    def test_pagination_duplicates_and_future(self):
        for changes in (dict(complete=False), dict(complete=True, next_cursor="abc")):
            p = actual()
            p["page"] = changes
            self.bad(p)
        p = actual()
        p["page"] = dict(complete=False, next_cursor="abc")
        parse_world_read_page(p)
        p = actual()
        p["stocks"].append(copy.deepcopy(p["stocks"][0]))
        self.bad(p)
        p = actual()
        p["audit_events"][0]["occurred_game_s"] = 2000.0
        self.bad(p)
        p = actual()
        p["equipment"] = p["equipment"] * 129
        self.bad(p)

    def test_renderer_requires_both_model_identities(self):
        model = ModelIdentity.model_validate(base()["models"])
        model.require_renderer(
            topology_version="0.4", engineering_version="0.5-candidate"
        )
        for topology, engineering in (("0.4", "0.4"), ("0.5", "0.5-candidate")):
            with self.assertRaises(ValueError):
                model.require_renderer(
                    topology_version=topology, engineering_version=engineering
                )

    def test_pressure_cells_span_rooms_and_boundaries_are_real_links(self):
        p = actual()
        p["spaces"] = [
            dict(
                space_id="TEST-A", condition="serviceable", pressure_cell_id="PZ-TEST"
            ),
            dict(
                space_id="TEST-B", condition="serviceable", pressure_cell_id="PZ-TEST"
            ),
            dict(space_id="TEST-VOID", condition="serviceable", pressure_cell_id=None),
        ]
        p["pressure_cells"] = [
            dict(
                cell_id="PZ-TEST",
                space_ids=["TEST-A", "TEST-B"],
                pressure_kpa=101.0,
                oxygen_kpa=21.0,
                temperature_k=293.15,
                # 101 kPa at 293.15 K in 150 m3 under the world's dry-air model.
                gas_mass_kg=180.041,
                volume_m3=150.0,
            )
        ]
        p["pressure_boundaries"] = [
            dict(
                link_id="HATCH-A",
                from_space_id="TEST-A",
                to_space_id="TEST-VOID",
                from_cell_id="PZ-TEST",
                to_cell_id=None,
                setting="closed",
                authored_policy="closed_or_auto",
                condition="serviceable",
            )
        ]
        m = parse_world_read_page(p)
        self.assertEqual(len(m.pressure_cells[0].space_ids), 2)
        self.assertEqual(m.pressure_boundaries[0].setting, "closed")
        bad = copy.deepcopy(p)
        bad["spaces"][0]["measurements"] = [
            dict(name="pressure_kpa", unit="kPa", value=101.0)
        ]
        self.bad(bad)
        bad = copy.deepcopy(p)
        bad["spaces"][0]["pressure_cell_id"] = "PZ-FORGED"
        self.bad(bad)
        bad = copy.deepcopy(p)
        bad["pressure_boundaries"][0]["from_cell_id"] = "PZ-FORGED"
        self.bad(bad)
        bad = copy.deepcopy(p)
        bad["pressure_cells"][0]["space_ids"].append("TEST-A")
        self.bad(bad)
        bad = copy.deepcopy(p)
        bad["pressure_boundaries"][0]["to_cell_id"] = "PZ-TEST"
        self.bad(bad)
        # A design policy is not an actual hatch state.
        bad = copy.deepcopy(p)
        bad["pressure_boundaries"][0]["setting"] = "closed_or_auto"
        self.bad(bad)
        # Room IDs inside a cell obey the identifier grammar.
        for room in ("", "X" * 5000, "bad room"):
            bad = copy.deepcopy(p)
            bad["pressure_cells"][0]["space_ids"] = [room]
            self.bad(bad)
        # Pressure must agree with mass, temperature and volume.
        for field, value in (
            ("gas_mass_kg", 1e30),
            ("volume_m3", 1.0),
            ("pressure_kpa", 50.0),
        ):
            bad = copy.deepcopy(p)
            bad["pressure_cells"][0][field] = value
            self.bad(bad)

    def test_duplicate_metrics_and_units_are_rejected(self):
        for readings in (
            [
                dict(name="pressure_kpa", unit="kPa", value=60.0),
                dict(name="pressure_kpa", unit="kPa", value=61.0),
            ],
            [dict(name="pressure_kpa", unit="furlongs", value=60.0)],
            [dict(name="pressure_kpa", unit="kg", value=60.0)],
            [dict(name="volume_m3", unit="K", value=3.0)],
            [dict(name="tank_volume_m3", unit="K", value=3.0)],
            [dict(name="pump_flow_kg_s", unit="kg", value=3.0)],
            [dict(name="bearing_temperature_k", unit="kPa", value=300.0)],
        ):
            p = actual()
            p["equipment"][0]["measurements"] = readings
            self.bad(p)
        p = observed()
        p["equipment"][0]["readings"] = [
            dict(name="power_kw", unit="kW", value=10.0),
            dict(name="power_kw", unit="kW", value=11.0),
        ]
        self.bad(p)
        # Suffixed names take their own unit; unsuffixed names any listed unit.
        p = actual()
        p["equipment"][0]["measurements"] = [
            dict(name="tank_volume_m3", unit="m3", value=3.0),
            dict(name="pump_flow_kg_s", unit="kg/s", value=3.0),
            dict(name="valve_position", unit="%", value=40.0),
        ]
        parse_world_read_page(p)

    def test_real_addressed_event_text_and_flat_datums(self):
        event = parse_world_read_page(observed()).addressed_events[0]
        self.assertIn("Low pressure", event.text)
        self.assertEqual(event.datum_fields["datum_pressure_kpa"], 51.2)
        for field in ("text", "datum_fields"):
            p = observed()
            if field == "text":
                del p["addressed_events"][0]["text"]
            else:
                p["addressed_events"][0][field] = {"datum_bad": {"nested": "no"}}
            self.bad(p)
        for datums in (
            {"unit": "furlongs"},
            {"datum_bad": float("inf")},
            {"datum_bad": [1, 2]},
        ):
            p = observed()
            p["addressed_events"][0]["datum_fields"] = datums
            self.bad(p)

    def test_event_evidence_is_consistent_and_may_be_paginated(self):
        p = observed()
        p["equipment"][0]["availability"] = "available"
        p["equipment"][0]["evidence"] = dict(
            source="addressed_event",
            source_id="ALARM:18",
            event_id="ALARM:18",
            observed_game_s=1019.0,
        )
        parse_world_read_page(p)
        # The cited event may be on another page of the same cursor series.
        other_page = copy.deepcopy(p)
        other_page["equipment"][0]["evidence"]["event_id"] = "ALARM:17"
        parse_world_read_page(other_page)
        other_page = copy.deepcopy(p)
        other_page["addressed_events"] = []
        parse_world_read_page(other_page)
        # When co-paged, the observation cannot predate the event it cites.
        bad = copy.deepcopy(p)
        bad["equipment"][0]["evidence"]["observed_game_s"] = 1017.0
        self.bad(bad)

    def test_freshness_policy_is_age_based_not_supplied_by_client(self):
        p = observed()
        p["equipment"][0]["availability"] = "available"
        p["equipment"][0]["evidence"]["observed_game_s"] = 960.0
        parse_world_read_page(p)  # exactly 60 game-seconds old
        p = observed()
        p["equipment"][0]["availability"] = "available"
        p["equipment"][0]["evidence"]["observed_game_s"] = 20.0
        self.bad(p)  # 1000 game-seconds old
        p = observed()
        p["equipment"][0]["availability"] = "stale"
        p["equipment"][0]["evidence"]["observed_game_s"] = 1019.0
        self.bad(p)
        p = observed()
        p["equipment"][0]["availability"] = "unavailable"
        p["equipment"][0]["reported_condition"] = None
        p["equipment"][0]["evidence"]["observed_game_s"] = 1019.0
        parse_world_read_page(p)
        # A failure known for 1,020 s is still unavailable, with its real time.
        p["equipment"][0]["evidence"]["observed_game_s"] = 0.0
        parse_world_read_page(p)
        # ...but an unavailable instrument still supplies no reading.
        p["equipment"][0]["reported_condition"] = "serviceable"
        self.bad(p)

    def test_advertised_exit_needs_destination(self):
        p = observed()
        p["exits"][0]["assessment"] = "advertised"
        p["exits"][0]["to_space_id"] = "HAB-ENTRY"
        parse_world_read_page(p)
        del p["exits"][0]["to_space_id"]
        self.bad(p)


class PreProducerAmendmentTests(unittest.TestCase):
    """31 Oct 2026 in-place amendments before any producer publishes."""

    def bad(self, data):
        with self.assertRaises((ValidationError, ValueError)):
            parse_world_read_page(data)

    def test_null_datum_is_a_reported_unknown_not_a_missing_key(self):
        p = observed()
        p["addressed_events"][0]["datum_fields"] = {
            "datum_zone": "PZ-HUB-SVC",
            "datum_sampled_game_s": None,
        }
        event = parse_world_read_page(p).addressed_events[0]
        self.assertIn("datum_sampled_game_s", event.datum_fields)
        self.assertIsNone(event.datum_fields["datum_sampled_game_s"])
        p["addressed_events"][0]["datum_fields"] = {"datum_bad": {"nested": None}}
        self.bad(p)

    def panel_page(self, sampled, delivered):
        p = observed()
        p["equipment"][0]["availability"] = "available"
        p["equipment"][0]["evidence"] = dict(
            source="local_panel",
            source_id="LP-ENG",
            observed_game_s=sampled,
            event_id="ALARM:18",
        )
        p["addressed_events"][0]["occurred_game_s"] = delivered
        return p

    def test_panel_evidence_may_cite_its_later_delivery_event(self):
        parse_world_read_page(self.panel_page(sampled=1000.0, delivered=1018.0))
        parse_world_read_page(self.panel_page(sampled=1018.0, delivered=1018.0))
        # A reading cannot be delivered before the panel sampled it.
        self.bad(self.panel_page(sampled=1018.5, delivered=1018.0))

    def test_only_event_or_panel_evidence_cites_events(self):
        p = observed()
        p["exits"][0]["evidence"]["event_id"] = "ALARM:18"
        self.bad(p)
        p = observed()
        p["equipment"][0]["evidence"] = dict(
            source="addressed_event", source_id="ALARM:18", observed_game_s=1019.0
        )
        self.bad(p)


class FrozenPayloadTests(unittest.TestCase):
    def test_event_datums_are_immutable_and_round_trip(self):
        event = parse_world_read_page(observed()).addressed_events[0]
        with self.assertRaises(TypeError):
            event.datum_fields["datum_pressure_kpa"] = 0.0  # type: ignore[index]
        model = parse_world_read_page(observed())
        again = type(model).model_validate_json(model.model_dump_json())
        self.assertEqual(
            dict(again.addressed_events[0].datum_fields),
            dict(event.datum_fields),
        )
        dumped = model.model_dump()
        self.assertIs(type(dumped["addressed_events"][0]["datum_fields"]), dict)


if __name__ == "__main__":
    unittest.main()
