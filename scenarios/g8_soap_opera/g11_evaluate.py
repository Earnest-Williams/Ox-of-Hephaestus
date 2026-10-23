"""Verify G11 real Evennia agreement outcomes, receipt ownership and memory.

This covers only explicit opted-in world-backed Decider/GOAP social replies.
Each verified resulting *state transition* is from Evennia, not a model's
claim. Delegation to Decider is never permission to bypass the social port.
"""
from __future__ import annotations

import argparse
from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


def load_g9_evaluator():
    spec=spec_from_file_location(
        "ox_g9_evaluator",Path(__file__).with_name("g9_evaluate.py"),
    )
    module=module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(root: Path, *, turns: int=205) -> dict:
    state=json.loads((root/"state.json").read_text(encoding="utf-8"))
    if (state.get("cognition_mode") != "decider"
            or state.get("contract_routing") is not True
            or state.get("turn") != turns
            or len(state.get("trace",())) != turns):
        raise PermissionError("G11 requires completed opt-in real-world experiment")
    # Existing G9 invariant checks include all six independently checkpointed
    # characters, verified speech provenance, actual maintenance receipts, and
    # the final world/GOAP conversation trace.
    base=load_g9_evaluator().evaluate(root, turns=turns)
    audits=state.get("contract_audit")
    if not isinstance(audits,list) or not audits:
        raise AssertionError("No real-world contracted model/GOAP boundary exercised")
    if len(audits)!=len({x["turn"] for x in audits}):
        raise AssertionError("Duplicate real commitment boundary")
    counters=Counter()
    keys=set()
    work_events=set()
    heard_by={}
    for row in state["trace"]:
        if not row["kind"].startswith("spoken_"):
            continue
        for listener in row.get("heard_by",()):
            if listener != row["actor"]:
                heard_by[(listener,"g8-speech-"+str(row["turn"])+"-"+row["actor"])] = row["turn"]
    for audit in audits:
        role=audit["actor"]
        other=audit["counterpart"]
        turn=audit["turn"]
        if (role == other or role not in base["actors"] or other not in base["actors"]
                or not 1<=turn<=turns):
            raise PermissionError("Cross-character world agreement audit")
        trace=state["trace"][turn-1]
        if (trace["actor"]!=role or trace["kind"]!="relationship_"+audit["chosen"]
                or trace.get("g11_contract")!=audit
                or trace.get("agreement")!=audit["agreement_id"]
                or trace.get("receipt")!=audit["world_request_id"]
                or trace.get("listener_event")!=audit["counterpart_event_id"]):
            raise AssertionError("World-authenticated reply disagrees with chosen action")
        if audit["chosen"] not in ("accept","defer","decline"):
            raise AssertionError("Unrecognized relationship transition")
        if audit["baseline"] not in ("accept","defer","decline"):
            raise AssertionError("No meaningful symbolic GOAP baseline")
        if audit["deviated"] != (audit["baseline"]!=audit["chosen"]):
            raise AssertionError("Reported deviation not associated with chosen reply")
        if audit["route"] not in ("goap","llm"):
            raise AssertionError("Unrecognized personality route")
        if audit["model_calls"]!=int(audit["route"]=="llm"):
            raise AssertionError("Model invocation quota not correctly recorded")
        if (not isinstance(audit.get("world_request_id"),str)
                or not isinstance(audit.get("world_event_id"),str)
                or not isinstance(audit.get("counterpart_event_id"),str)
                or not all((audit["world_request_id"],audit["world_event_id"],
                            audit["counterpart_event_id"]))):
            raise AssertionError("Incomplete authoritative evidence triplet")
        if audit["world_request_id"] in keys or audit["world_event_id"] in work_events:
            raise AssertionError("Duplicate server-accepted world reply or receipt")
        keys.add(audit["world_request_id"])
        work_events.add(audit["world_event_id"])
        if (audit["route"]=="llm") != bool(audit.get("proposal_request_id")):
            raise AssertionError("Unowned Decider proposal was adopted")
        for source in audit["latest_peer_evidence"]:
            heard_turn=heard_by.get((role,source))
            if heard_turn is None or heard_turn>=turn:
                raise PermissionError("Agent's decision cited speech it never heard")
        counters[audit["route"]]+=1
        counters["action_"+audit["chosen"]]+=1
        counters["actor_"+role]+=1
        counters["departures"]+=int(audit["deviated"])
    if sum(counters[x] for x in ("llm","goap")) != len(audits):
        raise AssertionError("Incomplete personality split")
    if len(base["verified_world_work"])!=5:
        raise AssertionError("Maintenance recovery did not retain world authority")
    report={
        "schema":1, "status":"real_evennia_g11_verified",
        "seed":state["seed"],"turns":turns,
        "six_distinct_actors":len(base["actors"]),
        "world_maintenance_receipts":len(base["verified_world_work"]),
        "real_agreement_receipts":len(audits),
        "selected_model_calls":counters["llm"],
        "goap_replies":counters["goap"],
        "different_from_goap":counters["departures"],
        "responses":{a:counters["action_"+a] for a in ("accept","defer","decline")},
        "actor_replies":{r:counters["actor_"+r] for r in base["actors"]},
        "actual_world_social_proofs":[
            {"turn":x["turn"],"actor":x["actor"],"counterpart":x["counterpart"],
             "route":x["route"],"baseline":x["baseline"],"chosen":x["chosen"],
             "request_id":x["world_request_id"],
             "source_event_id":x["world_event_id"],
             "counterpart_event_id":x["counterpart_event_id"]}
            for x in audits
        ],
        "scope":[
            "Real server-verified reply and separate addressed counterpart event.",
            "A socially awkward reply is not automatically an error.",
            "Private memories and GOAP route records remain actor scoped.",
            "No dangerous physical operation was selected by this model path.",
            "The chosen social result is actual Evennia state, not an invented consequence.",
        ],
    }
    (root/"g11-report.json").write_text(
        json.dumps(report,indent=2,sort_keys=True),encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--turns",type=int,default=205)
    args=parser.parse_args()
    report=evaluate(args.root,turns=args.turns)
    print(json.dumps({k:v for k,v in report.items() if k in (
        "seed","turns","world_maintenance_receipts","real_agreement_receipts",
        "selected_model_calls","goap_replies","different_from_goap",
        "responses","actor_replies",
    )},sort_keys=True))
    print("OX_G11_AUTHENTIC_WORLD_SOCIAL_PASS")


if __name__=="__main__":
    main()
