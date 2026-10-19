"""G3 Rumsfeld/open-world epistemics: no actor receives omniscient truth."""
from __future__ import annotations

import copy
import json
import unittest

from ox_ai.runtime.epistemics import AgentEpistemics


def addressed(sequence, *, who="#72", kind="atmosphere_alarm", msg=""):
    return {
        "event_id": f"oxevt-v2-{sequence:04d}",
        "kind": kind, "recipient_dbref": who,
        "game_time": float(sequence), "text": msg,
        "sender_dbref": "#81",
    }


class EpistemicTests(unittest.TestCase):
    def setUp(self):
        self.record = {}
        self.teo = AgentEpistemics(self.record, role="teo", character_id="#72")

    def test_unmodeled_and_known_unknown_do_not_imply_false(self):
        self.assertEqual(self.teo.assess("cargo.reserve", now=20),
                         {"status": "unmodeled", "value": None})
        self.assertEqual(self.record["surprises"], [])
        self.teo.ask("cargo.reserve", reason="How many are physically available?")
        self.assertEqual(self.teo.assess("cargo.reserve", now=21)["status"],
                         "known_unknown")
        self.assertNotIn("value", self.teo.assess("cargo.reserve", now=21))
        self.assertEqual(self.record["surprises"], [])

    def test_persons_belief_is_never_promoted_without_world_evidence(self):
        self.teo.believe("scrubber.spares", 3, confidence=1.0,
                         basis="Mara guessed from yesterday's manifest")
        result = self.teo.assess("scrubber.spares", now=100)
        self.assertEqual(result["status"], "believed")
        self.assertEqual(result["value"], 3)
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(self.record["observations"], {})

    def test_local_verified_knowledge_expires_and_retains_history(self):
        self.teo.ask("scrubber.spares", reason="Must inspect before cartridge replacement")
        self.assertTrue(self.teo.observe_verified(
            "scrubber.spares", 0, evidence_id="localread-01",
            at=10.0, valid_for=2.0, source="world_local",
        ))
        observed = self.teo.assess("scrubber.spares", now=11)
        self.assertEqual(observed["status"], "observed")
        self.assertEqual(observed["value"], 0)
        self.assertEqual(self.teo.assess("scrubber.spares", now=14)["status"],
                         "known_unknown")
        self.assertTrue(self.teo.observe_verified(
            "scrubber.spares", 1, evidence_id="localread-02",
            at=15.0, valid_for=2.0, source="world_local",
        ))
        self.assertEqual(self.teo.assess("scrubber.spares", now=16)["value"], 1)
        self.assertEqual(self.record["observations"]["scrubber.spares"]["history"][0]["value"], 0)
        # Newer direct reading survives replay of older evidence.
        self.assertFalse(self.teo.observe_verified(
            "scrubber.spares", 0, evidence_id="localread-01",
            at=10.0, valid_for=2.0, source="world_local",
        ))

    def test_world_evidence_refutes_contrary_belief_but_not_same_one(self):
        self.teo.believe("scrubber.spares", 5, confidence=0.7,
                         basis="Likely crates in the store")
        self.teo.observe_verified("scrubber.spares", 0, evidence_id="localread-1",
                                  at=10, valid_for=1, source="world_local")
        self.assertEqual(self.record["beliefs"]["scrubber.spares"]["state"], "refuted")
        self.assertEqual(self.teo.assess("scrubber.spares", now=12)["status"],
                         "historically_observed")
        with self.assertRaises(PermissionError):
            self.teo.observe_verified("scrubber.spares", 2, evidence_id="localread-1",
                                      at=10, valid_for=1, source="world_local")

    def test_knowledge_cannot_be_asserted_from_testimony_or_model(self):
        for source in ("coworker_says", "llm", "prompt", "guess"):
            with self.assertRaises(PermissionError):
                self.teo.observe_verified("scrubber.spares", 5,
                                          evidence_id="claim-1", at=4,
                                          source=source)
        for bad in (float("nan"), float("inf"), object(), []):
            with self.assertRaises(ValueError):
                self.teo.believe("scrubber.spares", bad,
                                 confidence=0.4, basis="Guess")
        with self.assertRaises(ValueError):
            self.teo.believe("scrubber.spares", 4,
                             confidence=float("nan"), basis="Guess")

    def test_unknown_unknown_cannot_be_inventoried_until_retrospective_surprise(self):
        self.assertEqual(self.record["surprises"], [])
        self.teo.observe_verified(
            "thermal_anomaly.unexpected_duct", True,
            evidence_id="localread-duct-1", at=20, valid_for=1,
            source="world_local", surprise=True,
        )
        self.assertEqual(self.record["surprises"], [{
            "fact": "thermal_anomaly.unexpected_duct",
            "evidence_id": "localread-duct-1",
            "classification": "previously_unmodeled",
        }])
        # A novel observation by itself need not have been surprising.
        self.teo.observe_verified("pump.state", "normal",
                                  evidence_id="reading-1", at=21,
                                  source="world_local")
        self.assertEqual(len(self.record["surprises"]), 1)
        self.teo.ask("cargo.missing_item", reason="What is missing?")
        self.teo.observe_verified("cargo.missing_item", "filter",
                                  evidence_id="reading-2", at=22,
                                  source="world_local", surprise=True)
        self.assertEqual(len(self.record["surprises"]), 1)

    def test_world_event_is_proof_of_its_arrival_not_sender_text_truth(self):
        fake_claim = addressed(3, msg="I have 200 spare cartridges, trust me")
        self.assertTrue(self.teo.receive_event(fake_claim))
        self.assertFalse(self.teo.receive_event(fake_claim))
        self.assertEqual(self.teo.assess("scrubber.spares", now=3)["status"],
                         "unmodeled")
        self.assertEqual(len(self.record["events"]), 1)
        with self.assertRaises(PermissionError):
            self.teo.receive_event(addressed(4, who="#81"))
        with self.assertRaises(PermissionError):
            self.teo.receive_event({**fake_claim, "kind": "supply_replenished"})

    def test_private_state_survives_restart_and_rejects_cross_actor_restore(self):
        self.teo.ask("scrubber.spares", reason="Service requires verified stock")
        self.teo.receive_event(addressed(7))
        self.teo.believe("cargo.reserve", 1, confidence=0.2, basis="Rumour")
        copy_record = json.loads(json.dumps(self.record))
        recovered = AgentEpistemics(copy_record, role="teo", character_id="#72")
        self.assertEqual(recovered.assess("cargo.reserve", now=12)["status"],
                         "believed")
        with self.assertRaises(PermissionError):
            AgentEpistemics(copy.deepcopy(copy_record),
                            role="mara", character_id="#81")
        with self.assertRaises(PermissionError):
            AgentEpistemics(copy.deepcopy(copy_record),
                            role="teo", character_id="#99")
        altered = copy.deepcopy(copy_record)
        altered["observations"]["hidden"] = {"claim": "unverified"}
        with self.assertRaises(ValueError):
            AgentEpistemics(altered, role="teo", character_id="#72")


    def test_long_running_evidence_retains_recent_proofs_without_replay_churn(self):
        for sequence in range(1, 701):
            self.assertTrue(self.teo.receive_event(addressed(sequence)))
        self.assertEqual(len(self.record["events"]), 512)
        self.assertNotIn("oxevt-v2-0001", self.record["events"])
        self.assertIn("oxevt-v2-0700", self.record["events"])
        saved = json.loads(json.dumps(self.record, sort_keys=True))
        restored = AgentEpistemics(saved, role="teo", character_id="#72")
        self.assertFalse(restored.receive_event(addressed(700)))
        self.assertTrue(restored.receive_event(addressed(701)))
        self.assertEqual(len(saved["events"]), 512)



if __name__ == "__main__":
    unittest.main()
