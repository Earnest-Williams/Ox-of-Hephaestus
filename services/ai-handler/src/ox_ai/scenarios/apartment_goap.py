"""A deliberately small, model-free GOAP experiment in ordinary social choices.

Two people have enjoyed a date and are talking in her apartment. This module
does not generate dialogue with an LLM. GOAP chooses communicative acts,
which the initial probe realises using fixed, recognizable utterances.

World/transport must confirm a spoken line before its author's projected
action effects are adopted. A listener infers only cues from heard words;
neither agent receives the other's private motivation or emotional state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable


LINES = {
    "appreciate": "I had a really good time tonight.",
    "ask_feeling": "What did you think of our evening?",
    "answer_feeling": "I enjoyed being with you. I'm glad we had time to talk.",
    "reciprocate": "I'm glad you said that. I feel the same.",
    "invite": "Would you like to go out together again sometime?",
    "accept": "Yes, I'd really like that.",
    "defer": "I had a lovely time, but I'd like to take things slowly.",
    "decline": "I enjoyed tonight, but I don't think another date is right for me.",
    "share_pace": "I'm enjoying this, but I'd like us to take things slowly.",
    "acknowledge_pace": "Of course. There's no rush.",
    "acknowledge_decline": "Thank you for telling me. I understand.",
    "celebrate": "That makes me happy. I'm looking forward to it.",
    "goodnight": "I'm glad we got together. Good night.",
}

# Derived ONLY from exact words a listener actually receives. These are not
# mental-state labels or authoritative declarations that a date succeeded.
HEARD_CUES = {
    LINES["appreciate"]: {"partner_positive", "partner_appreciated"},
    LINES["ask_feeling"]: {"partner_asked"},
    LINES["answer_feeling"]: {"partner_positive"},
    LINES["reciprocate"]: {"partner_positive"},
    LINES["invite"]: {"partner_invited"},
    LINES["accept"]: {"partner_accepted"},
    LINES["defer"]: {"partner_pace"},
    LINES["decline"]: {"partner_declined"},
    LINES["share_pace"]: {"partner_pace"},
    LINES["acknowledge_pace"]: {"partner_acknowledged_pace"},
    LINES["acknowledge_decline"]: {"partner_acknowledged_decline"},
    LINES["celebrate"]: {"partner_positive"},
    LINES["goodnight"]: {"partner_goodnight"},
}


def _act(name: str, requires: Iterable[str], adds: Iterable[str], cost: int = 1):
    return GoapAction(
        name, requires=frozenset(requires), adds=frozenset(adds),
        cost=cost, verb="say", target=name,
    )


SOCIAL_ACTIONS = (
    _act("appreciate", ("in_apartment", "date_enjoyed"), ("appreciated",)),
    _act("ask_feeling", ("appreciated", "partner_present"), ("asked_feeling",), 2),
    _act("answer_feeling", ("partner_asked", "date_enjoyed"), ("answered_feeling",)),
    _act("reciprocate", ("partner_appreciated", "appreciated"), ("reciprocated",)),
    _act("invite", ("appreciated", "partner_positive"),
         ("invited",), 2),
    _act("accept", ("partner_invited", "open_to_more"),
         ("answered_invitation", "accepted")),
    _act("defer", ("partner_invited", "needs_time"),
         ("answered_invitation", "deferred")),
    _act("decline", ("partner_invited", "not_interested"),
         ("answered_invitation", "declined")),
    _act("share_pace", ("appreciated", "prefers_slow"), ("pace_shared",)),
    _act("acknowledge_pace", ("partner_pace",), ("pace_acknowledged",)),
    _act("acknowledge_decline", ("partner_declined",), ("decline_acknowledged",)),
    _act("celebrate", ("partner_accepted",), ("acceptance_acknowledged",)),
    _act("goodnight", ("appreciated",), ("said_goodnight",)),
)


@dataclass(frozen=True, slots=True)
class SocialDecision:
    actor: str
    goal: str
    plan: tuple[str, ...]
    cost: int
    expansions: int
    action: str
    line: str


class SocialGoapActor:
    """Independently plans from private motives and public observations.

    Interest and caution are authored starting tendencies, not revealed facts
    about another person. This first pilot intentionally does not implement
    physiology, attachment theory, free-text understanding or LLM narration.
    """

    def __init__(self, name: str, *, interest: int, caution: int):
        if not name or not (0 <= interest <= 100 and 0 <= caution <= 100):
            raise ValueError("A named adult with 0-100 motive scales is required")
        self.name = name
        self.interest = interest
        self.caution = caution
        self.facts = {"in_apartment", "partner_present", "date_enjoyed"}
        if interest < 40:
            self.facts.add("not_interested")
        elif interest < 65 or caution >= 75:
            self.facts.add("needs_time")
        else:
            self.facts.add("open_to_more")
        if caution >= 75:
            self.facts.add("prefers_slow")
        self.planner = GoapPlanner(SOCIAL_ACTIONS, expansion_cap=1024)
        self.pending: SocialDecision | None = None
        self.seen: set[str] = set()
        self.blocked: set[str] = set()
        self.planning_calls = 0
        self.expanded_states = 0
        self.model_calls = 0  # There is deliberately no model object.

    def _goals(self) -> list[tuple[str, frozenset[str], int]]:
        """Offer competing private goals, not a prescribed turn-by-turn script."""
        f = self.facts
        if "said_goodnight" in f:
            return []
        if "partner_goodnight" in f:
            return [("reply_goodnight", frozenset({"said_goodnight"}), 180)]
        candidates: list[tuple[str, frozenset[str], int]] = []
        def offer(name: str, fact: str, value: int):
            if fact not in f:
                candidates.append((name, frozenset({fact}), value))

        if "partner_invited" in f and "answered_invitation" not in f:
            offer("answer_invitation", "answered_invitation", 150)
        if "partner_declined" in f:
            offer("respect_decline", "decline_acknowledged", 145)
        if "partner_pace" in f:
            offer("respect_pace", "pace_acknowledged", 140)
        if "partner_asked" in f:
            offer("answer_question", "answered_feeling", 135)

        offer("express_enjoyment", "appreciated", 100)
        if "partner_accepted" in f:
            offer("acknowledge_acceptance", "acceptance_acknowledged", 85)
        if "prefers_slow" in f and "partner_appreciated" in f:
            offer("communicate_pace", "pace_shared", 92)
        if "partner_appreciated" in f:
            offer("reciprocate_enjoyment", "reciprocated", 72)
        if ("open_to_more" in f and "partner_positive" in f
                and "partner_pace" not in f and "partner_declined" not in f
                and "partner_invited" not in f):
            offer("consider_another_date", "invited", 86)
        if ("partner_invited" not in f and "invited" not in f
                and "partner_declined" not in f and "partner_pace" not in f):
            offer("learn_partner_view", "asked_feeling", 48)
        # Ending is a legitimate autonomous choice, not a forced success state.
        offer("conclude_evening", "said_goodnight", 12)
        return candidates

    def propose(self) -> SocialDecision | None:
        if self.pending is not None:
            raise RuntimeError("Cannot plan another utterance before acknowledgement")
        options = []
        for goal_name, goal_facts, value in self._goals():
            if goal_facts.issubset(self.facts):
                continue
            self.planning_calls += 1
            try:
                plan = self.planner.plan(
                    self.facts, goal_facts, excluded=self.blocked,
                )
            except PlanUnavailable:
                continue
            self.expanded_states += plan.expanded_states
            if not plan.actions:
                continue
            # Compare competing goals on utility net of their GOAP path cost.
            utility = value - plan.total_cost * 3
            options.append((utility, value, -plan.total_cost,
                            goal_name, plan))
        if not options:
            return None
        _utility, _value, _cost, goal_name, plan = max(
            options, key=lambda item: (item[0], item[1], item[2], item[3])
        )
        action = plan.actions[0]
        decision = SocialDecision(
            actor=self.name, goal=goal_name,
            plan=tuple(step.name for step in plan.actions),
            cost=plan.total_cost, expansions=plan.expanded_states,
            action=action.name, line=LINES[action.name],
        )
        self.pending = decision
        return decision

    def confirm_spoken(self, line: str) -> None:
        """Only after the world or test-room confirms the actual speaker's line."""
        pending = self.pending
        if pending is None or pending.line != line:
            raise PermissionError("No matching, outstanding utterance to confirm")
        action = next(a for a in SOCIAL_ACTIONS if a.name == pending.action)
        if not action.applicable(self.facts):
            raise RuntimeError("A newly observed circumstance invalidated the act")
        self.facts.difference_update(action.removes)
        self.facts.update(action.adds)
        self.pending = None

    def refuse(self, reason: str) -> None:
        if self.pending is None:
            raise RuntimeError("No social action awaiting a world response")
        if not reason:
            raise ValueError("A refusal reason is required")
        self.blocked.add(self.pending.action)
        self.pending = None

    def hear(self, *, sender: str, event_id: str, line: str) -> bool:
        """Interpret *heard words*, never the other actor's chosen GOAP goal."""
        if sender == self.name or not event_id:
            raise PermissionError("Hearing requires a distinct, identified speaker")
        if event_id in self.seen:
            return False
        self.seen.add(event_id)
        new = set(HEARD_CUES.get(line, ()))
        if not new:
            new.add("heard_unclassified")
        if new - self.facts:
            self.blocked.clear()
        self.facts.update(new)
        return True


class OfflineApartment:
    """Disposable text relay for focused GOAP tests, not an Evennia simulation."""

    def __init__(self, woman: SocialGoapActor, man: SocialGoapActor):
        if woman is man or woman.name == man.name:
            raise ValueError("Two distinct agents are required")
        self.people = (woman, man)
        self.transcript: list[dict] = []

    def step(self, speaker: SocialGoapActor) -> bool:
        if speaker not in self.people:
            raise PermissionError("Unknown apartment visitor")
        decision = speaker.propose()
        if decision is None:
            return False
        # Only spoken words pass across the social boundary. The other
        # participant cannot inspect goal, plan, motive or private facts.
        listener = next(a for a in self.people if a is not speaker)
        event_id = f"offline-apartment-{len(self.transcript) + 1}"
        speaker.confirm_spoken(decision.line)
        listener.hear(sender=speaker.name, event_id=event_id, line=decision.line)
        self.transcript.append({
            "speaker": speaker.name, "line": decision.line,
            "goal": decision.goal, "plan": list(decision.plan),
            "action": decision.action, "goap_cost": decision.cost,
            "goap_expansions": decision.expansions,
        })
        return True

    def run(self, *, turn_cap: int = 24) -> dict:
        if not (1 <= turn_cap <= 100):
            raise ValueError("Bounded test requires 1-100 total turns")
        for turn in range(turn_cap):
            actor = self.people[turn % len(self.people)]
            self.step(actor)
            if all("said_goodnight" in p.facts for p in self.people):
                break
        complete = all("said_goodnight" in p.facts for p in self.people)
        return {
            "status": "complete" if complete else "turn_capped",
            "scope": "model_free_goap_offline_apartment",
            "turns": len(self.transcript),
            "model_calls": sum(p.model_calls for p in self.people),
            "planning_calls": {p.name: p.planning_calls for p in self.people},
            "private_facts": {p.name: sorted(p.facts) for p in self.people},
            "transcript": list(self.transcript),
        }


def make_pair(*, variant: str = "cautious"):
    """Both enjoyed the date; future interest and comfort are still private."""
    if variant not in ("cautious", "mutual", "mismatch"):
        raise ValueError("Unknown social comparison variant")
    woman = SocialGoapActor(
        "Clara", interest=79, caution=82 if variant == "cautious" else 28,
    )
    man = SocialGoapActor(
        "Ben", interest=30 if variant == "mismatch" else 86, caution=30,
    )
    return woman, man


def run_offline(*, variant: str = "cautious", turn_cap: int = 24) -> dict:
    return OfflineApartment(*make_pair(variant=variant)).run(turn_cap=turn_cap)


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Two-person model-free GOAP social pilot")
    parser.add_argument("--variant", choices=("cautious", "mutual", "mismatch"),
                        default="cautious")
    parser.add_argument("--turn-cap", type=int, default=24)
    args = parser.parse_args()
    print(json.dumps(run_offline(variant=args.variant, turn_cap=args.turn_cap),
                     indent=2))
