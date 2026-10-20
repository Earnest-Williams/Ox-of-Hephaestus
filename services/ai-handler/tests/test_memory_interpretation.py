"""G8: genuine, bounded subjective reinterpretation without forged world truth."""
from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
import tempfile
import unittest

from ox_ai.memory.interpretation import InterpretationBank
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory, TemporalMemoryBank


def claim(identity, stance, *, at=0, happened=None,
          group=None, kind="witnessed_speech", subject="lin",
          topic="lin_ari_separated", credibility=80, salience=90):
    when = at if happened is None else happened
    return TemporalMemory(
        identity, subject, f"{identity} is this person's account", kind,
        occurred_turn=when, learned_turn=at, confidence=95,
        salience=salience, claim_subject=subject,
        claim_key=topic, claim_stance=stance,
        source_group=group, claim_credibility=credibility,
        source_event_id=f"received.{identity}",
    )


class SubjectiveBeliefTests(unittest.TestCase):
    def test_old_claim_survives_as_memory_when_new_account_disagrees(self):
        first = claim("remembered.lin", 1, at=0, happened=-380,
                      group="lin.marriage_account", kind="recollection")
        competing = claim("ari.recollection", -1, at=22, group="ari.marriage_account")
        memories = TemporalMemoryBank((first, competing))
        beliefs = InterpretationBank()
        first_change = beliefs.admit(first, at_turn=0)
        before = beliefs.get("lin", "lin_ari_separated").confidence
        second_change = beliefs.admit(competing, at_turn=22)
        after = beliefs.get("lin", "lin_ari_separated")
        self.assertIsNotNone(first_change)
        self.assertIsNotNone(second_change)
        self.assertEqual(second_change.reason, "counterevidence")
        self.assertLess(after.confidence, before)
        self.assertTrue(after.contradictory)
        self.assertEqual(len(memories), 2)
        self.assertIs(memories.get("remembered.lin"), first)
        self.assertEqual(first.claim_stance, 1)  # not rewritten
        self.assertEqual(second_change.evidence_id, "ari.recollection")

    def test_heard_speech_is_not_objective_confirmation_of_its_claim(self):
        speech = claim("s1", 1, at=5, kind="witnessed_speech")
        receipt = claim("w1", 1, at=5, kind="world_receipt")
        a, b = InterpretationBank(), InterpretationBank()
        a.admit(speech, at_turn=5)
        b.admit(receipt, at_turn=5)
        self.assertGreater(
            b.get("lin", "lin_ari_separated").confidence,
            a.get("lin", "lin_ari_separated").confidence,
        )
        # These tests model a verified receipt *entailing its proposition*,
        # never inferring a third party's motives from a contract.

    def test_same_origin_repeated_ten_times_is_one_source(self):
        bank = InterpretationBank()
        initial = claim("l1", 1, at=0, group="lin.same_assertion")
        bank.admit(initial)
        before = bank.get("lin", "lin_ari_separated").confidence
        for i in range(1, 11):
            repeated = claim(f"l{i+1}", 1, at=i,
                             group="lin.same_assertion")
            self.assertIsNone(bank.admit(repeated))
        view = bank.get("lin", "lin_ari_separated")
        self.assertEqual(view.confidence, before)
        self.assertEqual(view.evidence_ids, ("l1",))
        self.assertEqual(len(view.sources), 1)
        self.assertEqual(len(view.revisions), 1)

    def test_recantation_changes_interpretation_not_history(self):
        bank = InterpretationBank()
        bank.admit(claim("first", 1, at=1, group="speaker.lin"), at_turn=1)
        before = bank.get("lin", "lin_ari_separated").confidence
        revised = bank.admit(
            claim("recanted", -1, at=12, group="speaker.lin"), at_turn=12)
        self.assertEqual(revised.reason, "source_revised")
        view = bank.get("lin", "lin_ari_separated")
        self.assertEqual(view.evidence_ids, ("recanted",))
        self.assertLess(view.confidence, before)
        self.assertFalse(view.contradictory)
        self.assertEqual(len(view.revisions), 2)

    def test_character_specific_prior_yields_different_reactions(self):
        key = ("lin", "lin_ari_separated")
        trusting = InterpretationBank({key: 72})
        skeptical = InterpretationBank({key: 28})
        evidence = claim("message", 1, at=8)
        trusting.admit(evidence)
        skeptical.admit(evidence)
        self.assertGreater(trusting.get(*key).confidence,
                           skeptical.get(*key).confidence)

    def test_credible_new_evidence_outweighs_old_weak_rumor(self):
        bank = InterpretationBank()
        rumor = claim("rumor", 1, at=0, happened=-700, credibility=20,
                      kind="testimony", group="one.chain")
        reliable = claim("independent", -1, at=50, credibility=95,
                         kind="witnessed_speech", group="ari.firsthand")
        bank.admit(rumor)
        old = bank.get("lin", "lin_ari_separated").confidence
        bank.admit(reliable, at_turn=50)
        new = bank.get("lin", "lin_ari_separated")
        self.assertLess(new.confidence, old)
        self.assertIn("one.chain", new.sources)
        self.assertIn("ari.firsthand", new.sources)

    def test_irrelevant_or_future_evidence_does_not_change_a_view(self):
        bank = InterpretationBank()
        bank.admit(claim("p", 1))
        before = bank.to_records()
        self.assertIsNone(bank.admit(TemporalMemory(
            "heard-smalltalk", "lin", "We should have tea", "witnessed_speech",
            20, 20, 100, 20, source_event_id="speech.20")))
        self.assertEqual(before, bank.to_records())
        unrelated = claim("other", -1, at=40, subject="mara",
                          topic="mara_teo_finished")
        bank.admit(unrelated, at_turn=40)
        self.assertEqual(bank.get("lin", "lin_ari_separated").confidence,
                         before["states"][0]["confidence"])
        with self.assertRaises(ValueError):
            bank.admit(claim("future", -1, at=80), at_turn=50)
        with self.assertRaises(ValueError):
            bank.admit(claim("past", -1, at=-1), at_turn=-1)

    def test_checkpoint_roundtrip_and_no_reconsideration_on_reload(self):
        original = InterpretationBank()
        original.admit(claim("old", 1, at=2))
        original.admit(claim("new", -1, at=10, group="independent"))
        payload = original.to_records()
        recovered = InterpretationBank.from_records(
            json.loads(json.dumps(payload)))
        self.assertEqual(recovered.to_records(), payload)
        self.assertEqual(len(recovered.all_revisions()),
                         len(original.all_revisions()))
        self.assertIsNone(recovered.admit(claim("new", -1, at=10,
                                               group="independent"),
                                         at_turn=10))
        self.assertEqual(recovered.to_records(), payload)
        bad = {"version": 50, "states": [], "priors": []}
        with self.assertRaises(ValueError):
            InterpretationBank.from_records(bad)

    def test_typed_claim_validations(self):
        with self.assertRaises(ValueError):
            claim("bad", 0)
        with self.assertRaises(ValueError):
            claim("bad", 1, credibility=-1)
        with self.assertRaises(ValueError):
            SeededMemory("s", "claim", "lin", claim_key="refusal", claim_stance=0)
        with self.assertRaises(ValueError):
            TemporalMemory(
                "no", "ari", "I know", "recollection", 0, 0, 90, 90,
                claim_stance=1,
            )

    @unittest.skipIf(find_spec("concordia") is None,
                     "Native private checkpoint requires Concordia extra")
    def test_native_private_checkpoint_fork_and_legacy_rebuild(self):
        from concordia.testing.mock_model import MockModel
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        def person(name, ref, seeds=()):
            return CrewAgent(
                CrewIdentity(name, ref, name, "Duty", "Watch"), MockModel(),
                initial_memories=seeds)
        seed = SeededMemory(
            "old.original", "Lin and Ari had separated, I thought.", "lin",
            occurred_turn=-200, claim_key="lin_ari_separated",
            claim_subject="lin", claim_stance=1,
            source_group="lin.marriage_account")
        mara = person("Mara", "#1", (seed,))
        ari = person("Ari", "#2")
        before = mara.interpretations.get(
            "lin", "lin_ari_separated").confidence
        first_original = mara.temporal_memories.get("old.original").text
        response = claim("ari.contradiction", -1, at=40,
                         group="ari.marriage_account")
        self.assertTrue(mara.remember_timed(response))
        after = mara.interpretations.get("lin", "lin_ari_separated")
        self.assertLess(after.confidence, before)
        self.assertEqual(mara.temporal_memories.get("old.original").text,
                         first_original)
        self.assertEqual(len(ari.interpretations.all_revisions()), 0)
        self.assertEqual(mara.pending_requests, ())  # no world receipts
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "person.json"
            mara.save_checkpoint(checkpoint)
            restored = CrewAgent.from_checkpoint(checkpoint, MockModel())
            self.assertEqual(restored.interpretations.to_records(),
                             mara.interpretations.to_records())
            self.assertFalse(restored.remember_timed(response))
            fork = restored.fork_for_inference()
            fork.remember_timed(claim("later", 1, at=55, group="person.three"))
            self.assertNotEqual(fork.interpretations.to_records(),
                                restored.interpretations.to_records())
            # Version 1 checkpoints already in circulation have no new index.
            legacy = json.loads(checkpoint.read_text())
            legacy.pop("interpretations")
            checkpoint.write_text(json.dumps(legacy))
            recovered = CrewAgent.from_checkpoint(checkpoint, MockModel())
            self.assertIsNotNone(recovered.interpretations.get(
                "lin", "lin_ari_separated"))
            self.assertEqual(len(recovered.temporal_memories), 2)


if __name__ == "__main__":
    unittest.main()
