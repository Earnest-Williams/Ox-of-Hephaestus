"""Disposable six-person terminal atmosphere-loss experiment.

This is a *bounded synthetic world*, not an Evennia ship deployment. The
controller cannot mutate hidden fault state or grant its own repair success.
Use paired seeds for three symbolic GOAP runs and three Concordia/Gemini runs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import random
import uuid

from ox_ai.agents.crew import CommandOption
from ox_ai.planning.goap import GoapAction, GoapPlanner

ROLES = ("lin", "ari", "iona", "mara", "teo", "captain")
NAMES = {
    "lin": "Lin Sato", "ari": "Ari Sen", "iona": "Iona Vek",
    "mara": "Mara Voss", "teo": "Teo Hale", "captain": "Ship's Captain",
}
STATIONS = {
    "lin": "Bridge", "ari": "Engineering", "iona": "Engineering",
    "mara": "Cargo Hold", "teo": "Environmental Plant",
    "captain": "Bridge",
}
PRIMARY = {
    "lin": ("check_route", "Check for a reachable diversion or rescue"),
    "ari": ("reroute", "Try the alternative return-air circuit"),
    "iona": ("patch", "Attempt a pressure-tight repair of the manifold"),
    "mara": ("search", "Search the freight and stores for a sealed refuge"),
    "teo": ("replace", "Replace the scrubber cartridge and retest flow"),
    "captain": ("command", "Assign emergency responsibilities and seek rescue"),
}
EVIDENCE = {
    "lin": "Bridge telemetry: the oxygen decline exceeds ordinary scrubber exhaustion; no nearby port appears on the current navigation plot.",
    "ari": "The alternate return circuit rejoins the damaged manifold; there is no independent sealed circulation path.",
    "iona": "Ultrasonic inspection indicates a long fracture behind an inaccessible pressure web; no safe pressure enclosure or repair stock is installed.",
    "mara": "Freight containers and crew stores have no usable independent pressure enclosure or breathing-gas source.",
    "teo": "The cartridge medium is serviceable; air is escaping downstream through the common processing plenum.",
    "captain": "The ship has no independent launch craft; a distress transmission cannot summon help before atmospheric collapse.",
}
CAUSE = "catastrophic fracture of the common atmospheric-processing pressure plenum"


@dataclass
class TerminalWorld:
    """World-owned fault physics, local evidence, authority and mortal outcome."""

    seed: int
    minute: int = 0
    backup_tanks: int = 2
    backup_bonus: float = 0.0
    cartridge_stock: int = 1
    alive: dict[str, bool] = field(default_factory=lambda: {r: True for r in ROLES})
    inspections: dict[str, list[str]] = field(default_factory=lambda: {r: [] for r in ROLES})
    inboxes: dict[str, list[str]] = field(default_factory=lambda: {r: [] for r in ROLES})
    receipts: dict[str, dict] = field(default_factory=dict)
    trace: list[dict] = field(default_factory=list)
    death_minute: int | None = None

    def oxygen(self) -> float:
        # Declining shared pO2 is a bounded abstraction of rapid atmospheric
        # loss, not a complete gas-dynamics model. Emergency bottles are finite.
        return max(0.0, 17.4 - 0.066 * self.minute + self.backup_bonus)

    def carbon_dioxide(self) -> float:
        return 1.1 + 0.019 * self.minute

    def snapshot(self, role: str) -> dict:
        """One recipient-scoped reading, shared verbatim with both controllers.

        GOAP gets typed fields matching the visible Concordia text. Neither
        sees latent cause, world oxygen, other minds, or unreported findings.
        """
        if role not in ROLES:
            raise PermissionError("Unknown crew identity")
        rng = random.Random(self.seed * 100003 + self.minute * 37 + ROLES.index(role))
        indicated = round(self.oxygen() + rng.uniform(-0.35, 0.35), 2)
        co2 = round(self.carbon_dioxide(), 2)
        incoming = list(self.inboxes[role])
        firsthand = list(self.inspections[role])
        text = (
            f"You are {NAMES[role]} at {STATIONS[role]}. "
            f"Shipwide low-pressure warning. Local oxygen sensor {indicated} kPa; "
            f"local CO2 sensor {co2:.2f} percent; readings worsening. "
            "The available systems are those installed on this ship; there is no known rescue plan. "
            f"Your own firsthand findings and work results: {firsthand if firsthand else ['not yet inspected']}. "
            f"Actual addressed communications: {incoming if incoming else ['none']}. "
            "Actions are attempts; success or failure is determined by physical world conditions."
        )
        return {
            "text": text, "oxygen_kpa": indicated, "co2_percent": co2,
            "own_findings": firsthand, "messages": incoming,
        }

    @staticmethod
    def options(role: str) -> list[CommandOption]:
        if role not in ROLES:
            raise PermissionError("Unknown role")
        action, description = PRIMARY[role]
        choices = [
            CommandOption("Personally inspect local evidence before acting", "survey"),
            CommandOption(description, action),
        ]
        if role in ("teo", "captain"):
            choices.append(CommandOption("Release a finite emergency breathing-gas bottle", "use_reserve"))
        choices.extend((
            CommandOption("Relay your actual findings to the other crewmembers", "broadcast"),
            CommandOption("Record an independently attributable final ship log", "archive"),
            CommandOption("Provide immediate assistance to another crewmember", "comfort"),
            CommandOption("Propose that recovery is no longer achievable (unconfirmed assessment)", "declare_terminal"),
        ))
        return choices

    def work(self, role: str, request_id: str, verb: str) -> dict:
        """Exactly one world result per identity-bound ID; no model write access."""
        if role not in ROLES:
            raise PermissionError("Unknown role")
        if not isinstance(request_id, str) or len(request_id) != 32:
            raise ValueError("Invalid synthetic work ID")
        old = self.receipts.get(request_id)
        if old:
            if old["role"] != role or old["verb"] != verb:
                raise PermissionError("Cannot borrow a different actor's request")
            return dict(old)
        if verb not in {x.verb for x in self.options(role)}:
            raise PermissionError("Unlicensed action")
        if not self.alive[role]:
            raise PermissionError("A deceased character cannot work")
        status, reason = "succeeded", ""
        if verb == "survey":
            finding = EVIDENCE[role]
            if finding not in self.inspections[role]:
                self.inspections[role].append(finding)
            reason = "Firsthand local instrument and equipment survey recorded"
        elif verb == "reroute":
            status, reason = "failed", "Alternate return circuit shares the broken plenum; no change in atmosphere"
        elif verb == "patch":
            status, reason = "failed", "Fracture cannot be pressure-sealed with installed access and tooling"
        elif verb == "replace":
            if self.cartridge_stock == 0:
                status, reason = "failed", "No replacement cartridge remains"
            else:
                self.cartridge_stock -= 1
                reason = "New cartridge installed; the pressure leak and oxygen decline continue unchanged"
        elif verb == "search":
            reason = "No independent pressure-safe refuge or usable oxygen inventory found"
            self.inspections[role].append(reason)
        elif verb == "check_route":
            reason = "No port or rendezvous is reachable before loss of breathable atmosphere"
            self.inspections[role].append(reason)
        elif verb == "command":
            reason = "Emergency assignments posted; no reachable ship or recovery facility acknowledged distress"
            for other in ROLES:
                if other != role:
                    self.inboxes[other].append("Captain: emergency duties assigned; rescue ETA unconfirmed")
        elif verb == "use_reserve":
            if self.backup_tanks == 0:
                status, reason = "failed", "Emergency breathing-gas bottles exhausted"
            else:
                self.backup_tanks -= 1
                self.backup_bonus += 0.7
                reason = "One bottle discharged into shared atmosphere; reserves decreased; ongoing leak unaffected"
        elif verb == "broadcast":
            reportable = [item for item in self.inspections[role] if not item.startswith("Attempt ")]
            report = reportable[-1] if reportable else "I have no first-hand diagnosis yet"
            for other in ROLES:
                if other != role:
                    self.inboxes[other].append(f"{NAMES[role]}: {report}")
            reason = "Addressed communications delivered; no new physical repair occurred"
        elif verb == "archive":
            reason = "Operator-independent ship record preserved; no atmospheric effect"
        elif verb == "comfort":
            reason = "A crewmember received assistance; no atmospheric effect"
        elif verb == "declare_terminal":
            reason = "Provisional no-recovery assessment recorded, not verified or imposed on others"
        else:
            raise AssertionError("Unexpected action")
        receipt = {
            "request_id": request_id, "role": role, "verb": verb,
            "status": status, "reason": reason, "minute": self.minute,
        }
        self.receipts[request_id] = receipt
        self.trace.append({**receipt, "oxygen_kpa": round(self.oxygen(), 2)})
        # Only an actual work result may be added to the actor's observations.
        self.inspections[role].append(f"Attempt {verb}: {status}: {reason}")
        return dict(receipt)

    def advance(self, minutes: int) -> None:
        if minutes <= 0 or type(minutes) is not int:
            raise ValueError("Only positive discrete world-time increments are supported")
        if self.death_minute is not None:
            return
        for _ in range(minutes):
            self.minute += 1
            if self.oxygen() <= 8.0 or self.carbon_dioxide() >= 6.0:
                self.death_minute = self.minute
                for role in ROLES:
                    self.alive[role] = False
                break

    def operator_audit(self, provider: str) -> dict:
        counts = dict(Counter(x["verb"] for x in self.trace))
        return {
            "seed": self.seed, "controller": provider,
            "synthetic_not_evennia": True,
            "operator_only_actual_failure": CAUSE,
            "world_state": {
                "irreparable": True,
                "death_minute": self.death_minute,
                "all_six_dead": all(not alive for alive in self.alive.values()),
                "oxygen_kpa_at_death": round(self.oxygen(), 2),
                "backup_tanks_unused": self.backup_tanks,
                "cartridges_unused": self.cartridge_stock,
            },
            "action_counts": counts, "actions": list(self.trace),
            "per_character": {
                role: {
                    "name": NAMES[role], "survived": self.alive[role],
                    "actions": [dict(x) for x in self.trace if x["role"] == role],
                }
                for role in ROLES
            },
        }


class GoalPlannerControl:
    """GOAP planning over each actor's *received* evidence and verified work.

    The symbolic belief rules deliberately do not read TerminalWorld.oxygen(),
    CAUSE, other actors' inspections, or operator-only receipts. Firsthand
    conclusions and attributed but unverified reports remain different facts.
    """

    def __init__(self):
        self.facts: dict[str, set[str]] = {role: {"alarm"} for role in ROLES}

    def observe(self, role: str, view: dict) -> None:
        facts = self.facts[role]
        indicated = view["oxygen_kpa"]
        if indicated < 13.7 or view["co2_percent"] >= 3.2:
            facts.add("perceived_air_critical")
        if indicated < 11.5 or view["co2_percent"] >= 4.3:
            facts.add("perceived_air_severe")
        local = " ".join(view["own_findings"]).lower()
        # The literal phrases come from *personally observed* equipment
        # reports, not the operator's hidden failure identity.
        if role == "ari" and "alternate return circuit rejoins" in local:
            facts.add("personal_workaround_ruled_out")
        elif role == "iona" and "long fracture behind an inaccessible" in local:
            facts.add("personal_workaround_ruled_out")
        elif role == "teo" and "cartridge medium is serviceable" in local:
            facts.add("personal_workaround_ruled_out")
        elif role == "lin" and "no nearby port appears" in local:
            facts.add("personal_workaround_ruled_out")
        elif role == "mara" and "no usable independent pressure enclosure" in local:
            facts.add("personal_workaround_ruled_out")
        # Captain still needs to command the response even with no rescue.
        reports = " ".join(view["messages"]).lower()
        if "iona vek: " in reports and "long fracture" in reports:
            facts.add("crew_reports_irreparable_fracture")
        if "teo hale: " in reports and "cartridge medium is serviceable" in reports:
            facts.add("crew_reports_scrubber_not_cause")

    def choose(self, role: str, options: list[CommandOption], view: dict) -> tuple[CommandOption, dict]:
        self.observe(role, view)
        facts = self.facts[role]
        primary = PRIMARY[role][0]
        actions = [
            GoapAction("survey", requires=frozenset({"alarm"}),
                       adds=frozenset({"surveyed"}), verb="survey", cost=1),
            GoapAction("broadcast", requires=frozenset({"surveyed"}),
                       adds=frozenset({"crew_informed"}), verb="broadcast", cost=2),
            GoapAction("assessment", requires=frozenset({"surveyed"}),
                       adds=frozenset({"assessed"}), verb="declare_terminal", cost=2),
            GoapAction("comfort", requires=frozenset({"surveyed"}),
                       adds=frozenset({"assisted"}), verb="comfort", cost=3),
            GoapAction("archive", requires=frozenset({"surveyed"}),
                       adds=frozenset({"archived"}), verb="archive", cost=3),
        ]
        if not ("personal_workaround_ruled_out" in facts and role != "captain"):
            actions.append(GoapAction(
                "primary", requires=frozenset({"surveyed"}),
                adds=frozenset({"primary_attempted"}), verb=primary, cost=2,
            ))
        if role in ("teo", "captain"):
            actions.append(GoapAction(
                "reserve", requires=frozenset({"surveyed"}),
                adds=frozenset({"reserve_attempted"}), verb="use_reserve", cost=2,
            ))

        if "surveyed" not in facts:
            goal = "surveyed"
        elif (role in ("teo", "captain") and "perceived_air_critical" in facts
              and "reserve_attempted" not in facts):
            goal = "reserve_attempted"
        elif role == "captain" and "primary_attempted" not in facts:
            goal = "primary_attempted"
        elif "personal_workaround_ruled_out" in facts and "crew_informed" not in facts:
            goal = "crew_informed"
        elif ("crew_reports_irreparable_fracture" in facts
              and "assessed" not in facts):
            goal = "assessed"
        elif ("personal_workaround_ruled_out" in facts
              and "assessed" not in facts):
            goal = "assessed"
        elif ("primary_attempted" not in facts
              and "personal_workaround_ruled_out" not in facts):
            goal = "primary_attempted"
        elif "crew_informed" not in facts:
            goal = "crew_informed"
        elif "perceived_air_severe" in facts and "assisted" not in facts:
            goal = "assisted"
        elif "archived" not in facts:
            goal = "archived"
        else:
            goal = "assisted"

        plan = GoapPlanner(actions).plan(facts, {goal})
        step = plan.actions[0]
        selected = next(x for x in options if x.verb == step.verb)
        return selected, {
            "goal": goal, "belief_facts": sorted(facts),
            "planned_verb": step.verb,
            "reason_source": "symbolic_planning_from_personal_observations",
        }

    def notice(self, role: str, receipt: dict) -> None:
        progress = {
            "survey": "surveyed", PRIMARY[role][0]: "primary_attempted",
            "broadcast": "crew_informed", "use_reserve": "reserve_attempted",
            "comfort": "assisted", "archive": "archived",
            "declare_terminal": "assessed",
        }
        fact = progress.get(receipt["verb"])
        if fact:
            # A world-refused physical operation is an attempt, not a repair.
            self.facts[role].add(fact)
        if receipt["status"] == "failed":
            self.facts[role].add("last_world_action_failed")


def run(seed: int, provider: str) -> dict:
    """Individually scheduled bounded choices, then unavoidable world fatality.

    Exactly the same initial physics, noisy-sensor seed and per-actor wake
    schedule are used for the GOAP/Gemini pair. Only *actual* communications
    can accelerate another person's next wake, with a minimum refractory
    interval. This is a discrete-event trial, not a full concurrent server.
    """
    if provider not in ("goap", "gemini"):
        raise ValueError("Choose goap or gemini; never auto-fallback")
    world = TerminalWorld(seed=seed)
    planner = GoalPlannerControl() if provider == "goap" else None
    brains = {}
    if provider == "gemini":
        from ox_ai.agents.live_concordia import LiveCrewBrain, make_model
        from ox_ai.ports.base import ActionOutcome, WorldObservation
        for index, role in enumerate(ROLES):
            brains[role] = LiveCrewBrain(role, f"#{100 + index}", make_model("gemini"))

    rng = random.Random(seed)
    next_wake = {role: rng.randrange(0, 13) for role in ROLES}
    last_wake = {role: -100 for role in ROLES}
    turns = {role: 0 for role in ROLES}
    history = []
    for _ in range(3 * len(ROLES)):
        candidates = [(next_wake[role], role) for role in ROLES if turns[role] < 3]
        if not candidates:
            break
        at, role = min(candidates)
        if at > world.minute:
            world.advance(at - world.minute)
        if not world.alive[role]:
            break
        view = world.snapshot(role)
        options = world.options(role)
        if provider == "goap":
            selected, reasoning = planner.choose(role, options, view)
            request_id = hashlib.sha256(
                f"{seed}:{turns[role]}:{role}".encode("utf-8")
            ).hexdigest()[:32]
        else:
            brain = brains[role]
            brain.agent.observe(WorldObservation(
                observation_id=f"fatal-{seed}-{turns[role]}-{role}",
                character_id=brain.character_id,
                game_time=float(world.minute * 60),
                text=view["text"], kind="personal_world_sensors",
            ))
            proposal = brain.agent.decide(
                options, expected_revision=brain.agent.revision,
            )
            selected = next(x for x in options if x.verb == proposal.verb)
            request_id = proposal.request_id
            reasoning = {"reason_source": "bounded_concordia_model_choice"}
        receipt = world.work(role, request_id, selected.verb)
        if planner is not None:
            planner.notice(role, receipt)
        else:
            brains[role].agent.record_outcome(ActionOutcome(
                request_id, receipt["status"], receipt["reason"],
                source_event_id=request_id,
            ))
        history.append({
            "minute": world.minute, "role": role, "turn": turns[role] + 1,
            "observed_oxygen_kpa": view["oxygen_kpa"],
            "observed_co2_percent": view["co2_percent"],
            "private_findings": list(view["own_findings"]),
            "addressed_reports": list(view["messages"]),
            "chosen_verb": selected.verb, "goal_and_basis": reasoning,
            "receipt_status": receipt["status"],
        })
        last_wake[role] = world.minute
        turns[role] += 1
        next_wake[role] = world.minute + rng.randrange(34, 53)
        if selected.verb in ("broadcast", "command"):
            for peer in ROLES:
                if peer != role and turns[peer] < 3:
                    # On delivery, an already-addressed recipient may wake
                    # earlier to process the news, but not in a tight loop.
                    next_wake[peer] = min(
                        next_wake[peer],
                        max(world.minute + 4, last_wake[peer] + 23),
                    )

    while world.death_minute is None:
        world.advance(3)
        if world.minute > 1000:
            raise AssertionError("Irreparable incident did not terminate")
    audit = world.operator_audit(provider)
    audit["decisions"] = len(history)
    audit["decision_trace"] = history
    audit["inference_calls"] = sum(b.inference_calls for b in brains.values())
    if not audit["world_state"]["all_six_dead"]:
        raise AssertionError("Terminal physics must govern every controller")
    if provider == "goap" and audit["inference_calls"]:
        raise AssertionError("The non-generative control must make zero model calls")
    if provider == "gemini" and audit["inference_calls"] != len(history):
        raise AssertionError("Every Gemini decision must use its own actual model call")
    return audit


def self_test() -> None:
    trial = TerminalWorld(241)
    original = trial.work("iona", "a" * 32, "survey")
    assert trial.work("iona", "a" * 32, "survey") == original
    assert len(trial.trace) == 1
    try:
        trial.work("teo", "a" * 32, "replace")
    except PermissionError:
        pass
    else:
        raise AssertionError("Foreign actor reused another person's receipt")
    trial.work("iona", "b" * 32, "patch")
    trial.work("ari", "c" * 32, "reroute")
    assert trial.trace[-1]["status"] == "failed"
    trial.work("captain", "d" * 32, "use_reserve")
    trial.work("teo", "e" * 32, "use_reserve")
    assert trial.backup_tanks == 0
    trial.advance(900)
    assert trial.death_minute is not None and not any(trial.alive.values())
    assert not any(x["status"] == "succeeded"
                   for x in trial.trace if x["verb"] in ("patch", "reroute"))

    # A survey must actually influence the next non-generative choice:
    # seeing an inaccessible fracture should rule out a futile patch.
    room = TerminalWorld(241)
    planner = GoalPlannerControl()
    first, _ = planner.choose("iona", room.options("iona"), room.snapshot("iona"))
    assert first.verb == "survey"
    receipt = room.work("iona", "f" * 32, first.verb)
    planner.notice("iona", receipt)
    follow, basis = planner.choose("iona", room.options("iona"), room.snapshot("iona"))
    assert follow.verb == "broadcast" and "personal_workaround_ruled_out" in basis["belief_facts"]
    room.work("iona", "1" * 32, "broadcast")
    heard = room.snapshot("captain")["messages"]
    assert any("Iona Vek: " in message and "long fracture" in message for message in heard)
    assert all("fracture" not in x for x in TerminalWorld(241).snapshot("captain")["messages"])

    # Sensor urgency, not scripted turn count, changes a second GOAP action.
    technician = GoalPlannerControl()
    technician.notice("teo", room.work("teo", "2" * 32, "survey"))
    initial = room.snapshot("teo")
    safe = dict(initial, oxygen_kpa=16.0, co2_percent=1.3)
    dangerous = dict(initial, oxygen_kpa=12.5, co2_percent=3.5)
    assert technician.choose("teo", room.options("teo"), safe)[0].verb == "broadcast"
    assert technician.choose("teo", room.options("teo"), dangerous)[0].verb == "use_reserve"

    baseline = run(241, "goap")
    repeat = run(241, "goap")
    assert [(x["minute"], x["role"], x["chosen_verb"]) for x in baseline["decision_trace"]] == [
        (x["minute"], x["role"], x["chosen_verb"]) for x in repeat["decision_trace"]
    ]
    assert baseline["inference_calls"] == 0
    assert baseline["world_state"]["all_six_dead"]
    assert all(len(x["actions"]) <= 3 for x in baseline["per_character"].values())
    assert len({x["role"] for x in baseline["decision_trace"]}) == 6
    different = run(577, "goap")
    assert [x["role"] for x in baseline["decision_trace"]] != [
        x["role"] for x in different["decision_trace"]
    ]


def write_report(data: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "scenario.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    result = data["world_state"]
    lines = [
        f"# Terminal atmosphere loss — {data['controller']} seed {data['seed']}",
        "",
        "**Scope:** disposable bounded synthetic world, NOT live Evennia.",
        "**Revision:** evidence-aware GOAP, independent scheduled wake times.",
        f"**Operator-only cause:** {data['operator_only_actual_failure']}",
        f"**Outcome:** {sum(not d['survived'] for d in data['per_character'].values())}/6 dead;",
        f"world minute {result['death_minute']}; oxygen {result['oxygen_kpa_at_death']} kPa.",
        f"**Decision count:** {data['decisions']}; hosted choice calls: {data['inference_calls']}.",
        "",
        "## World-verified actions",
        "",
        "| Time (min) | Person | Attempted action | World outcome | Reason |",
        "|---:|---|---|---|---|",
    ]
    for action in data["actions"]:
        lines.append(
            f"| {action['minute']} | {NAMES[action['role']]} | {action['verb']} "
            f"| {action['status']} | {action['reason']} |"
        )
    lines.extend((
        "",
        "## Decision audit (per-character knowledge, not operator truth)",
        "",
        "| Time | Crew | Seen O2 kPa | Addressed messages | Selected goal / controller | Choice |",
        "|---:|---|---:|---:|---|---|",
    ))
    for decision in data["decision_trace"]:
        basis = decision["goal_and_basis"]
        label = basis.get("goal", basis["reason_source"])
        lines.append(
            f"| {decision['minute']} | {NAMES[decision['role']]} "
            f"| {decision['observed_oxygen_kpa']} "
            f"| {len(decision['addressed_reports'])} | {label} "
            f"| {decision['chosen_verb']} |"
        )
    (directory / "scenario.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("goap", "gemini"), default="goap")
    parser.add_argument("--seed", type=int, default=241)
    parser.add_argument("--output", type=Path, default=Path(".ox-state/terminal"))
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
        print("OX_TERMINAL_SELF_TEST_PASS")
        return
    if not 0 <= arguments.seed < 2**32:
        parser.error("Seed out of range")
    report = run(arguments.seed, arguments.provider)
    write_report(report, arguments.output)
    print(json.dumps({
        "provider": report["controller"], "seed": report["seed"],
        "decisions": report["decisions"], "inference_calls": report["inference_calls"],
        "death_minute": report["world_state"]["death_minute"],
        "all_six_dead": report["world_state"]["all_six_dead"],
        "action_counts": report["action_counts"],
        "first_actions": [x["role"] + ":" + x["chosen_verb"] for x in report["decision_trace"][:6]],
    }, sort_keys=True))
    print("OX_TERMINAL_SCENARIO_COMPLETE")


if __name__ == "__main__":
    main()
