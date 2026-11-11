"""Access-evidence tests: identity limits, actual transitions and paged replay."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from world.ship_access_observations import (
    AccessEvidenceError, AccessMonitoringPlan, load_access_plan,
    project_access_page,
)
from world.ship_model import AccessLinkSpec, ShipWorldModel, SpaceSpec, load_ship_model


def model_fixture():
    spaces = tuple(
        SpaceSpec(id=key, name=key, kind="room", frame="fixed", zone="test",
                  current_condition="serviceable", metadata={})
        for key in ("CMD-PRIMARY", "B", "C", "D"))
    links = tuple(
        AccessLinkSpec(id=key, from_id=source, to_id=target,
                       kind="pressure_hatch", metadata={"pressure_boundary": True})
        for key, source, target in (
            ("AB", "CMD-PRIMARY", "B"), ("BC", "B", "C"), ("CD", "C", "D")))
    return ShipWorldModel(
        schema_version="ox.ship-world/0.1", model_version="test",
        principal={}, spaces=spaces, access_links=links)


def sample(sequence, operation, link, before, after, actor="#123"):
    return SimpleNamespace(
        sequence=sequence, operation=operation, component_key="access:" + link,
        before=before, after=after, actor_dbref=actor, game_time=1000.0 + sequence)


def test_plan():
    return AccessMonitoringPlan(
        topology_version="test", controlled_spaces=frozenset({"CMD-PRIMARY"}),
        rack_reader_candidates=(), candidate_link_options={})


class AccessEvidenceTests(unittest.TestCase):
    def test_replay_uses_three_real_sources_with_no_phantom_hatch_or_arrival(self):
        model, plan = model_fixture(), test_plan()
        source = [
            sample(1, "crew_hatch", "AB",
                   {"setting": "closed"},
                   {"setting": "open", "requested_value": "open"}),
            sample(2, "crew_hatch", "AB",
                   {"setting": "open"},
                   {"setting": "open", "requested_value": "open"}),
            sample(3, "crew_traverse", "AB",
                   {"space_id": "CMD-PRIMARY"}, {"space_id": "B"}),
            sample(4, "crew_indexed_transfer_queued", "BC",
                   {"space_id": "B"}, {"space_id": "C"}),
            sample(5, "crew_indexed_transfer_complete", "BC",
                   {"space_id": "B"}, {"space_id": "C"}),
            sample(6, "crew_hatch", "AB",
                   {"setting": "open"},
                   {"setting": "closed", "requested_value": "closed"}),
            sample(7, "crew_indexed_transfer_aborted", "BC",
                   {"space_id": "B"}, {"space_id": "C"}),
            sample(8, "crew_traverse", "CD",
                   {"space_id": "B"}, {"space_id": "D"}),
        ]
        result = project_access_page(
            source + [source[2]], model, plan,
            observed_links={"AB", "BC", "CD"}, identity_links={"AB"})
        events = result["events"]
        self.assertEqual([e["source_event_id"] for e in events],
                         ["1", "3", "5", "6"])
        self.assertEqual([e["kind"] for e in events],
                         ["hatch_change", "passage", "arrival", "hatch_change"])
        self.assertEqual(events[0]["setting_after"], "open")
        self.assertNotIn("direction", events[0])
        self.assertEqual(events[1]["direction"], "forward")
        self.assertEqual(events[2]["direction"], "forward")
        self.assertEqual(events[2]["from_space"], "B")
        self.assertEqual(events[2]["to_space"], "C")
        self.assertEqual(events[0]["actor_dbref"], "#123")
        self.assertNotIn("actor_dbref", events[2])
        self.assertEqual(result["next_after_sequence"], 8)

    def test_reader_scope_is_not_derived_from_a_client_claim(self):
        model, plan = model_fixture(), test_plan()
        record = sample(2, "crew_traverse", "AB",
                        {"space_id": "CMD-PRIMARY"}, {"space_id": "B"})
        self.assertEqual(project_access_page(
            [record], model, plan, observed_links=())["events"], [])
        self.assertNotIn("actor_dbref", project_access_page(
            [record], model, plan, observed_links={"AB"})["events"][0])
        with self.assertRaises(AccessEvidenceError):
            project_access_page(
                [record], model, plan, observed_links={"AB"},
                identity_links={"BC"})
        with self.assertRaises(AccessEvidenceError):
            project_access_page(
                [record], model, plan, observed_links={"BC"},
                identity_links={"BC"})
        with self.assertRaises(AccessEvidenceError):
            project_access_page(
                [record], model, plan, observed_links={"INVALID"})

    def test_pagination_scans_filtered_records_without_skipping_replays(self):
        model, plan = model_fixture(), test_plan()
        source = [
            sample(1, "crew_traverse", "CD",
                   {"space_id": "C"}, {"space_id": "D"}),
            sample(2, "crew_hatch", "AB",
                   {"setting": "closed"}, {"setting": "closed", "requested_value": "closed"}),
            sample(3, "crew_traverse", "AB",
                   {"space_id": "B"}, {"space_id": "CMD-PRIMARY"}),
            sample(4, "crew_traverse", "BC",
                   {"space_id": "B"}, {"space_id": "C"}),
        ]
        first = project_access_page(
            source, model, plan, observed_links={"AB"}, max_scan=2)
        self.assertEqual(first["events"], [])
        self.assertEqual(first["next_after_sequence"], 2)
        self.assertTrue(first["has_more"])
        second = project_access_page(
            source, model, plan, observed_links={"AB"},
            after_sequence=first["next_after_sequence"], max_scan=2)
        self.assertEqual([x["source_event_id"] for x in second["events"]], ["3"])
        self.assertFalse(second["has_more"])
        third = project_access_page(
            source, model, plan, observed_links={"AB"},
            after_sequence=second["next_after_sequence"], max_scan=2)
        self.assertEqual(third["events"], [])
        self.assertEqual(third["next_after_sequence"], 4)

    def test_malformed_events_do_not_create_evidence(self):
        model, plan = model_fixture(), test_plan()
        invalid = [
            sample(1, "crew_hatch", "AB",
                   {"setting": "closed"}, {"setting": "open", "requested_value": "closed"}),
            sample(2, "crew_traverse", "AB",
                   {"space_id": "C"}, {"space_id": "D"}),
            sample(3, "crew_indexed_transfer_complete", "AB",
                   {"space_id": "CMD-PRIMARY"}, {"space_id": "D"}),
        ]
        self.assertEqual(project_access_page(
            invalid, model, plan, observed_links={"AB"})["events"], [])
        for bad in (True, -1, 1.5):
            with self.assertRaises(AccessEvidenceError):
                project_access_page([], model, plan, observed_links=(),
                                    after_sequence=bad)

    def test_canonical_overlay_and_candidate_validate_without_fitting(self):
        canonical = load_ship_model()
        plan = load_access_plan(canonical)
        self.assertEqual(plan.topology_version, canonical.model_version)
        self.assertIn("CMD-PRIMARY", plan.controlled_spaces)
        self.assertNotIn("XCON-GAP-23", plan.controlled_spaces)
        self.assertIn(("MIND-03", "XCON-GAP-23"), plan.rack_reader_candidates)
        self.assertFalse(plan.candidate_link_options)

    def test_overlay_refuses_unknown_room_and_forged_motor_flags(self):
        model = model_fixture()
        data = {
            "schema_version": "ox.ship-access-monitoring/1",
            "status": "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY",
            "topology_version": "test",
            "controlled_spaces": ["CMD-PRIMARY"],
            "rack_reader_candidates": [],
            "candidate_access_links": [],
        }
        with TemporaryDirectory() as root:
            path = Path(root) / "overlay.json"
            def check(payload):
                path.write_text(json.dumps(payload), encoding="utf-8")
                return load_access_plan(model, path)
            self.assertEqual(check(data).controlled_links(model), {"AB"})
            data["controlled_spaces"] = ["MISSING"]
            with self.assertRaises(AccessEvidenceError):
                check(data)
            data["controlled_spaces"] = ["CMD-PRIMARY"]
            data["candidate_access_links"] = [
                {"id": "AB", "motorised": 1, "vacuum_seal": True}]
            with self.assertRaises(AccessEvidenceError):
                check(data)
            data["candidate_access_links"][0]["motorised"] = True
            self.assertEqual(check(data).candidate_link_options["AB"], (True, True))


if __name__ == "__main__":
    unittest.main()
