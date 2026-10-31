"""SKETCH end-to-end: world projection → engineer belief → inspection → join.

Pure: no Evennia, no sockets. It exercises the real contracts, the real
``AgentEpistemics`` ledger and the Polars join with one stale-belief case.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

import orjson

ROOT: Path = Path(__file__).resolve().parents[3]
for extra in (
    ROOT / "game",
    ROOT / "services" / "ai-handler" / "src",
    ROOT / "services" / "interface" / "src",
):
    sys.path.insert(0, str(extra))

from ox_ai.inspection.authorization import Grant, authorize  # noqa: E402
from ox_ai.inspection.projection import (  # noqa: E402
    InspectionUnavailable,
    inspection_page,
)
from ox_ai.runtime.epistemics import AgentEpistemics  # noqa: E402
from ox_ai.runtime.g19_beliefs import ingest_actor_pages, panel_fact  # noqa: E402
from ox_contracts.world_read_model import parse_world_read_page  # noqa: E402
from ox_interface.views.belief_vs_actual import belief_vs_actual  # noqa: E402
from world.world_read_projection import (  # noqa: E402
    AccessRow,
    ActorSnapshot,
    AuditRow,
    CellRow,
    CursorBinding,
    EquipmentRow,
    ExitRow,
    InventoryRow,
    JournalRow,
    MotionBalances,
    PanelReadingRow,
    SpaceRow,
    StaleCursor,
    WorldSnapshot,
    actor_series,
    cell_pressure_kpa,
    decode_cursor,
    developer_series,
)

KEY: bytes = b"k" * 32
ENGINEER: str = "#12"


def cell(cell_id: str, mass_kg: float) -> CellRow:
    return CellRow(cell_id, mass_kg, mass_kg * 0.232, 293.15, 100.0)


def world(now_s: float, hab_mass_kg: float, *, publication: int) -> WorldSnapshot:
    spaces: list[SpaceRow] = [
        SpaceRow("HAB-01-COR", "serviceable", "PZ-HAB-01"),
        SpaceRow("ENG-CONTROL", "serviceable", "PZ-ENG"),
        SpaceRow("HULL-EXT", "serviceable", "VACUUM"),
    ] + [SpaceRow(f"BULK-{i:03d}", "serviceable", "PZ-ENG") for i in range(200)]
    return WorldSnapshot(
        world_id="ox-test",
        topology_version="0.4",
        engineering_version="0.5-candidate",
        publication_seq=publication,
        game_time_s=now_s,
        spaces=tuple(spaces),
        cells=(cell("PZ-HAB-01", hab_mass_kg), cell("PZ-ENG", 118.0)),
        access=(
            AccessRow(
                "ACC-1",
                "HAB-01-COR",
                "ENG-CONTROL",
                True,
                "closed_or_auto",
                "closed_or_auto",
                "serviceable",
            ),
            AccessRow(
                "ACC-2",
                "ENG-CONTROL",
                "HULL-EXT",
                True,
                "closed",
                "closed",
                "serviceable",
            ),
            AccessRow(
                "ACC-3",
                "ENG-CONTROL",
                "BULK-000",
                True,
                "open",
                "open",
                "serviceable",
            ),
        ),
        equipment=(
            EquipmentRow("LP-HAB-01", "HAB-01-COR", "serviceable", True, {}),
            EquipmentRow(
                "F1-FW-01",
                "ENG-CONTROL",
                "serviceable",
                True,
                {"physics_startup_s": 4.0},
            ),
        ),
        inventories=(InventoryRow("INV-REACTION", 2.5), InventoryRow("INV-SPARES", 25)),
        motion=MotionBalances(propellant_kg=1500.0, ftl_fuel_kg=900.0),
        audit=(AuditRow(7, "crew_traverse", now_s - 1), AuditRow(8, "late", now_s + 1)),
    )


def engineer_view(now_s: float, sampled_s: float, reading_kpa: float) -> ActorSnapshot:
    return ActorSnapshot(
        world_id="ox-test",
        topology_version="0.4",
        engineering_version="0.5-candidate",
        publication_seq=8,
        game_time_s=now_s,
        character_id=ENGINEER,
        location_id="HAB-01-COR",
        panel_readings=(
            PanelReadingRow(
                "oxevt-v2-0041",
                "LP-HAB-01",
                "HAB-01-COR",
                "online",
                read_game_s=sampled_s + 2,
                sampled_game_s=sampled_s,
                metrics={"pressure_kpa": reading_kpa, "oxygen_kpa": 21.0},
            ),
        ),
        exits=(ExitRow("ACC-1", "ENG-CONTROL", "advertised"),),
        events=(
            JournalRow(
                "oxevt-v2-0041",
                ENGINEER,
                "panel_reading",
                sampled_s + 2,
                "Local panel LP-HAB-01: online",
                {"panel": "LP-HAB-01", "zone": None},
            ),
            JournalRow("oxevt-v2-0042", ENGINEER, "radio", sampled_s + 3, "", {}),
        ),
    )


class DeveloperProjection(unittest.TestCase):
    def test_pages_round_trip_through_contract(self) -> None:
        pages, omissions = developer_series(
            world(1000.0, 118.0, publication=8), viewer="developer:1", key=KEY
        )
        self.assertEqual(len(pages), 2)  # 203 spaces > 128 per page
        for page in pages:
            parse_world_read_page(orjson.loads(page.model_dump_json()))
        first = pages[0]
        settings = {b.link_id: b.setting for b in first.pressure_boundaries}
        self.assertEqual(settings, {"ACC-1": "closed", "ACC-2": "closed"})
        self.assertIn("boundary inside one envelope: ACC-3", omissions.reasons)
        vacuum = next(b for b in first.pressure_boundaries if b.link_id == "ACC-2")
        self.assertIsNone(vacuum.to_cell_id)
        stocks = {s.account_id: (s.accounting, s.quantity_kg) for s in first.stocks}
        self.assertEqual(stocks["INV-REACTION"], ("legacy_reference", 2500.0))
        self.assertEqual(stocks["motion.propellant_kg"][1], 1500.0)
        self.assertEqual([e.event_id for e in first.audit_events], ["cse-7"])

    def test_cursor_is_bound_to_viewer_and_publication(self) -> None:
        pages, _ = developer_series(
            world(1000.0, 118.0, publication=8), viewer="developer:1", key=KEY
        )
        token = pages[0].page.next_cursor
        assert token is not None
        binding = CursorBinding(
            "developer_actual", "developer:1", "ox-test", 8, "0.4", "0.5-candidate"
        )
        self.assertEqual(decode_cursor(token, binding, key=KEY), 1)
        for other in (
            CursorBinding(
                "developer_actual", "developer:2", "ox-test", 8, "0.4", "0.5-candidate"
            ),
            CursorBinding(
                "developer_actual", "developer:1", "ox-test", 9, "0.4", "0.5-candidate"
            ),
        ):
            with self.assertRaises(StaleCursor):
                decode_cursor(token, other, key=KEY)
        with self.assertRaises(StaleCursor):
            decode_cursor(token[:-2] + "00", binding, key=KEY)


class EngineerBeliefVersusActual(unittest.TestCase):
    def test_stale_belief_after_a_leak(self) -> None:
        # t=1000: the engineer reads the HAB panel at a nominal pressure.
        reading: float = cell_pressure_kpa(cell("PZ-HAB-01", 118.0))
        pages, omissions = actor_series(engineer_view(1000.0, 995.0, reading), key=KEY)
        self.assertEqual(pages[0].equipment[0].availability, "available")
        self.assertEqual(len(pages[0].addressed_events), 1)  # empty text omitted
        self.assertEqual(len(omissions.reasons), 1)

        record: dict[str, Any] = {}
        ledger = AgentEpistemics(record, role="engineer", character_id=ENGINEER)
        report = ingest_actor_pages(ledger, pages)
        self.assertEqual(report.recorded, 4)  # availability, 2 metrics, exit
        self.assertEqual(report.events_proved, 1)
        state: bytes = orjson.dumps({"epistemics": {"engineer": record}})

        # t=1300: the cell has lost gas; the engineer has not looked again.
        world_pages, _ = developer_series(
            world(1300.0, 80.0, publication=40), viewer="developer:1", key=KEY
        )
        inspection = inspection_page(state, ENGINEER)
        table = belief_vs_actual(world_pages, inspection)
        row = table.filter(table["metric"] == "pressure_kpa").row(0, named=True)
        self.assertEqual(row["panel_id"], "LP-HAB-01")
        self.assertAlmostEqual(row["believed"], reading)
        self.assertLess(row["actual"], reading)
        self.assertFalse(row["verified"])  # 305 s old, valid for 60 s
        self.assertAlmostEqual(row["belief_age_s"], 305.0)
        self.assertIn(panel_fact("LP-HAB-01", "pressure_kpa"), record["observations"])

    def test_private_cognition_is_not_shared(self) -> None:
        authorize(Grant("developer", None), ENGINEER)
        authorize(Grant("character", ENGINEER), ENGINEER)
        for grant in (Grant("character", "#13"), None):
            with self.assertRaises(InspectionUnavailable):
                authorize(grant, ENGINEER)


if __name__ == "__main__":
    unittest.main()
