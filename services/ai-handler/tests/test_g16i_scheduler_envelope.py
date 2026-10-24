"""G16i: independently test service-time model without calling a native model."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"scenarios/profiling"))
import g16i_scheduler_envelope as g16i


def synthetic_shape_only():
    """NOT a native result; checks model schema/refusal math only."""
    return {
        "schema":1,
        "experiment":"g16f_deliberate_personality_throughput",
        "backend":"decider-q4",
        "native_gguf_forwards_measured":True,
        "hypothetical_only":True,
        "evennia_commands_sent":0,
        "forward_calls":198,
        "maximum_concurrent_native_forwards":1,
        "default_production_timeout_seconds":25,
        "engine_manifest":{"sha256":g16i.NATIVE_MODEL_HASH,"model":"decider-q4"},
        "measured_cohorts":[
            {
                "actors":n,"model_forwards_counted":3*n,
                "decisions_completed":n,
                "arrival_pattern":"sequential",
                "median_end_to_end_seconds":20.55,
                "p95_end_to_end_seconds":21.09,
                "measured_decisions_per_hour_at_this_backend":170.0,
            } for n in g16i.POPULATIONS
        ],
    }


class G16iEvidenceEnvelopeTests(unittest.TestCase):
    def test_refuse_unverified_model_or_burst_for_native_reference(self):
        data=synthetic_shape_only()
        for path,value in (
            ("backend","fixture"),
            ("forward_calls",197),
            ("maximum_concurrent_native_forwards",2),
            ("native_gguf_forwards_measured",False),
        ):
            mutated=copy.deepcopy(data)
            mutated[path]=value
            with self.subTest(path=path), self.assertRaises(PermissionError):
                g16i.validate_native_g16f(mutated)
        mutated=copy.deepcopy(data)
        mutated["engine_manifest"]["sha256"]="0"*64
        with self.assertRaises(PermissionError):
            g16i.validate_native_g16f(mutated)
        mutated=copy.deepcopy(data)
        mutated["measured_cohorts"][2]["arrival_pattern"]="burst"
        with self.assertRaises(PermissionError):
            g16i.validate_native_g16f(mutated)

    def test_all_forty_simultaneously_cannot_finish_before_25s_deadline(self):
        b=g16i.burst(40,0.0)
        for method in ("queued","bounded"):
            one=g16i.simulate(b,service_seconds=21.09,workers=1,mode=method)
            self.assertEqual(one["arrivals"],40)
            self.assertEqual(one["completed_before_deadline"],1)
            self.assertEqual(one["no_world_commands"],True)
            self.assertEqual(
                one["accepted_native_starts"]+one["refused_unexecuted"]
                +one["expired_while_queued"]+one["same_actor_inflight_refusals"],
                40,
            )
            self.assertEqual(one["mean_wait_seconds_for_started"] >= 0,True)
            optimistic=g16i.simulate(b,service_seconds=21.09,workers=2,mode=method)
            self.assertEqual(optimistic["completed_before_deadline"],2)
            self.assertFalse(optimistic["measured_concurrent_engine"])
        safe=g16i.simulate(b,service_seconds=21.09,workers=1,mode="bounded")
        self.assertEqual(safe["refused_unexecuted"],39)
        self.assertEqual(safe["expired_after_native_started"],0)

    def test_staggered_service_and_blocked_actor_do_not_duplicate(self):
        rows=g16i.burst(40,22.0)
        for method in ("queued","bounded"):
            r=g16i.simulate(rows,service_seconds=21.09,workers=1,mode=method)
            self.assertEqual(r["completed_before_deadline"],40)
            self.assertEqual(r["accepted_native_starts"],40)
            self.assertEqual(r["expired_while_queued"],0)
            self.assertEqual(r["expired_after_native_started"],0)
            self.assertEqual(r["refused_unexecuted"],0)
        same=(g16i.Arrival(0,1,0),g16i.Arrival(1,1,1))
        x=g16i.simulate(same,service_seconds=21.09,workers=1,mode="bounded")
        self.assertEqual(x["completed_before_deadline"],1)
        self.assertEqual(x["same_actor_inflight_refusals"],1)
        with self.assertRaises(ValueError):
            g16i.simulate(tuple(reversed(rows)),
                          service_seconds=21.09,workers=1,mode="bounded")

    def test_staggering_helps_without_claiming_concurrent_speedup(self):
        for pop in g16i.POPULATIONS:
            burst=g16i.simulate(g16i.burst(pop,0.0),
                                service_seconds=21.09,workers=1,mode="bounded")
            spaced=g16i.simulate(g16i.burst(pop,22.0),
                                 service_seconds=21.09,workers=1,mode="bounded")
            self.assertEqual(burst["completed_before_deadline"],1)
            self.assertEqual(spaced["completed_before_deadline"],pop)
            self.assertEqual(burst["accepted_native_starts"],1)

    def test_entire_hypothetical_demand_grid_and_reproducibility(self):
        x=synthetic_shape_only()
        outcome=g16i.run(x)
        self.assertEqual(len(outcome["burst_tables"]),96)
        self.assertEqual(len(outcome["hourly_hypothetical_demand_sweep"]),96)
        self.assertEqual(outcome["real_native_forwards_in_this_model"],0)
        self.assertEqual(outcome["actual_concurrent_native_capacity_measured"],1)
        self.assertTrue(outcome["two_workers_are_only_optimistic_unverified"])
        self.assertEqual(outcome["deadline_seconds"],25)
        self.assertEqual(outcome,g16i.run(x))
        self.assertEqual(outcome["reference_40_actor_sequential_p95_seconds"],21.09)
        self.assertEqual(outcome["reference_40_actor_sequential_median_seconds"],20.55)
        self.assertTrue(all(
            s["replicates"]==12 for s in outcome["hourly_hypothetical_demand_sweep"]
        ))
        for n in (6,20,40):
            for duty in g16i.DUTY_OPPORTUNITIES_HOURLY:
                for p in g16i.DELIBERATION_PROBABILITIES:
                    a=g16i.stochastic_duty_arrivals(
                        n,duty_rate=duty,route_probability=p,seed=615)
                    z=g16i.stochastic_duty_arrivals(
                        n,duty_rate=duty,route_probability=p,seed=615)
                    self.assertEqual(a,z)


if __name__=="__main__":
    unittest.main()
