"""G6b: continuous, recipient-scoped, six-account terminal crisis experiment.

Unlike the historical four-choice G6 observer, this drives each authenticated
person until Evennia reports death. No operator-side fatality or cause is read.
The decision to travel is explicit and separate from any world work receipt.
Unchanged evidence does not force another model call or a duplicate command.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import random
import time
import uuid

from ox_ai.agents.crew import CommandOption
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.five_crew_service import FiveCrewSupervisor
from ox_ai.runtime.watch_service import atomic_json

from trial import ROLES, STATIONS, PRIMARY, sensor
from turn_budget import TurnBudget, TurnCapReached
from assessment_payload import compose_assessment

DESTINATIONS = ("Bridge", "Environmental Plant", "Engineering",
                "Cargo Hold", "Crew Mess")
TERMINAL_KINDS = frozenset((
    "terminal_alarm", "terminal_report", "terminal_critical",
    "terminal_order", "terminal_assistance", "terminal_work_result",
    "terminal_death",
))
TIMELIMIT = 230  # Independent wall-clock watchdog for stalled servers.
MAX_TURNS_PER_CHARACTER = 100   # Previous trial peaked at 30 per character.
MAX_TURNS_TOTAL = 480           # Previous complete trial had 137 total.


def urgency(view: dict) -> int:
    """Actor's *noisy* local observations, not operator-side gas truth."""
    oxygen = view["oxygen_kpa"]
    co2 = view["co2_percent"]
    if oxygen <= 10.0 or co2 >= 4.2:
        return 3
    if oxygen <= 12.6 or co2 >= 3.2:
        return 2
    if oxygen <= 15.0 or co2 >= 2.0:
        return 1
    return 0


def valid_options(role: str, view: dict, known: dict) -> list[CommandOption]:
    """World-visible eligibility: keep uncertain *technical* attempts possible."""
    here = view["location"]
    choices = [CommandOption("Monitor the current atmosphere and await evidence", "monitor")]
    # Travelling is itself chosen; no automatic dispatch to a work station.
    for place in DESTINATIONS:
        if place != here:
            choices.append(CommandOption("Travel through ship passages to " + place,
                                         "move:" + place))
    base_station = STATIONS[role]
    if here == base_station:
        choices.append(CommandOption("Inspect local equipment and sensor evidence",
                                     "terminal_survey"))
        action, label = PRIMARY[role]
        if action != "terminal_replace":
            choices.append(CommandOption(label, action))
    if role == "teo" and here == "Environmental Plant":
        choices.append(CommandOption(
            "Independently cross-check A-01's nominal pressure sensor",
            "terminal_crosscheck",
        ))
        # Do NOT suppress cartridge replacement merely because the nominal
        # sensor says healthy; a technician may doubt the sensor itself.
        if view.get("local_cartridge_spares", 0) > 0:
            choices.append(CommandOption(
                "Diagnostically exchange an A-01 cartridge using a real spare",
                "terminal_replace",
            ))
    if (role in ("teo", "captain") and here == "Environmental Plant"
            and view.get("local_reserve_bottles", 0) > 0):
        choices.append(CommandOption(
            "Release one finite emergency breathing-gas reserve bottle",
            "terminal_reserve",
        ))
    if view.get("own_finding") and known.get("last_relayed") != view["own_finding"]:
        choices.append(CommandOption(
            "Transmit new firsthand findings to the crew",
            "terminal_broadcast",
        ))
    if view.get("nearby_living"):
        present = ", ".join(x["role"] for x in view["nearby_living"])
        choices.append(CommandOption(
            "Offer assistance to a physically present colleague: " + present,
            "terminal_comfort",
        ))
    choices.append(CommandOption(
        "Record a provisional assessment subject to new evidence",
        "terminal_assess",
    ))
    choices.append(CommandOption(
        "Preserve an incident record at the current station",
        "terminal_archive",
    ))
    return choices


class AdaptiveGoap:
    """Situation-dependent GOAP goals; no scripted four-phase response table."""

    def __init__(self, role: str):
        self.role = role
        self.attempts = Counter()
        self.last_relayed = ""
        self.command_observation_id = 0
        self.critical_assessed = False
        self.last_archived_stage = -1
        self.last_help_stage = -1
        self.last_assessed_stage = -1
        self.last_assessed_evidence_seq = 0
        self.last_assessed_finding = None
        self.last_assessment_content = None
        self.last_refused_assessment_content = None
        self.last_reported_stage = -1
        self.awaiting_post_exchange_survey = False
        self.post_exchange_surveys = 0

    def state(self) -> dict:
        return {"last_relayed": self.last_relayed}

    def notice(self, selected: str, status: str, view: dict,
               last_event: int, *, assessment: dict | None = None,
               refusal_reason: str = "") -> None:
        # Refusal feedback is scoped to precisely the same authored claim,
        # confidence, interpretation AND evidence. It is not a veto on a
        # genuinely changed reading or a reconsidered interpretation.
        if selected == "terminal_assess" and assessment is not None:
            if status == "succeeded":
                self.last_assessment_content = dict(assessment)
                self.last_refused_assessment_content = None
                self.last_assessed_stage = urgency(view)
                self.last_assessed_evidence_seq = int(assessment["evidence_sequence"])
                self.last_assessed_finding = assessment["finding_digest"]
            elif status == "failed":
                self.last_refused_assessment_content = dict(assessment)
                # The actor did attempt a revision for this risk band; another
                # unchanged opinion should wait, but a new report/reading,
                # proposition or confidence may justify a new attempt.
                self.last_assessed_stage = urgency(view)
                self.last_assessed_evidence_seq = int(assessment["evidence_sequence"])
                self.last_assessed_finding = assessment["finding_digest"]
        if status == "succeeded":
            self.attempts[selected] += 1
            if selected == "terminal_replace":
                # Maintenance success is NOT diagnostic success. Require a
                # fresh independent survey to discover any effect.
                self.awaiting_post_exchange_survey = True
            elif selected == "terminal_survey" and self.awaiting_post_exchange_survey:
                self.awaiting_post_exchange_survey = False
                self.post_exchange_surveys += 1
            if selected == "terminal_broadcast":
                self.last_relayed = view.get("own_finding", "")
                self.last_reported_stage = urgency(view)
            elif selected == "terminal_command":
                self.command_observation_id = last_event
            elif selected == "terminal_archive":
                self.last_archived_stage = urgency(view)
            elif selected == "terminal_comfort":
                self.last_help_stage = urgency(view)
        elif status == "failed":
            # World refusals must not be treated as successful work, but
            # repeated identical attempts should not be a scripted loop.
            self.attempts["failed:" + selected] += 1

    def propose_assessment(self, view: dict, evidence_sequence: int) -> dict:
        band = urgency(view)
        # A subjective, fallible opinion authored from the character's own
        # measured risk and local evidence; not the world's hidden cause.
        propositions = {
            0: "Atmospheric recovery remains uncertain",
            1: "Atmospheric decline requires further investigation",
            2: "Current atmosphere threatens crew survival",
            3: "Immediate atmospheric survival is in doubt",
        }
        confidence = (
            "strong" if band >= 3 else
            "moderate" if band >= 2 else "tentative"
        )
        rationale = (
            "I interpret the local oxygen and CO2 instruments, and the "
            "evidence addressed to me, as grounds for this provisional "
            "assessment. I may revise it after further observation."
        )
        return compose_assessment(
            view, claim=propositions[band], confidence=confidence,
            rationale=rationale, evidence_sequence=evidence_sequence,
        )

    def select(self, view: dict, events: list[dict],
               options: list[CommandOption], last_event: int):
        offered = {x.verb: x for x in options}
        stage = urgency(view)
        location = view["location"]
        people = view.get("nearby_living", [])
        evid = view.get("own_finding", "")
        previously = self.attempts
        candidates: list[tuple[int, str, str]] = []

        def goal(score: int, name: str, action: str) -> None:
            if action in offered:
                candidates.append((score, name, action))

        # GOAP plans across locations rather than teleporting the crew.
        if (stage >= 1 and self.role in ("teo", "captain")
                and not previously["terminal_reserve"]
                and not previously["failed:terminal_reserve"]):
            if location == "Environmental Plant":
                goal(180 + stage * 5, "buy_breathing_time", "terminal_reserve")
            else:
                goal(160 + stage * 5, "reach_breathing_reserves",
                     "move:Environmental Plant")

        if (self.role == "teo" and location == "Environmental Plant"
                and self.awaiting_post_exchange_survey):
            goal(220, "measure_after_cartridge_exchange", "terminal_survey")
        if location == STATIONS[self.role] and not previously["terminal_survey"]:
            goal(170, "establish_personal_evidence", "terminal_survey")

        if self.role == "captain" and location == "Bridge":
            novel = last_event > self.command_observation_id
            if not previously["terminal_command"] or novel and stage >= 2:
                goal(145, "coordinate_new_evidence", "terminal_command")

        # The nominal A-01 sensor might itself be wrong. GOAP can test a
        # *hypothesis*, not simply read "nominal" as a prohibition.
        if self.role == "teo" and location == "Environmental Plant" and evid:
            if not previously["terminal_crosscheck"]:
                goal(140, "verify_contested_instrument", "terminal_crosscheck")
            elif (not previously["terminal_replace"]
                  and not previously["failed:terminal_replace"]
                  and view.get("local_cartridge_spares", 0) > 0):
                goal(95, "test_cartridge_hypothesis", "terminal_replace")

        if evid and self.last_relayed != evid:
            goal(150, "share_new_primary_evidence", "terminal_broadcast")

        received_diagnostic = any(e["kind"] == "terminal_report" for e in events)
        critical = any(e["kind"] == "terminal_critical" for e in events)
        proposal = self.propose_assessment(view, last_event)
        # Risk transitions and newly addressed evidence legitimately change
        # a prognosis. Compare the complete assessment, never merely a verb
        # or a local inspection/message cursor.
        substantive_trigger = (
            stage != self.last_assessed_stage
            or last_event > self.last_assessed_evidence_seq
            or proposal["finding_digest"] != self.last_assessed_finding
            or (
                self.last_assessment_content is not None
                and any(proposal[k] != self.last_assessment_content[k]
                        for k in ("claim", "confidence", "rationale"))
            )
        )
        not_same_payload = (
            proposal != self.last_assessment_content
            and proposal != self.last_refused_assessment_content
        )
        if ((received_diagnostic or stage >= 2)
                and substantive_trigger and not_same_payload):
            goal(115 if critical else 75, "update_provisional_assessment",
                 "terminal_assess")

        if self.last_archived_stage != stage and stage >= 1:
            goal(65, "preserve_changing_incident_record", "terminal_archive")

        if people and stage >= 2 and self.last_help_stage != stage:
            goal(55, "assist_co_located_crew", "terminal_comfort")

        goal(1, "observe_and_reconsider", "monitor")
        candidates.sort(key=lambda c: (-c[0], c[1]))
        chosen = candidates[0]
        # The planner authorises the selected *verb* from actor-visible
        # preconditions. This is a genuine planner but not generic AGI.
        facts = {"conscious", "authenticated", "alarm"}
        if location == "Environmental Plant":
            facts.add("at_environmental")
        actions = [
            GoapAction(
                verb, requires=frozenset({"conscious"}),
                adds=frozenset({verb}), verb=verb,
                cost=1 if verb != "monitor" else 3,
            ) for verb in offered
        ]
        planned = GoapPlanner(actions).plan(facts, {chosen[2]})
        if not planned.actions or planned.actions[0].verb not in offered:
            raise AssertionError("GOAP tried action outside actor's menu")
        option = offered[planned.actions[0].verb]
        return option, {
            "goal": chosen[1], "priority": chosen[0], "risk_band": stage,
            "source": "personal_facts_and_GOAP",
        }


async def experiment(seed: int, provider: str, destination: Path) -> None:
    if provider not in ("goap", "gemini"):
        raise ValueError("Explicit provider required")
    if os.environ.get("OX_TERMINAL_LIVE_CI") != "1":
        raise RuntimeError("Disposable live-server opt-in required")
    if os.environ.get("OX_CAPTAIN_OVERSIGHT") != "1":
        raise RuntimeError("Six authenticated crew are required")
    supervisor = FiveCrewSupervisor()
    if set(supervisor.ids) != set(ROLES) or len(set(supervisor.ids.values())) != 6:
        raise PermissionError("Every character requires distinct authenticated identity")

    randomizer = random.Random(seed)
    startup_offsets = {role: randomizer.uniform(0.15, 1.3) for role in ROLES}
    pulse = {role: randomizer.uniform(1.2, 2.5) for role in ROLES}
    records: list[dict] = []
    fatal_confirmations: dict[str, bool] = {}
    heard_critical: dict[str, bool] = {role: False for role in ROLES}
    budget = TurnBudget(
        ROLES, max_per_character=MAX_TURNS_PER_CHARACTER,
        max_total=MAX_TURNS_TOTAL,
    )
    stop_requested = asyncio.Event()
    stopped_for_limit: dict[str, str | None] = {"reason": None}
    started = time.monotonic()

    def claim_turn(role: str) -> int | None:
        try:
            return budget.claim(role)
        except TurnCapReached as error:
            stopped_for_limit["reason"] = str(error)
            stop_requested.set()
            return None

    async def role_loop(role: str) -> None:
        await asyncio.sleep(startup_offsets[role])
        client = supervisor.clients[role]
        brain = supervisor.brains[role]
        policy = AdaptiveGoap(role)
        last_sequence = 0
        last_evidence_sequence = 0
        previous_band = -1
        last_decision_world_minute = -100
        work_index = 0
        seen_death = False

        while True:
            if stop_requested.is_set():
                break
            if time.monotonic() - started > TIMELIMIT:
                raise TimeoutError("World did not reach fatal state in time")
            events = await supervisor.read_inbox(role)
            relevant = [
                event for event in events
                if event["kind"] in TERMINAL_KINDS
                and int(event["sequence"]) > last_sequence
            ]
            if relevant:
                last_sequence = max(int(x["sequence"]) for x in relevant)
                evidence_events = [
                    x for x in relevant
                    if x["kind"] in (
                        "terminal_alarm", "terminal_report", "terminal_critical",
                        "terminal_assistance",
                    )
                ]
                if evidence_events:
                    last_evidence_sequence = max(
                        last_evidence_sequence,
                        *(int(x["sequence"]) for x in evidence_events),
                    )
                heard_critical[role] |= any(
                    x["kind"] == "terminal_critical" for x in relevant
                )
            current = await sensor(client)
            if current["status"] == "dead":
                seen_death = True
                break
            level = urgency(current)
            # Reconsider on a new addressed event, changed sensor urgency,
            # or a periodic personal watch. No fixed count or phase cutoff.
            significant = bool(relevant) or level != previous_band or (
                current["minute"] - last_decision_world_minute >= 18
            )
            if not significant:
                await asyncio.sleep(pulse[role])
                continue
            # A ceiling is a harness safeguard, not simulated fatigue.
            # Preserve an explicit stopped/incomplete experiment instead
            # of claiming that characters died or that the task passed.
            actor_turn = claim_turn(role)
            if actor_turn is None:
                break
            previous_band = level
            menu = valid_options(role, current, policy.state())
            if provider == "goap":
                selected, why = policy.select(
                    current, events, menu, last_evidence_sequence,
                )
            else:
                brain.observe_local("Live authenticated atmosphere", json.dumps(
                    current, sort_keys=True,
                ))
                proposal = await supervisor.cognition.decide(role, brain.agent, menu)
                selected = next(x for x in menu if x.verb == proposal.verb)
                brain.selected_procedure(proposal)
                why = {"source": "Concordia_bounded_choice", "risk_band": level}
            entry = {
                "role": role, "character_dbref": client.character_dbref,
                "turn_number": actor_turn, "world_minute": current["minute"],
                "oxygen_kpa": current["oxygen_kpa"],
                "location": current["location"], "status": "alive",
                "decision": selected.verb, "reasoning": why,
                "newly_addressed": [x["kind"] for x in relevant],
                "heard_critical_at_choice": heard_critical[role],
                "actor_evidence": current.get("own_finding", ""),
                "kind": "monitor" if selected.verb == "monitor" else (
                    "travel" if selected.verb.startswith("move:") else "work"
                ),
            }
            last_decision_world_minute = current["minute"]
            if selected.verb == "monitor":
                entry["result"] = "waiting_for_new_evidence"
            elif selected.verb.startswith("move:"):
                place = selected.verb.partition(":")[2]
                if place not in DESTINATIONS:
                    raise PermissionError("Agent invented an unreachable station")
                await supervisor.ensure_station(role, place)
                actual = await sensor(client)
                if actual["location"] != place:
                    raise AssertionError("Movement choice did not reach world station")
                entry["result"] = "arrived"
                entry["arrived_at"] = actual["location"]
            else:
                request_id = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"g6b:{current['case_id']}:{role}:{work_index}",
                ).hex
                work_index += 1
                entry["receipt_id"] = request_id
                assessment = (
                    policy.propose_assessment(current, last_evidence_sequence)
                    if selected.verb == "terminal_assess" else None
                )
                if assessment is not None:
                    entry["assessment"] = dict(assessment)
                actual = await DurableEvenniaPort(client).submit_work(ActionRequest(
                    request_id, client.character_dbref, selected.verb, "ship",
                    arguments=assessment or {},
                ))
                if actual.status == "unknown":
                    actual = await DurableEvenniaPort(client).reconcile_work(request_id)
                entry["result"] = actual.status
                entry["receipt_reason"] = actual.description
                entry["source_event_id"] = actual.source_event_id
                policy.notice(
                    selected.verb, actual.status, current,
                    last_evidence_sequence, assessment=assessment,
                    refusal_reason=actual.description,
                )
            records.append(entry)
            await asyncio.sleep(pulse[role])
        fatal_confirmations[role] = seen_death

    try:
        await supervisor.open()
        async with asyncio.timeout(TIMELIMIT + 25):
            await asyncio.gather(*(role_loop(role) for role in ROLES))
        all_dead = (
            set(fatal_confirmations) == set(ROLES)
            and all(fatal_confirmations.values())
        )
        termination_reason = (
            "all_six_world_confirmed_deaths" if all_dead else
            stopped_for_limit["reason"] or "incomplete"
        )
        summary = {
            "controller": provider, "seed": seed,
            "connected_characters": dict(supervisor.ids),
            "decisions": sorted(
                records, key=lambda d: (d["world_minute"], d["role"]),
            ),
            "all_six_confirmed_dead": all_dead,
            "termination_reason": termination_reason,
            "turn_count": budget.total,
            "turn_counts_by_role": dict(budget.counts),
            "turn_limits": {
                "per_character": MAX_TURNS_PER_CHARACTER,
                "total": MAX_TURNS_TOTAL,
            },
            "heard_critical": heard_critical,
            "inference_calls": sum(b.inference_calls for b in supervisor.brains.values()),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "turn_cap_reached": stopped_for_limit["reason"] is not None,
        }
        if provider == "goap" and summary["inference_calls"] != 0:
            raise AssertionError("GOAP must never query a generative model")
        if provider == "gemini" and not summary["inference_calls"]:
            raise AssertionError("Gemini must invoke the actual provider")
        atomic_json(destination, summary)
        if not all_dead:
            print(
                "OX_G6B_EXPERIMENT_INCOMPLETE",
                termination_reason, provider, seed, len(records), flush=True,
            )
            raise RuntimeError(
                "Scenario ended without six verified world deaths: "
                + termination_reason
            )
        print("OX_G6B_CONTINUOUS_SIX_CREW_PASS", provider, seed, len(records), flush=True)
    finally:
        atomic_json(Path(".ox-state/g6b-partial.json"), {
            "seed": seed, "controller": provider, "decisions": records,
            "fatal_confirmations": fatal_confirmations,
            "heard_critical": heard_critical,
            "termination_reason": stopped_for_limit["reason"],
            "turn_count": budget.total,
            "turn_counts_by_role": dict(budget.counts),
            "turn_limits": {
                "per_character": MAX_TURNS_PER_CHARACTER,
                "total": MAX_TURNS_TOTAL,
            },
        })
        await supervisor.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("goap", "gemini"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, default=Path(".ox-state/g6b-handler.json"))
    args = parser.parse_args()
    asyncio.run(experiment(args.seed, args.provider, args.out))


if __name__ == "__main__":
    main()
