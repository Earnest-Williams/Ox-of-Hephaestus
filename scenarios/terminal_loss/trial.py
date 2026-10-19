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

    def snapshot(self, role: str) -> str:
        """Only observations this actual crew member could legitimately have."""
        if role not in ROLES:
            raise PermissionError("Unknown crew identity")
        randomizer = random.Random(self.seed * 100003 + self.minute * 37 + ROLES.index(role))
        indicated = round(self.oxygen() + randomizer.uniform(-0.35, 0.35), 2)
        incoming = list(self.inboxes[role])
        own = list(self.inspections[role])
        return (
            f"You are {NAMES[role]} at {STATIONS[role]}. "
            f"Shipwide low-pressure warning. Local oxygen sensor {indicated} kPa; "
            f"local CO2 sensor {self.carbon_dioxide():.2f} percent; readings worsening. "
            "The available systems are those installed on this ship; there is no known rescue plan. "
            f"Your own firsthand findings: {own if own else ['not yet inspected']}. "
            f"Actual addressed communications: {incoming if incoming else ['none']}. "
            "Actions are attempts; success or failure is determined by physical world conditions."
        )

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
            report = self.inspections[role][-1] if self.inspections[role] else "I have no first-hand diagnosis yet"
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
    """Finite GOAP policy, operating on personal outcome history, never truth."""

    def __init__(self):
        self.facts: dict[str, set[str]] = {r: {"alarm"} for r in ROLES}

    def choose(self, role: str, options: list[CommandOption]) -> CommandOption:
        facts = self.facts[role]
        primary = PRIMARY[role][0]
        actions = [
            GoapAction("survey", requires=frozenset({"alarm"}),
                       adds=frozenset({"surveyed"}), verb="survey", cost=1),
            GoapAction(primary, requires=frozenset({"surveyed"}),
                       adds=frozenset({"primary_attempted"}), verb=primary, cost=2),
            GoapAction("broadcast", requires=frozenset({"surveyed"}),
                       adds=frozenset({"crew_informed"}), verb="broadcast", cost=2),
            GoapAction("comfort", requires=frozenset({"surveyed"}),
                       adds=frozenset({"assisted"}), verb="comfort", cost=3),
        ]
        if role in ("teo", "captain"):
            actions.append(GoapAction(
                "use_reserve", requires=frozenset({"surveyed"}),
                adds=frozenset({"temporary_supply"}), verb="use_reserve", cost=3,
            ))
        goal = ("surveyed" if "surveyed" not in facts
                else "primary_attempted" if "primary_attempted" not in facts
                else "temporary_supply" if role in ("teo", "captain") and "temporary_supply" not in facts
                else "crew_informed" if "crew_informed" not in facts
                else "assisted")
        step = GoapPlanner(actions).plan(facts, {goal}).actions[0]
        return next(x for x in options if x.verb == step.verb)

    def notice(self, role: str, receipt: dict) -> None:
        progress = {
            "survey": "surveyed", PRIMARY[role][0]: "primary_attempted",
            "broadcast": "crew_informed", "use_reserve": "temporary_supply",
            "comfort": "assisted",
        }
        # A failed physical operation is an ATTEMPT, never presumed recovery.
        fact = progress.get(receipt["verb"])
        if fact:
            self.facts[role].add(fact)


def run(seed: int, provider: str) -> dict:
    """Three opportunity rounds, then fatal world progression without decisions."""
    if provider not in ("goap", "gemini"):
        raise ValueError("Choose goap or gemini; never auto-fallback")
    world = TerminalWorld(seed=seed)
    planner = GoalPlannerControl() if provider == "goap" else None
    brains = {}
    if provider == "gemini":
        from ox_ai.agents.live_concordia import LiveCrewBrain, make_model
        from ox_ai.ports.base import ActionOutcome, WorldObservation
        # Each separately instantiated Concordia mind receives only local and
        # actually addressed observations, with immutable character bindings.
        for index, role in enumerate(ROLES):
            brains[role] = LiveCrewBrain(role, f"#{100 + index}", make_model("gemini"))

    decisions = 0
    for window in range(3):
        for role in ROLES:
            if not world.alive[role]:
                break
            observed = world.snapshot(role)
            options = world.options(role)
            if provider == "goap":
                selected = planner.choose(role, options)
                request_id = hashlib.sha256(
                    f"{seed}:{window}:{role}".encode("utf-8")
                ).hexdigest()[:32]
            else:
                brain = brains[role]
                brain.agent.observe(WorldObservation(
                    observation_id=f"fatal-{seed}-{window}-{role}",
                    character_id=brain.character_id,
                    game_time=float(world.minute * 60),
                    text=observed, kind="personal_world_sensors",
                ))
                proposal = brain.agent.decide(
                    options, expected_revision=brain.agent.revision,
                )
                selected = next(x for x in options if x.verb == proposal.verb)
                request_id = proposal.request_id
            receipt = world.work(role, request_id, selected.verb)
            if planner is not None:
                planner.notice(role, receipt)
            else:
                brains[role].agent.record_outcome(ActionOutcome(
                    request_id, receipt["status"], receipt["reason"],
                    source_event_id=request_id,
                ))
            decisions += 1
            world.advance(7)
        if world.death_minute is not None:
            break
        world.advance(12)

    # Terminal physics remains authoritative even when the crew defer.
    while world.death_minute is None:
        world.advance(3)
        if world.minute > 1000:
            raise AssertionError("Irreparable incident did not terminate")
    audit = world.operator_audit(provider)
    audit["decisions"] = decisions
    audit["inference_calls"] = sum(b.inference_calls for b in brains.values())
    if not audit["world_state"]["all_six_dead"]:
        raise AssertionError("Terminal physics must govern every controller")
    if provider == "goap" and audit["inference_calls"]:
        raise AssertionError("The non-generative control must make zero model calls")
    if provider == "gemini" and audit["inference_calls"] != decisions:
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
    assert not any(x["status"] == "succeeded" for x in trial.trace if x["verb"] in ("patch", "reroute"))
    baseline = run(241, "goap")
    repeat = run(241, "goap")
    assert [(a["role"], a["verb"], a["status"]) for a in baseline["actions"]] == [
        (a["role"], a["verb"], a["status"]) for a in repeat["actions"]
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
        f"**Operator-only cause:** {data['operator_only_actual_failure']}",
        f"**Outcome:** {sum(not d['survived'] for d in data['per_character'].values())}/6 dead;",
        f"world minute {result['death_minute']}; oxygen {result['oxygen_kpa_at_death']} kPa.",
        f"**Decision count:** {data['decisions']}; hosted choice calls: {data['inference_calls']}.",
        "",
        "| Time (min) | Person | Attempted action | World outcome | Reason |",
        "|---:|---|---|---|---|",
    ]
    for action in data["actions"]:
        lines.append(
            f"| {action['minute']} | {NAMES[action['role']]} | {action['verb']} "
            f"| {action['status']} | {action['reason']} |"
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
    }, sort_keys=True))
    print("OX_TERMINAL_SCENARIO_COMPLETE")


if __name__ == "__main__":
    main()
