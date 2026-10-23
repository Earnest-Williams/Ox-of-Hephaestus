"""Aggregate all G11 real-world seed treatments, no selective success subset."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path


SEEDS=(241,619,1009)


def assess(root:Path)->dict:
    runs=[]
    for seed in SEEDS:
        filepath=root/f"ox-g11-world-seed-{seed}"/"g11-report.json"
        if not filepath.is_file():
            raise FileNotFoundError(f"Missing real-world verified seed {seed}")
        report=json.loads(filepath.read_text(encoding="utf-8"))
        if (report.get("schema")!=1 or report.get("seed")!=seed
                or report.get("status")!="real_evennia_g11_verified"
                or report.get("turns")!=205 or report.get("six_distinct_actors")!=6
                or report.get("world_maintenance_receipts")!=5):
            raise PermissionError("Wrong or unverified live-world seed")
        receipt_count=report["real_agreement_receipts"]
        if (receipt_count<1
                or report["selected_model_calls"]+report["goap_replies"]!=receipt_count
                or len(report["actual_world_social_proofs"])!=receipt_count
                or sum(report["responses"].values())!=receipt_count):
            raise AssertionError("World reply vs per-person routing records disagree")
        signatures=set()
        for event in report["actual_world_social_proofs"]:
            if (not event["request_id"] or not event["source_event_id"]
                    or not event["counterpart_event_id"]
                    or event["chosen"] not in ("accept","defer","decline")):
                raise AssertionError("Unconfirmed social world event in seed")
            if event["request_id"] in signatures:
                raise AssertionError("Replayed or duplicated world social work request")
            signatures.add(event["request_id"])
        runs.append(report)
    if len({r["seed"] for r in runs})!=3:
        raise AssertionError("No independent seed coverage")
    actions=Counter()
    per_actor=Counter()
    world_receipts=0
    model_calls=0
    goap_routes=0
    deviated=0
    for run in runs:
        actions.update(run["responses"])
        per_actor.update(run["actor_replies"])
        world_receipts+=run["real_agreement_receipts"]
        model_calls+=run["selected_model_calls"]
        goap_routes+=run["goap_replies"]
        deviated+=run["different_from_goap"]
    return {
        "schema":1,
        "status":"all_three_real_evennia_seeds_verified",
        "seeds":list(SEEDS),
        "authenticated_turns":sum(r["turns"] for r in runs),
        "real_equipment_work_receipts":sum(
            r["world_maintenance_receipts"] for r in runs),
        "real_social_commitment_receipts":world_receipts,
        "decider_world_social_choices":model_calls,
        "goap_world_social_choices":goap_routes,
        "model_departures_from_symbolic_goap":deviated,
        "world_accepted_answers":dict(actions),
        "recipient_character_workload":dict(per_actor),
        "by_seed":[{
            k:v for k,v in r.items() if k in (
                "seed","turns","real_agreement_receipts","selected_model_calls",
                "goap_replies","different_from_goap","responses","actor_replies",
            )
        } for r in runs],
        "limits":[
            "Each accepted reply and peer observation has an actual Evennia receipt.",
            "Equipment work remains a procedural GOAP task with real world verification.",
            "The original authored social relationships are scenario priors, not independently natural personalities.",
            "A difference from GOAP is not automatically harmful or story-worthy.",
            "Only six crew and two scheduled physical incidents per seed; no production supervisor.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=assess(args.root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True))
    print(json.dumps({k:v for k,v in result.items() if k in (
        "authenticated_turns","real_equipment_work_receipts",
        "real_social_commitment_receipts","decider_world_social_choices",
        "goap_world_social_choices","model_departures_from_symbolic_goap",
        "world_accepted_answers"
    )},sort_keys=True))
    print("OX_G11_THREE_SEED_WORLD_SUITE_PASS")


if __name__=="__main__":
    main()
