"""Six real Evennia clients investigate a world-owned, fatal atmosphere incident.

Disposable CI run. No handler accesses world models or operator-only cause.
The scenario admits only world-authorised commands through actual sessions.
"""
from __future__ import annotations

import argparse
import asyncio
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

ROLES = ("lin", "ari", "iona", "mara", "teo", "captain")
STATIONS = {
    "lin": "Bridge", "ari": "Engineering", "iona": "Engineering",
    "mara": "Cargo Hold", "teo": "Environmental Plant",
    "captain": "Bridge",
}
PRIMARY = {
    "lin": ("terminal_route", "Look for an immediate diversion or rescue on bridge navigation"),
    "ari": ("terminal_reroute", "Try the engineering bypass line"),
    "iona": ("terminal_patch", "Attempt a pressure repair with shipboard tooling"),
    "mara": ("terminal_search", "Check freight for a usable safe refuge"),
    "teo": ("terminal_replace", "Try the atmosphere cartridge replacement procedure"),
    "captain": ("terminal_command", "Direct specialists to investigate and seek help"),
}


def choices(role):
    primary, label = PRIMARY[role]
    result = [
        CommandOption("Conduct my own local instrument survey", "terminal_survey"),
        CommandOption(label, primary),
    ]
    if role in ("teo", "captain"):
        result.append(CommandOption(
            "Discharge one finite emergency atmosphere reserve bottle", "terminal_reserve",
        ))
    return result + [
        CommandOption("Broadcast my actual verified finding to the other crew", "terminal_broadcast"),
        CommandOption("File a provisional assessment that recovery is impossible", "terminal_assess"),
        CommandOption("Preserve the ship's incident log for later investigation", "terminal_archive"),
        CommandOption("Provide direct assistance to another crew member nearby", "terminal_comfort"),
    ]


async def sensor(client):
    await client.send_line("oxterminal")
    async with asyncio.timeout(12):
        for _ in range(200):
            pkt = await client.receive()
            if pkt.kind != "ox_terminal":
                continue
            if len(pkt.args) != 1 or not isinstance(pkt.args[0], dict):
                raise ValueError("Malformed authenticated ship sensor response")
            data = pkt.args[0]
            if data.get("character_dbref") != client.character_dbref:
                raise PermissionError("Sensor belongs to another crew member")
            if not isinstance(data.get("minute"), int) or data.get("minute") < 0:
                raise ValueError("Malformed world incident time")
            if "cause" in data or "operator_only_hidden_cause" in data:
                raise PermissionError("World secret leaked to a crew member")
            return data
    raise RuntimeError("World sensor OOB frame not received")


class LocalGoap:
    """GOAP control using *only* this person's authenticated views and events."""

    def __init__(self, role):
        self.role = role
        self.beliefs = {"notified"}

    def notice(self, verb, status):
        fact = {
            "terminal_survey": "surveyed",
            "terminal_broadcast": "reported",
            "terminal_assess": "assessed",
            "terminal_reserve": "reserved",
            "terminal_command": "commanded",
            "terminal_archive": "archived",
            "terminal_comfort": "assisted",
            PRIMARY[self.role][0]: "primary_attempted",
        }.get(verb)
        if fact:
            self.beliefs.add(fact)
        if status == "failed":
            self.beliefs.add("last_action_failed")

    def choose(self, view, events, options):
        facts = self.beliefs
        evidence = str(view.get("own_finding", "")).lower()
        if self.role == "iona" and "inaccessible" in evidence:
            facts.add("personal_workaround_ruled_out")
        if self.role == "ari" and "rejoins" in evidence:
            facts.add("personal_workaround_ruled_out")
        if self.role == "teo" and "nominal" in evidence:
            facts.add("personal_workaround_ruled_out")
        if self.role == "mara" and "not rated" in evidence:
            facts.add("personal_workaround_ruled_out")
        if self.role == "lin" and "no reachable port" in evidence:
            facts.add("personal_workaround_ruled_out")
        if view["oxygen_kpa"] < 15.0 or view["co2_percent"] > 2.5:
            facts.add("air_critical")
        for evt in events:
            if evt["kind"] == "terminal_report" and (
                "Fracture echoes" in evt["text"]
                or "damaged shared manifold" in evt["text"]
            ):
                facts.add("reported_structural_problem")

        available = {o.verb for o in options}
        actions = [
            GoapAction(
                option.verb,
                requires=frozenset({"notified"}),
                adds=frozenset({f"done_{option.verb}"}),
                verb=option.verb,
                cost=1,
            )
            for option in options
        ]
        primary = PRIMARY[self.role][0]
        if "surveyed" not in facts:
            proposed = "terminal_survey"
        elif self.role == "captain" and "commanded" not in facts:
            proposed = "terminal_command"
        elif (self.role in ("teo", "captain") and "air_critical" in facts
              and "reserved" not in facts):
            proposed = "terminal_reserve"
        elif ("personal_workaround_ruled_out" in facts
              and "reported" not in facts):
            proposed = "terminal_broadcast"
        elif ("reported_structural_problem" in facts
              and "assessed" not in facts):
            proposed = "terminal_assess"
        elif ("personal_workaround_ruled_out" in facts
              and "assessed" not in facts):
            proposed = "terminal_assess"
        elif ("primary_attempted" not in facts
              and "personal_workaround_ruled_out" not in facts):
            proposed = primary
        elif "reported" not in facts:
            proposed = "terminal_broadcast"
        elif "archived" not in facts:
            proposed = "terminal_archive"
        else:
            proposed = "terminal_comfort"
        if proposed not in available:
            raise PermissionError("GOAP generated a world-unoffered option")
        target = f"done_{proposed}"
        plan = GoapPlanner(actions).plan(facts, {target})
        assert len(plan.actions) == 1
        return next(o for o in options if o.verb == plan.actions[0].verb), {
            "goal": proposed, "personal_beliefs": sorted(facts),
            "reason_source": "authenticated_private_GOAP",
        }


async def experiment(seed, provider, out):
    if provider not in ("goap", "gemini"):
        raise ValueError("Explicit live trial provider required")
    if os.getenv("OX_TERMINAL_LIVE_CI") != "1":
        raise RuntimeError("Requires explicit disposable Evennia integration opt-in")
    if os.getenv("OX_CAPTAIN_OVERSIGHT") != "1":
        raise RuntimeError("Six separate authenticated clients are mandatory")

    s = FiveCrewSupervisor()
    if set(s.ids) != set(ROLES) or len(set(s.ids.values())) != 6:
        raise PermissionError("Refusing anything other than six distinct crew identities")
    traces = []
    all_events = {}
    clock_observations = []
    rng = random.Random(seed)
    initial = {role: rng.uniform(0.3, 2.8) for role in ROLES}
    next_delay = {role: [rng.uniform(2.0, 4.0) for _ in range(4)] for role in ROLES}
    started = time.monotonic()
    try:
        await s.open()
        # Verify actual world clock through a real authenticated client.
        captain_client = s.clients["captain"]
        initial_clock = await sensor(captain_client)
        clock_observations.append({
            "minute": initial_clock["minute"],
            "oxygen_kpa": initial_clock["oxygen_kpa"],
        })
        await asyncio.sleep(5)
        advanced_clock = await sensor(captain_client)
        clock_observations.append({
            "minute": advanced_clock["minute"],
            "oxygen_kpa": advanced_clock["oxygen_kpa"],
        })
        if advanced_clock["minute"] <= initial_clock["minute"]:
            raise AssertionError(
                "Server-owned terminal clock stalled before decisions: "
                f"{initial_clock['minute']} -> {advanced_clock['minute']}"
            )

        async def person(role):
            await asyncio.sleep(initial[role])
            controller = LocalGoap(role)
            actor = s.clients[role]
            for turn in range(4):
                events = await s.read_inbox(role)
                visible = await sensor(actor)
                if visible["status"] == "dead":
                    break
                s.brains[role].observe_local(
                    "Personal ship atmosphere telemetry", json.dumps(visible, sort_keys=True),
                )
                menu = choices(role)
                if provider == "goap":
                    option, reason = controller.choose(visible, events, menu)
                else:
                    proposal = await s.cognition.decide(role, s.brains[role].agent, menu)
                    option = next(x for x in menu if x.verb == proposal.verb)
                    reason = {"reason_source": "Concordia_Gemini_bounded_choice"}
                    s.brains[role].selected_procedure(proposal)
                destination = (
                    "Environmental Plant" if option.verb == "terminal_reserve"
                    else STATIONS[role]
                )
                # This is real Evennia movement through actual ship exits.
                await s.ensure_station(role, destination)
                # Repeat sensor after transit; no actor may rely on stale data.
                after_travel = await sensor(actor)
                if after_travel["status"] == "dead":
                    break
                request_id = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"ox-g6-world:{visible['case_id']}:{role}:{turn}",
                ).hex
                intent = {
                    "request_id": request_id, "actor": actor.character_dbref,
                    "operation": option.verb, "target": "ship",
                }
                atomic_json(Path(".ox-state/g6-intents") / f"{role}-{turn}.json", intent)
                actual = await DurableEvenniaPort(actor).submit_work(ActionRequest(
                    request_id, actor.character_dbref, option.verb, "ship",
                ))
                if actual.status == "unknown":
                    # Never submit another action with a fresh ID on ACK loss.
                    actual = await DurableEvenniaPort(actor).reconcile_work(request_id)
                controller.notice(option.verb, actual.status)
                traces.append({
                    "role": role, "character_dbref": actor.character_dbref,
                    "turn": turn, "world_minute": visible["minute"],
                    "world_minute_at_attempt": after_travel["minute"],
                    "oxygen_kpa": visible["oxygen_kpa"],
                    "co2_percent": visible["co2_percent"],
                    "own_finding": visible["own_finding"],
                    "addressed_reports": [e["text"] for e in events
                                         if e["kind"] == "terminal_report"],
                    "decision": option.verb, "decision_basis": reason,
                    "status": actual.status, "receipt_id": request_id,
                    "source_event_id": actual.source_event_id,
                })
                await asyncio.sleep(next_delay[role][turn])
            # Receive the final addressed evidence through this actor only.
            all_events[role] = [
                {"kind": evt["kind"], "text": evt["text"]}
                for evt in await s.read_inbox(role)
                if evt["kind"].startswith("terminal_")
            ]

        # Six independently authenticated bodies execute one async character
        # task each. Model latency does not serialize their decisions.
        await asyncio.wait_for(
            asyncio.gather(*(person(role) for role in ROLES)), timeout=115,
        )

        # The Evennia Script, not this handler, owns progression to death.
        captain = s.clients["captain"]
        dead = False
        for _ in range(65):
            state = await sensor(captain)
            clock_observations.append({
                "minute": state["minute"],
                "oxygen_kpa": state["oxygen_kpa"],
                "status": state["status"],
            })
            if state["status"] == "dead":
                dead = True
                break
            await asyncio.sleep(2)
        if not dead:
            raise AssertionError(
                "Server-owned fatality did not occur; authenticated progression "
                f"start={clock_observations[0]['minute']} "
                f"last={clock_observations[-1]['minute']}"
            )
        all_events["captain"] = [
            {"kind": evt["kind"], "text": evt["text"]}
            for evt in await s.read_inbox("captain")
            if evt["kind"].startswith("terminal_")
        ]
        summary = {
            "controller": provider, "seed": seed,
            "connected_characters": dict(s.ids),
            "decisions": sorted(traces, key=lambda d: (d["world_minute_at_attempt"], d["role"])),
            "private_received_events": all_events,
            "inference_calls": sum(x.inference_calls for x in s.brains.values()),
            "elapsed_test_seconds": round(time.monotonic()-started, 2),
            "observed_captain_status": "dead",
            "clock_observations": clock_observations,
        }
        if provider == "goap" and summary["inference_calls"] != 0:
            raise AssertionError("GOAP test called a model")
        if provider == "gemini" and summary["inference_calls"] < len(traces):
            raise AssertionError("Gemini decisions did not use real inference")
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(out, summary)
        print("OX_G6_SIX_AUTHENTICATED_TERMINAL_RUN_PASS", provider, seed, flush=True)
    finally:
        # Preserve actor-scoped evidence on any failure, not hidden world truth.
        atomic_json(Path(".ox-state/g6-partial.json"), {
            "seed": seed, "controller": provider,
            "authenticated_ids": dict(s.ids),
            "decisions": traces,
            "clock_observations": clock_observations,
            "model_calls": sum(x.inference_calls for x in s.brains.values()),
        })
        await s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("goap", "gemini"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, default=Path(".ox-state/g6-handler.json"))
    args = parser.parse_args()
    asyncio.run(experiment(args.seed, args.provider, args.out))


if __name__ == "__main__":
    main()
