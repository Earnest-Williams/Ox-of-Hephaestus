"""G14 aggregator: require every authentic actor, arm, order, case and repeat."""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path

ROLES=("lin","ari","iona","mara","teo","captain")
CASES=("verified_mutual_aid","finite_spare_dispute",
       "approved_watch_relief","uncertain_private_apology")
ARMS=("numeric_original","numeric_independent",
      "prose_original","prose_independent")
ORDERS=("canonical","cycle_left","cycle_right")
POSITIONS={"canonical":(0,1,2),"cycle_left":(1,2,0),
           "cycle_right":(2,0,1)}
ACTIONS={
    "verified_mutual_aid":("accept_help","work_alone","reschedule"),
    "finite_spare_dispute":("reserve_spare","support_loan","seek_review"),
    "approved_watch_relief":("cover_watch","keep_watch","offer_alternative"),
    "uncertain_private_apology":("consider_talk","protect_space","ask_later"),
}
BASELINES={
    "verified_mutual_aid":"accept_help",
    "finite_spare_dispute":"reserve_spare",
    "approved_watch_relief":"cover_watch",
    "uncertain_private_apology":"consider_talk",
}


def assess(root:Path):
    if not root.is_dir():
        raise FileNotFoundError("Missing G14 complete actors directory")
    results=[]
    for role in ROLES:
        path=root/(role+".json")
        if not path.is_file():
            raise FileNotFoundError("Missing G14 native character report: "+role)
        r=json.loads(path.read_text(encoding="utf-8"))
        if (r.get("schema")!=2
                or r.get("status")!="g14_matched_balanced_profile_arms_complete"
                or r.get("engine")!="decider-q4"
                or r.get("role")!=role or r.get("source_g9_run")!=39872687597
                or r.get("source_world_maintenance_receipts")!=5
                or r.get("hypothetical_only") is not True
                or r.get("world_commands_sent")!=0 or r.get("native_model_calls")!=52):
            raise PermissionError("Unverified, incomplete or nonnative actor source")
        rows=r.get("rows")
        repeats=r.get("repeat_controls")
        if not isinstance(rows,list) or not isinstance(repeats,list):
            raise ValueError("Missing native G14 evidence")
        expected={(case,arm,order) for case in CASES for arm in ARMS
                  for order in ORDERS}
        keys={(x["case"],x["arm"],x["order"]) for x in rows}
        if len(rows)!=48 or keys!=expected or len(repeats)!=4:
            raise AssertionError("Missing or duplicated G14 treatment")
        by={(x["case"],x["arm"],x["order"]):x for x in rows}
        for x in rows+repeats:
            c=x["case"]
            if (x["role"]!=role or c not in CASES
                    or x["choice"] not in ACTIONS[c]
                    or x["goap_baseline"]!=BASELINES[c]
                    or set(x["scores"])!=set(ACTIONS[c])
                    or any(type(n) not in (int,float) or not 0<=n<=1
                           for n in x["scores"].values())
                    or abs(sum(x["scores"].values())-1)>.021
                    or x["evidence_digest"]!=r["evidence_digest"]
                    or x["model_calls"]!=1 or x["world_commands_sent"]!=0
                    or x["hypothetical_only"] is not True
                    or type(x["position"]) is not int or not 0<=x["position"]<3
                    or x["order"] not in ORDERS
                    or x.get("offered_actions")!=[
                        ACTIONS[c][i] for i in POSITIONS[x["order"]]]
                    or x["offered_actions"][x["position"]]!=x["choice"]
                    or x["scores"][x["choice"]]+1e-9<max(x["scores"].values())
                    or not isinstance(x["prompt_control_sha256"],str)
                    or len(x["prompt_control_sha256"])!=64):
                raise PermissionError("Malformed or non-authentic G14 decision")
        for case in CASES:
            for order in ORDERS:
                matched=[by[case,arm,order] for arm in ARMS]
                if len({x["prompt_control_sha256"] for x in matched})!=1:
                    raise PermissionError("Paired presentation/trait text confounded evidence")
                if len({x["evidence_digest"] for x in matched})!=1:
                    raise PermissionError("Original memory/state changed between treatments")
            baseline=by[case,"numeric_original","canonical"]
            repeats_here=[x for x in repeats if x["case"]==case]
            if (len(repeats_here)!=1 or repeats_here[0]["arm"]!="numeric_original"
                    or repeats_here[0]["order"]!="canonical"):
                raise AssertionError("Missing exact-match repeat baseline")
            if (repeats_here[0]["prompt_control_sha256"]!=baseline["prompt_control_sha256"]
                    or repeats_here[0]["offered_actions"]!=baseline["offered_actions"]):
                raise PermissionError("Repeat does not match original inference input")
            for arm in ARMS:
                for action in ACTIONS[case]:
                    positions=[
                        by[case,arm,order]["offered_actions"].index(action)
                        for order in ORDERS
                    ]
                    if sorted(positions)!=[0,1,2]:
                        raise PermissionError("Semantic action not position-balanced")
        results.append((role,by,repeats))

    choices={a:Counter() for a in ARMS}
    by_case={case:{arm:Counter() for arm in ARMS} for case in CASES}
    disagreements=Counter()
    score_shift=defaultdict(list)
    invariant=Counter()
    repeat_controls=Counter()
    position_counts={arm:Counter() for arm in ARMS}
    for role,by,repeats in results:
        for case in CASES:
            for order in ORDERS:
                cell={arm:by[case,arm,order] for arm in ARMS}
                for arm,x in cell.items():
                    choices[arm][x["choice"]]+=1
                    by_case[case][arm][x["choice"]]+=1
                    position_counts[arm][x["position"]]+=1
                pairs=(
                    ("numeric_original","numeric_independent","numeric_trait"),
                    ("prose_original","prose_independent","prose_trait"),
                    ("numeric_original","prose_original","format_original"),
                    ("numeric_independent","prose_independent","format_independent"),
                )
                for a,b,label in pairs:
                    disagreements[label]+=int(cell[a]["choice"]!=cell[b]["choice"])
                    for action in ACTIONS[case]:
                        score_shift[(label,action)].append(
                            cell[b]["scores"][action]-cell[a]["scores"][action]
                        )
            for arm in ARMS:
                invariant[arm]+=int(len({
                    by[case,arm,order]["choice"] for order in ORDERS
                })==1)
            repeat=next(x for x in repeats if x["case"]==case)
            base=by[case,"numeric_original","canonical"]
            repeat_controls["same_choice"]+=int(repeat["choice"]==base["choice"])
            repeat_controls["same_probs_within_0_01"]+=int(all(
                abs(repeat["scores"][key]-base["scores"][key])<.01
                for key in ACTIONS[case]
            ))
    return {
        "schema":2,"status":"six_actor_g14_position_balanced_personality_study",
        "actors":6,"cases":len(CASES),"orders":len(ORDERS),"arms":len(ARMS),
        "native_decider_calls":312,"factorial_calls":288,"repeat_calls":24,
        "matched_actor_case_order_conditions":72,
        "position_balanced":True,
        "hypothetical_only":True,"evennia_world_commands":0,
        "choices_by_arm":{a:dict(choices[a]) for a in ARMS},
        "choices_by_case_arm":{
            case:{arm:dict(by_case[case][arm]) for arm in ARMS} for case in CASES
        },
        "paired_decision_disagreements":dict(disagreements),
        "mean_native_score_shifts":{
            label:{action:sum(v)/len(v) for (lab,action),v in score_shift.items()
                   if lab==label}
            for label in ("numeric_trait","prose_trait",
                          "format_original","format_independent")
        },
        "per_arm_order_invariant_actor_case_treatments":dict(invariant),
        "identical_input_repeat_controls":dict(repeat_controls),
        "chosen_position_by_arm":{a:dict(position_counts[a]) for a in ARMS},
        "scope":[
            "Every arm uses the same actor's authentic, hash-verified private G9 brain.",
            "Trait intervention modifies six numerical starting tendencies as in G13.",
            "Formatting intervention substitutes derived non-imperative prose in the read-only profile component only.",
            "Non-profile prompt bytes, individual memories, observations, and option content are held fixed within each matched condition.",
            "The four cases are newly authored hypotheticals, not witnessed world events.",
            "No Evennia command, relationship state change or equipment result was created.",
            "No minimum behavioral difference is required for a passing model experiment.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    report=assess(args.root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True),
                        encoding="utf-8")
    print(json.dumps(report,sort_keys=True))
    print("OX_G14_SIX_ACTOR_PROFILE_AND_FORMAT_PASS")


if __name__=="__main__":
    main()
