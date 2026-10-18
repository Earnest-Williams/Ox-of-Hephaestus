"""True native-Concordia entity choices without live credentials or Evennia."""
import tempfile
from pathlib import Path
import unittest

try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


@unittest.skipIf(MockModel is None, "Pinned Concordia optional extra required")
class LiveCognitionTests(unittest.TestCase):
    def setUp(self):
        from ox_ai.agents.live_concordia import build_live_brains
        self.brains = build_live_brains({"ari": "#12", "lin": "#13", "iona": "#14"})

    def test_three_entity_graphs_and_role_scoped_memories(self):
        from ox_ai.agents.crew import CommandOption
        lin, ari, iona = (self.brains[k] for k in ("lin", "ari", "iona"))
        self.assertIsNot(lin.agent.entity, ari.agent.entity)
        self.assertIsNot(iona.agent.entity, ari.agent.entity)
        self.assertTrue(lin.observe_event({
            "event_id": "oxevt-0001", "recipient_dbref": "#13",
            "game_time": 180.0, "kind": "coolant_alarm",
            "text": "Low bridge pressure", "data": {"alarm_id": "a1"},
        }))
        self.assertFalse(lin.observe_event({
            "event_id": "oxevt-0001", "recipient_dbref": "#13",
            "game_time": 180.0, "kind": "coolant_alarm",
            "text": "Low bridge pressure", "data": {"alarm_id": "a1"},
        }))
        with self.assertRaises(PermissionError):
            ari.observe_event({
                "event_id": "oxevt-0001", "recipient_dbref": "#13",
                "game_time": 180.0, "kind": "coolant_alarm",
                "text": "Low bridge pressure", "data": {},
            })
        self.assertTrue(any("Low bridge pressure" in m for m in lin.agent.memories))
        self.assertFalse(any("Low bridge pressure" in m for m in ari.agent.memories))
        response = lin.choose(
            CommandOption("Relay alarm", "oxradio"),
            alternative="Defer until a second observation",
        )
        lin.require(response, "oxradio")
        self.assertEqual(lin.inference_calls, 1)
        self.assertEqual(ari.inference_calls, 0)
        lin.record_unknown(response)
        self.assertEqual(len(lin.agent.pending_requests), 1)
        with tempfile.TemporaryDirectory() as d:
            lin.save_checkpoint(Path(d) / "lin.json")
            self.assertTrue((Path(d) / "lin.json").is_file())

    def test_deferred_choice_never_submits_unoffered_game_action(self):
        from ox_ai.agents.live_concordia import LiveCrewBrain
        from ox_ai.agents.crew import CommandOption
        class DeferModel:
            def sample_choice(self, prompt, responses, *, seed=None):
                return len(responses) - 1, responses[-1], {}
            def sample_text(self, prompt, **kwargs):
                raise AssertionError("Text generation is not permitted")
        brain = LiveCrewBrain("ari", "#12", DeferModel())
        decision = brain.choose(
            CommandOption("Operate pump", "oxaction"),
            alternative="Defer until better evidence",
        )
        with self.assertRaises(RuntimeError):
            brain.require(decision, "oxaction")
        self.assertEqual(brain.inference_calls, 1)
        self.assertFalse(brain.agent.pending_requests)

    def test_world_acknowledgement_must_be_own_scoped_event(self):
        from ox_ai.agents.crew import CommandOption
        brain = self.brains["iona"]
        brain.observe_event({
            "event_id": "evt-initial", "recipient_dbref": "#14",
            "game_time": 100.0, "kind": "release_request",
            "text": "Review pump", "data": {},
        })
        decision = brain.choose(
            CommandOption("Approve", "oxapprove"), alternative="Decline",
        )
        with self.assertRaises(PermissionError):
            brain.confirm(decision, {
                "event_id": "evt-private", "recipient_dbref": "#12",
                "game_time": 101.0, "kind": "release_recorded", "data": {},
            })
        self.assertEqual(len(brain.agent.pending_requests), 1)
        brain.confirm(decision, {
            "event_id": "evt-chief", "recipient_dbref": "#14",
            "game_time": 101.0, "kind": "release_recorded",
            "text": "World recorded chief approval", "data": {},
        })
        self.assertFalse(brain.agent.pending_requests)

    def test_delayed_private_event_retains_original_timestamp(self):
        brain = self.brains["lin"]
        one = {"event_id": "e2", "recipient_dbref": "#13", "kind": "radio",
               "game_time": 110.0, "text": "Newer report", "data": {}}
        older = {"event_id": "e1", "recipient_dbref": "#13", "kind": "radio",
                 "game_time": 105.0, "text": "Delayed report", "data": {}}
        self.assertTrue(brain.observe_event(one))
        self.assertTrue(brain.observe_event(older))
        self.assertEqual(brain.agent.revision, 2)
        self.assertTrue(any("Delayed report" in x for x in brain.agent.memories))

    def test_five_independent_specialist_entities_and_private_checkpoint_restore(self):
        from ox_ai.agents.live_concordia import (
            build_live_brains, LiveCrewBrain, make_model,
        )
        ids = {
            "lin": "#11", "ari": "#12", "iona": "#13",
            "mara": "#14", "teo": "#15",
        }
        agents = build_live_brains(ids)
        self.assertEqual(len(agents), 5)
        self.assertEqual(len({id(b.agent.entity) for b in agents.values()}), 5)
        self.assertTrue(all(b.inference_calls == 0 for b in agents.values()))
        for role, event_id, kind in (
            ("mara", "oxevt-0010", "cargo_shift"),
            ("teo", "oxevt-0011", "atmosphere_alarm"),
        ):
            self.assertTrue(agents[role].observe_event({
                "event_id": event_id, "recipient_dbref": ids[role],
                "game_time": 123.0, "kind": kind,
                "text": kind + " noticed at work station",
                "data": {"state": "faulted"},
            }))
        self.assertTrue(any("cargo_shift" in m for m in
                            agents["mara"].agent.memories))
        self.assertFalse(any("cargo_shift" in m for m in
                             agents["teo"].agent.memories))
        self.assertTrue(any("atmosphere_alarm" in m for m in
                            agents["teo"].agent.memories))
        self.assertFalse(any("atmosphere_alarm" in m for m in
                             agents["mara"].agent.memories))
        with self.assertRaises(PermissionError):
            agents["mara"].observe_event({
                "event_id": "wrong", "recipient_dbref": "#15",
                "game_time": 124.0, "kind": "atmosphere_alarm",
                "data": {},
            })
        with tempfile.TemporaryDirectory() as td:
            for role in ("mara", "teo"):
                path = Path(td) / (role + ".json")
                agents[role].save_checkpoint(path)
                restored = LiveCrewBrain.from_checkpoint(
                    role, ids[role], make_model(), path
                )
                self.assertEqual(restored.character_id, ids[role])
                self.assertEqual(restored.agent.revision, 1)
                self.assertEqual(restored.agent.memories,
                                 agents[role].agent.memories)
                with self.assertRaises(PermissionError):
                    LiveCrewBrain.from_checkpoint(
                        role, ids["lin"], make_model(), path
                    )

    def test_no_model_invocation_during_idle_and_refuse_wrong_ids(self):
        from ox_ai.agents.live_concordia import build_live_brains
        self.assertTrue(all(x.inference_calls == 0 for x in self.brains.values()))
        with self.assertRaises(ValueError):
            build_live_brains({"ari": "#1", "lin": "#1", "iona": "#2"})
        with self.assertRaises(ValueError):
            self.brains["ari"].observe_event({
                "event_id": "late", "recipient_dbref": "#12",
                "game_time": -1.0, "kind": "alarm", "data": {},
            })


if __name__ == "__main__":
    unittest.main()
