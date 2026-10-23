"""Fail-closed aggregation of all six G13 native profile interventions."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROLES=("lin","ari","iona","mara","teo","captain")
CASES=("ordinary_favor","strained_repair","fatigue_pressure","conflicted_loyalty")
ARMS=("original","procedural","independent")
ORDERS=("canonical","reverse","rotate")
CHOICES={"accept","defer","decline"}


def assess(root:Path)->dict:
    cases=Counter()
    arm_choices={a:Counter() for a in ARMS}
    effects=Counter()
    repeats=Counter()
    order=Counter()
    routing={a:[] for a in ARMS}
    for role in ROLES:
        file=root/(role+".json")
        if not file.is_file():
            raise FileNotFoundError("Missing G13 actor report: "+role)
        r=json.loads(file.read_text(encoding="utf-8"))
        if (r.get("schema")!=1 or r.get("status")!="g13_matched_counterfactual_complete"
                or r.get("role")!=role or r.get("engine")!="decider-q4"
                or r.get("source_g9_run")!=39872687597
                or r.get("source_world_maintenance_receipts")!=5
                or r.get("world_commands_sent")!=0
                or r.get("native_model_calls")!=40
                or r.get("hypothetical_only") is not True):
            raise PermissionError("Incomplete, mock, or unauthenticated actor data")
        rows=r["rows"]
        controls=r["repeat_controls"]
        expected={(case,arm,position) for case in CASES
                  for arm in ARMS for position in ORDERS}
        if (len(rows)!=36 or len(controls)!=4
                or {(x["case"],x["arm"],x["order"]) for x in rows}!=expected):
            raise AssertionError("Missing, duplicated or replaced G13 treatment")
        by={(x["case"],x["arm"],x["order"]):x for x in rows}
        for x in rows+controls:
            if (x["role"]!=role or x["choice"] not in CHOICES
                    or set(x["scores"])!=CHOICES
                    or abs(sum(x["scores"].values())-1)>.021
                    or x["evidence_digest"]!=r["evidence_digest"]
                    or x["world_commands_sent"]!=0
                    or x["model_calls"]!=1
                    or x["hypothetical"] is not True
                    or not isinstance(x["prompt_control_sha256"],str)
                    or len(x["prompt_control_sha256"])!=64):
                raise PermissionError("Malformed or untrusted G13 decision")
        for case in CASES:
            for pos in ORDERS:
                matching=[by[case,arm,pos] for arm in ARMS]
                if len({x["prompt_control_sha256"] for x in matching})!=1:
                    raise PermissionError("Matched treatments changed non-trait prompt")
                if len({x["evidence_digest"] for x in matching})!=1:
                    raise PermissionError("Evidence mismatch")
                a,b,c=(x["choice"] for x in matching)
                effects["procedural_vs_original"]+=int(a!=b)
                effects["independent_vs_original"]+=int(a!=c)
                effects["procedural_vs_independent"]+=int(b!=c)
                cases[case]+=1
                for x in matching:
                    arm_choices[x["arm"]][x["choice"]]+=1
                    routing[x["arm"]].append(x["route_probability_only"])
            for arm in ARMS:
                order["stable_"+arm]+=int(len({
                    by[case,arm,pos]["choice"] for pos in ORDERS
                })==1)
            control=next((x for x in controls if x["case"]==case),None)
            if control is None or control["arm"]!="original" or control["order"]!="canonical":
                raise AssertionError("Missing frozen-profile repeat treatment")
            repeats["identical_choice"]+=int(control["choice"]==by[case,"original","canonical"]["choice"])
            repeats["identical_scores_within_0_01"]+=int(
                all(abs(control["scores"][k]-by[case,"original","canonical"]["scores"][k])<.01
                    for k in CHOICES))
    assert set(cases)==set(CASES)
    return {
        "schema":1,"status":"all_six_native_g13_profiles_evaluated",
        "actors":6,"cases":4,"counterbalanced_orders":3,"profile_arms":3,
        "native_model_calls":240,"hypothetical_only":True,"world_commands_sent":0,
        "paired_conditions":72, "profile_choice_differences":dict(effects),
        "per_arm_choices":{k:dict(v) for k,v in arm_choices.items()},
        "order_invariant_six_actor_case_arms":dict(order),
        "repeat_controls":dict(repeats),
        "mean_configured_decider_consultation_probability":{
            arm:sum(routing[arm])/len(routing[arm]) for arm in ARMS
        },
        "disclaimer":[
            "Trait interventions are hypothetical and not the original character personalities.",
            "Counterfactuals retain actor-specific memories; actors cannot be compared as identical individuals.",
            "Choice variation across trait arms is an effect of model conditioning, not automatically realistic psychology.",
            "The Decider is invoked directly for all trial arms; route probabilities are measured separately.",
            "No Evennia social offers, world commands or world receipts were created.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    result=assess(args.root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    print("OX_G13_ALL_SIX_MATCHED_PROFILE_PASS")

if __name__=="__main__":
    main()
