"""Counterfactual native-Concordia model comparison on actor-visible evidence.

Each of 24 independent authored situations has two plausible but materially
different observations and a fixed finite action menu. Only the evidence
changes across a pair. The expected action reverses; this is not a real-world
behavioural benchmark or proof of world action success.

Runs one *augmented-memory* native Concordia decision per scenario/variant:
48 real model requests total, no world commands. Existing G11 handles memory A/B.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import statistics
import time

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.memory.seeds import SeededMemory
from ox_ai.ports.base import WorldObservation


@dataclass(frozen=True)
class Case:
    name: str
    category: str
    recollection: str
    earlier: str
    changed: str
    first_option: str
    first_verb: str
    second_option: str
    second_verb: str
    expected_earlier: str
    expected_changed: str

    def __post_init__(self):
        assert self.expected_earlier != self.expected_changed
        assert self.expected_earlier in (self.first_verb, self.second_verb)
        assert self.expected_changed in (self.first_verb, self.second_verb)
        assert self.first_verb != self.second_verb


def fixtures() -> tuple[Case, ...]:
    """Twenty-four curated evidence flips: no duplicated wording across cases."""
    rows = (
        ("watch_swap", "commitment", "Mara offered to exchange tomorrow's watch.",
         "Mara confirmed she can still take the watch tomorrow.",
         "Mara explicitly withdrew tomorrow's watch-swap offer.",
         "Confirm the agreed watch swap", "confirm",
         "Ask for a replacement arrangement", "rearrange", "confirm", "rearrange"),
        ("coolant_pressure", "equipment", "P-01 had stable pressure yesterday.",
         "Direct P-01 gauge reading is within the nominal band now.",
         "Direct P-01 gauge reading is below the nominal band now.",
         "Log the nominal pressure", "log",
         "Investigate falling pressure", "investigate", "log", "investigate"),
        ("sensor_disagreement", "evidence", "The pressure sensor occasionally drifts.",
         "The calibrated handheld gauge agrees with the panel sensor.",
         "The calibrated handheld gauge contradicts the panel sensor.",
         "Use the corroborated reading", "use_reading",
         "Recheck the discrepant instruments", "recheck", "use_reading", "recheck"),
        ("air_spare", "inventory", "Atmosphere filters sometimes run out.",
         "Local inventory confirms one intact spare cartridge is present.",
         "Local inventory confirms there is no spare cartridge here.",
         "Prepare the available cartridge for authorised work", "prepare",
         "Request a replacement cartridge first", "request", "prepare", "request"),
        ("isolation_clearance", "permission", "P-01 requires chief release for isolation.",
         "A valid chief-engineer isolation release was received for this task.",
         "The requested chief-engineer isolation release was refused.",
         "Submit the scoped isolation request", "isolate",
         "Ask the chief to review alternatives", "review", "isolate", "review"),
        ("lost_ack", "recovery", "A pump inspection command was previously submitted.",
         "The authenticated world receipt confirms the inspection succeeded.",
         "No authenticated receipt was received; completion is unknown.",
         "Proceed using the verified inspection result", "proceed",
         "Reconcile the original request ID without retrying blindly", "reconcile",
         "proceed", "reconcile"),
        ("cargo_restraint", "equipment", "Cargo C-01 restraints were secure at loading.",
         "Today's direct restraint check found every bracket secure.",
         "Today's direct restraint check found one bracket loose.",
         "Report that this check found no loose restraint", "report_nominal",
         "Investigate and report the loose restraint", "investigate",
         "report_nominal", "investigate"),
        ("private_letter", "privacy", "Teo once trusted me with a personal letter.",
         "Teo explicitly authorised sharing his letter with Mara.",
         "Teo explicitly refused permission to share his letter with Mara.",
         "Share the letter with the intended recipient", "share",
         "Keep the letter confidential", "withhold", "share", "withhold"),
        ("watch_reassignment", "commitment", "Iona requested a watch handover.",
         "The assigned relief officer explicitly accepted the handover.",
         "The assigned relief officer said they could not accept the handover.",
         "Record the accepted duty transfer", "transfer",
         "Find confirmed relief before transfer", "find_relief", "transfer", "find_relief"),
        ("repeat_refusal", "repetition", "My request to Mara for an extra shift was refused.",
         "Mara reports a new available shift and invites the same request.",
         "Mara refused the identical request again; nothing has changed.",
         "Submit the newly invited request", "ask_again",
         "Seek genuinely new information rather than repeat", "seek_info",
         "ask_again", "seek_info"),
        ("medical_triage", "medical", "A crewmate has intermittently felt unwell.",
         "The medical monitor shows ordinary pulse and responsive breathing.",
         "The medical monitor shows absent breathing and an unresponsive patient.",
         "Schedule a routine medical check", "routine",
         "Trigger the emergency medical response", "emergency", "routine", "emergency"),
        ("hatch_access", "permission", "The engineering hatch requires an authorisation check.",
         "The access panel grants this person's hatch passage now.",
         "The access panel denies this person's hatch passage now.",
         "Use the authorised hatch", "traverse",
         "Request an authorised route", "request_access", "traverse", "request_access"),
        ("radio_reply", "communication", "Bridge requested an updated distress acknowledgement.",
         "A matching authenticated reply was received and verified.",
         "There is still no matching authenticated reply.",
         "File the verified acknowledgement", "file_ack",
         "Continue communication follow-up", "follow_up", "file_ack", "follow_up"),
        ("spares_priority", "resources", "There is one reserve atmospheric cartridge.",
         "The primary cartridge failed and no other working unit is available.",
         "The primary cartridge is healthy and reserve stock is untouched.",
         "Assign the reserve to the confirmed emergency", "allocate",
         "Keep the reserve for future confirmed needs", "conserve",
         "allocate", "conserve"),
        ("fire_alarm", "equipment", "One fire alarm had produced a spurious signal.",
         "Direct inspection confirms no fire, smoke or abnormal heat.",
         "Direct inspection confirms spreading smoke and abnormal heat.",
         "Report the inspected alarm as false", "report_false",
         "Invoke the real fire response", "fire_response", "report_false", "fire_response"),
        ("qualified_worker", "permission", "A specialised cooling repair needs a trained technician.",
         "The proposed worker's world skill record confirms the required qualification.",
         "The proposed worker's world skill record shows no required qualification.",
         "Assign work to the verified qualified technician", "assign",
         "Find a qualified technician", "find_worker", "assign", "find_worker"),
        ("handover_ack", "recovery", "The outgoing watch submitted a handover summary.",
         "The incoming officer acknowledged the exact handover ID.",
         "The incoming officer has not acknowledged the handover ID.",
         "Close the acknowledged handover", "close_handover",
         "Request receipt confirmation", "request_ack",
         "close_handover", "request_ack"),
        ("crew_health_privacy", "privacy", "The doctor gave me a sensitive medical update.",
         "The patient approved a limited medical briefing for the captain.",
         "The patient denied permission for a nonessential medical briefing.",
         "Pass along the explicitly authorised briefing", "brief",
         "Respect the patient's confidentiality", "withhold",
         "brief", "withhold"),
        ("inspection_superseded", "evidence", "An old report stated the pressure valve was sound.",
         "A new direct inspection confirms the valve is still sound.",
         "A new direct inspection finds a crack in that valve.",
         "Retain the now-corroborated valve report", "retain",
         "Revise the valve assessment with new evidence", "revise",
         "retain", "revise"),
        ("agreement_revision", "commitment", "Mara and I agreed to meet for dinner.",
         "Mara reaffirmed the agreed dinner time without changes.",
         "Mara says she is unavailable and asks to change the dinner time.",
         "Keep the reaffirmed dinner arrangement", "keep",
         "Negotiate another time", "negotiate", "keep", "negotiate"),
        ("chief_clearance", "permission", "Commissioning the pump needs a fresh chief release.",
         "A valid signed commissioning release was delivered for this pump.",
         "The commissioning release has expired and was not renewed.",
         "Request the approved commissioning step", "commission",
         "Request renewed clearance", "renew", "commission", "renew"),
        ("cooldown", "equipment", "The motor requires cooling after high load.",
         "A direct motor temperature reading is below its safe restart threshold.",
         "A direct motor temperature reading is above its safe restart threshold.",
         "Request restart of the cooled motor", "restart",
         "Wait and reinspect temperature", "wait", "restart", "wait"),
        ("deadline", "time", "The replacement filter must be checked on a schedule.",
         "The authenticated ship clock shows the check is due right now.",
         "The authenticated ship clock shows the check is due tomorrow.",
         "Perform the scheduled check now", "check_now",
         "Preserve the future appointment", "schedule", "check_now", "schedule"),
        ("route_blocked", "navigation", "The direct route to Cargo passes through a sealed hatch.",
         "The local hatch display shows the direct route is open and passable.",
         "The local hatch display shows the direct route is closed and locked.",
         "Use the now-open direct passage", "direct",
         "Find a permitted alternate route", "alternate", "direct", "alternate"),
    )
    return tuple(Case(*row) for row in rows)


def make_agent(case: Case, variant: str, model, *, memory_enabled: bool = True):
    if variant not in ("earlier", "changed"):
        raise ValueError("Unknown evidence state")
    options = (
        CommandOption(case.first_option, case.first_verb),
        CommandOption(case.second_option, case.second_verb),
    )
    agent = CrewAgent(
        CrewIdentity(
            agent_id="ox.counterfactual.officer", character_id="#77",
            name="Probe Officer",
            duty="Consider only character-observed information and permissions",
            goal="Choose a justified next attempt without asserting completion",
        ),
        model,
        initial_memories=(
            SeededMemory("cf." + case.name, case.recollection, "watch",
                         occurred_turn=-30),
        ),
        memory_projection_enabled=memory_enabled,
    )
    text = case.earlier if variant == "earlier" else case.changed
    obs_id = "cf." + case.name + "." + variant
    if not agent.observe(WorldObservation(
        obs_id, "#77", 10.0, text, source_event_id=obs_id,
    )):
        raise AssertionError("Fixture observation was not accepted")
    return agent, options


def run(provider: str, model_id: str, *, api_base: str,
        max_pairs: int = 24) -> dict:
    if type(max_pairs) is not int or not 1 <= max_pairs <= 24:
        raise ValueError("Pair limit must be between 1 and 24")
    if provider == "ollaya":
        from scenarios.decision_models_trial import (
            MODELS, OllayaChoiceModel, localhost_api,
        )
        if model_id not in MODELS:
            raise ValueError("Not an allowed Ollaya decision model")
        endpoint = localhost_api(api_base)

        def mk(options):
            return OllayaChoiceModel(model_id, tuple(o.label for o in options),
                                     endpoint, timeout=(600 if model_id == "decider:4b" else 180))
    elif provider == "qwen-local":
        from urllib.parse import urlsplit
        from ox_ai.inference.compatible_chat import CompatibleChatModel
        parsed = urlsplit(api_base)
        if (parsed.scheme != "http"
                or parsed.hostname not in ("127.0.0.1", "localhost")
                or parsed.path.rstrip("/") != "/v1"
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
            raise ValueError("Qwen requires a localhost HTTP /v1 API")
        if model_id not in ("qwen3.5-0.8b", "qwen3.5-4b"):
            raise ValueError("Unrecognised local Qwen model")

        def mk(options):
            return CompatibleChatModel(model_id, api_key="local-no-secret",
                                       api_base=api_base)
    elif provider == "capture":
        from scenarios.g11_memory_ab_trial import CaptureModel
        if model_id != "capture":
            raise ValueError("Capture provider uses the capture model only")

        def mk(options):
            return CaptureModel()
    else:
        raise ValueError("Unsupported provider")
    results = []
    for case in fixtures()[:max_pairs]:
        for variant in ("earlier", "changed"):
            # Both variants see the same recollection and options; only one
            # addressed observation differs. No world port is constructed.
            options = (
                CommandOption(case.first_option, case.first_verb),
                CommandOption(case.second_option, case.second_verb),
            )
            model = mk(options)
            brain, offered = make_agent(case, variant, model)
            start = time.perf_counter()
            request = brain.decide(offered, expected_revision=1)
            latency = round(time.perf_counter() - start, 4)
            if len(brain.pending_requests) != 1 or brain.usage.total_calls != 1:
                raise AssertionError("One inference must yield one pending proposal")
            if request.character_id != "#77" or request.agent_revision != 1:
                raise AssertionError("Character or revision mismatch")
            expected = (case.expected_earlier if variant == "earlier"
                        else case.expected_changed)
            row = {
                "case": case.name, "category": case.category,
                "variant": variant, "expected_verb": expected,
                "chosen_verb": request.verb, "match": request.verb == expected,
                "latency_seconds": latency, "world_commands_sent": 0,
            }
            if provider == "ollaya":
                row["decision"] = model.last_answer
            results.append(row)
    evaluated = len(results) // 2
    pairs = []
    for i in range(evaluated):
        a, b = results[2*i:2*i+2]
        pairs.append({
            "case": a["case"], "category": a["category"],
            "both_correct": a["match"] and b["match"],
            "changed_decision": a["chosen_verb"] != b["chosen_verb"],
        })
    return {
        "experiment": "ox_counterfactual_choices_v1",
        "provider": provider,
        "model": model_id,
        "real_model": provider != "capture",
        "pairs": evaluated,
        "decisions": len(results),
        "expected_match_rate": sum(row["match"] for row in results) / len(results),
        "counterfactual_pair_success_rate": (
            sum(p["both_correct"] for p in pairs) / len(pairs)
        ),
        "changed_decision_rate": (
            sum(p["changed_decision"] for p in pairs) / len(pairs)
        ),
        "median_latency_seconds": statistics.median(
            row["latency_seconds"] for row in results
        ),
        "records": results,
        "pair_records": pairs,
        "world_commands_sent": 0,
        "world_receipts_received": 0,
        "limitations": (
            "24 authored pairs, deterministic phrasing, no live world. "
            "A correct choice in one variant is insufficient: both must match."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("ollaya", "qwen-local", "capture"),
                        required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:11435")
    parser.add_argument("--max-pairs", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.provider, args.model, api_base=args.api_base,
                 max_pairs=args.max_pairs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k in (
        "experiment", "model", "pairs", "decisions", "expected_match_rate",
        "counterfactual_pair_success_rate", "changed_decision_rate",
        "median_latency_seconds",
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
