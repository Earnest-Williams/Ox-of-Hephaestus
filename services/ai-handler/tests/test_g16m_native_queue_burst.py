"""G16m queue and late-worker recovery tests; fixture rates are NOT native."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scenarios/profiling"))

try:
    import concordia
    import ox_contracts
except ImportError:
    concordia = ox_contracts = None


@unittest.skipUnless(
    concordia is not None and ox_contracts is not None,
    "Optional pinned native Concordia and strict G16a action contracts absent",
)
class NativeQueueBurstStructureTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        import g16m_native_queue_burst as burst
        from g16f_personality_throughput import EngineMeter, FakeSystemOne
        cls.burst = burst
        cls.EngineMeter = EngineMeter
        cls.FakeSystemOne = FakeSystemOne

    async def test_all_6_20_40_actor_proposals_run_same_g16c_scheduler_in_fixture(self):
        with mock.patch.dict(os.environ, {"OX_PERSONALITY_CHOICE":"1"}):
            result = await self.burst.run(engine_name="fixture")
        self.assertEqual(result["backend"], "fixture")
        self.assertFalse(result["native_model_verified"])
        self.assertEqual(result["actual_native_gguf_forward_calls"], 0)
        self.assertEqual(result["synthetic_fixture_forward_calls"], 198)
        self.assertEqual([x["actors"] for x in result["cohorts"]], [6,20,40])
        self.assertEqual([x["accepted_unexecuted_proposals"]
                          for x in result["cohorts"]], [6,20,40])
        self.assertEqual([x["timed_out_no_proposal"] for x in result["cohorts"]],
                         [0,0,0])
        for x in result["cohorts"]:
            self.assertEqual(x["underlying_actual_System_One_forwards"],3*x["actors"])
            self.assertEqual(x["provider_invocations_started"],x["actors"])
            self.assertEqual(x["provider_invocations_finished"],x["actors"])
            self.assertEqual(x["telemetry"]["proposals_adopted"],x["actors"])
            self.assertEqual(x["telemetry"]["timed_out_waiting_for_slot"],0)
            self.assertEqual(x["telemetry"]["timed_out_with_provider_active"],0)
            self.assertEqual(x["telemetry"]["maximum_simultaneous_inference_invocations"],1)
            self.assertEqual(x["world_commands_sent"],0)
            self.assertEqual(x["accepted_evennia_receipts"],0)
            self.assertEqual(len(x["accepted_actor_ids"]),x["actors"])
        self.assertFalse(result["personality_policy_production_enabled"])

    async def test_actually_detached_slow_fixture_times_out_and_drains_no_actor_state(self):
        class SlowSystemOne:
            def __init__(self, delegate):
                self.delegate=delegate
            def system_one(self, prompt, questions):
                time.sleep(.03)
                return self.delegate.system_one(prompt, questions)
        engine=self.EngineMeter(SlowSystemOne(self.FakeSystemOne()))
        with mock.patch.dict(os.environ, {"OX_PERSONALITY_CHOICE":"1"}):
            six=await self.burst.run_cohort(
                6,meter=engine,timeout_seconds=.06,native=False,
            )
        self.assertEqual(six["actors"],6)
        self.assertEqual(six["accepted_unexecuted_proposals"],0)
        self.assertEqual(six["timed_out_no_proposal"],6)
        self.assertEqual(six["provider_invocations_started"],1)
        self.assertEqual(six["provider_invocations_finished"],1)
        self.assertEqual(six["underlying_actual_System_One_forwards"],3)
        self.assertEqual(six["telemetry"]["timed_out_with_provider_active"],1)
        self.assertEqual(six["telemetry"]["timed_out_waiting_for_slot"],5)
        self.assertEqual(six["telemetry"]["expired_queue_entries_discarded"],5)
        self.assertEqual(six["telemetry"]["provider_finished_after_abandonment"],1)
        self.assertEqual(six["telemetry"]["proposals_adopted"],0)
        self.assertGreater(six["post_timeout_worker_drain_seconds"],0)
        self.assertEqual(six["world_commands_sent"],0)

    async def test_reject_fake_genuine_native_model_and_deadline_override(self):
        with self.assertRaises(FileNotFoundError):
            await self.burst.run(engine_name="decider-q4")
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            gguf=root/"decider.gguf"
            manifest=root/"model.json"
            gguf.write_bytes(b"this is not the authenticated native GGUF")
            manifest.write_text(json.dumps({
                "model":"decider-q4",
                "hf_revision":self.burst.MODEL_REVISIONS[0],
                "tokenizer_revision":self.burst.MODEL_REVISIONS[1],
                "size":gguf.stat().st_size,
                "sha256":"f"*64,
            }))
            with self.assertRaises(PermissionError):
                self.burst.native_engine(gguf,manifest)
            with self.assertRaises(ValueError):
                await self.burst.run(engine_name="decider-q4",
                                     gguf_path=gguf,manifest=manifest,
                                     timeout_override=12.0)

    async def test_invalid_deadline_or_actor_populations_fail_before_model_start(self):
        meter=self.EngineMeter(self.FakeSystemOne())
        for n in (0,5,41):
            with self.subTest(actors=n),self.assertRaises(ValueError):
                await self.burst.run_cohort(
                    n,meter=meter,timeout_seconds=1,native=False,
                )
        with self.assertRaises(ValueError):
            await self.burst.run_cohort(
                6,meter=meter,timeout_seconds=0,native=False,
            )
        self.assertEqual(meter.calls,0)


if __name__=="__main__":
    unittest.main()
