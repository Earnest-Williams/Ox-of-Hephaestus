"""G7b: independently planned, bounded social interaction and genuine bargaining.

The reusable operators/terms live in ox_ai.social. This apartment is only a
scenario adapter. Every goal is compared by a private utility and the existing
GoapPlanner. The offline room acts as a deliberately labelled authoritative
fake world; it validates exact offer revisions and observed actions. It is
NOT a game-side persistent agreement ledger or a general language model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Literal

from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable
from ox_ai.social.contracts import (
    ACTIVITIES, CONSIDERATIONS, PHYSICAL, ContractBoard,
    NegotiationEvent, Offer, Terms,
)
from ox_ai.social.domain import ACTION_BY_NAME, SOCIAL_OPERATORS

LABELS = {
    "another_date": "go out again", "stay_longer": "stay a little longer tonight",
    "stay_overnight": "stay overnight", "private_intimacy": "share a more intimate evening",
    "sit_together": "sit together", "move_closer": "move a little closer",
    "cuddle": "cuddle", "hold_hands": "hold hands",
    "hug": "share a hug", "kiss": "share a kiss", "quiet_company": "keep each other company",
    "walk_together": "walk together", "talk_privately": "talk privately",
    "share_secret": "share a confidence", "provide_information": "share information",
    "offer_introduction": "make an introduction", "practical_help": "offer practical help",
    "shift_swap": "swap shifts", "lend_equipment": "lend equipment",
    "share_supplies": "share supplies", "assist_task": "help with a task",
    "joint_investigation": "investigate together",
    "protect_reputation": "protect our reputations",
    "keep_confidence": "keep a confidence", "share_meal": "share a meal",
    "exchange_contact": "exchange contact details", "emotional_support": "provide emotional support",
    "lend_money": "lend money", "give_transport": "provide transport",
    "provide_shelter": "offer shelter", "exchange_funds": "exchange funds",
    "contract_work": "agree on paid work", "public_endorsement": "give a public endorsement",
    "share_credit": "share credit", "meet_friends": "meet friends",
    "future_commitment": "make a longer-term commitment",
}
CONSIDERATION_LABELS = {
    "none": "", "extra_time": "more time together", "help": "practical help",
    "payment": "payment", "shelter": "temporary shelter",
    "transport": "transport", "protection": "protection", "public_credit": "public credit",
    "information": "information I can share", "future_favor": "a future favor",
    "confidentiality": "confidentiality", "shared_risk": "sharing the risk",
    "resource": "a resource I can contribute", "introduction": "an introduction",
}
# More intimate activities are not prerequisites for any other activity. This
# ordering is only one option an actor can explore when proposing an alternative.
SOFTER = {
    "private_intimacy": ("kiss", "cuddle", "hug", "sit_together", "quiet_company"),
    "stay_overnight": ("stay_longer", "quiet_company"),
    "kiss": ("cuddle", "hug", "hold_hands", "sit_together", "quiet_company"),
    "cuddle": ("hug", "hold_hands", "sit_together"),
    "hug": ("hold_hands", "sit_together", "quiet_company"),
    "hold_hands": ("sit_together", "quiet_company"),
    "stay_longer": ("quiet_company", "talk_privately"),
    "another_date": ("talk_privately",),
    "share_secret": ("talk_privately",),
    "shift_swap": ("assist_task",),
}


def clamp(x: float) -> int:
    return max(0, min(100, round(x)))


@dataclass(frozen=True, slots=True)
class Disposition:
    # Nonsexual motivation and strategic reasons are independent of affection.
    affection: int = 55
    curiosity: int = 50
    companionship: int = 50
    pragmatism: int = 25
    reciprocity: int = 45
    duty: int = 20
    social_expectation: int = 15
    caution: int = 35
    anxiety: int = 25
    assertiveness: int = 55
    patience: int = 50
    consideration_values: tuple[tuple[str, int], ...] = ()

    def __post_init__(self):
        keys = ("affection", "curiosity", "companionship", "pragmatism",
                "reciprocity", "duty", "social_expectation", "caution",
                "anxiety", "assertiveness", "patience")
        if any(type(getattr(self, x)) is not int or not 0 <= getattr(self, x) <= 100
               for x in keys):
            raise ValueError("Disposition values must be 0-100 integers")
        if any(k not in CONSIDERATIONS or k == "none" or type(v) is not int
               or not 0 <= v <= 100 for k, v in self.consideration_values):
            raise ValueError("Malformed private consideration value")
        if len({k for k, _ in self.consideration_values}) != len(self.consideration_values):
            raise ValueError("Repeated private consideration value")


@dataclass(frozen=True, slots=True)
class SocialChoice:
    speaker: str
    goal: str
    action: str
    verb: Literal["say", "pose"]
    line: str
    plan: tuple[str, ...]
    cost: int
    goal_utility: int
    offer_id: str | None = None
    revision: int | None = None
    response: str | None = None
    terms: Terms | None = None
    # Operator-only analysis. Never delivered to the other mind.
    private_motivation: str = ""


@dataclass(frozen=True, slots=True)
class PublicObservation:
    event_id: str
    speaker: str
    line: str
    kind: str
    offer_id: str | None = None
    revision: int | None = None
    terms: Terms | None = None
    response: str | None = None
    initiator: str | None = None


class SocialGoapMind:
    """Owns subjective interpretations; it never reads the world board."""

    def __init__(self, name: str, disposition: Disposition, *, context: str = "date"):
        if not name or context not in ("date", "work", "trade"):
            raise ValueError("Expected one named adult and a known setting")
        self.name = name
        self.disposition = disposition
        self.context = context
        self.beliefs = {"together", "experienced_date" if context == "date" else "colleague_present"}
        self.emotion = {
            "comfort": clamp(55 - disposition.anxiety // 4),
            "trust": 50, "hope": 55 if disposition.affection > 60 else 42,
            "uncertainty": clamp(45 + disposition.anxiety // 4),
            "resentment": 0, "fatigue": 10,
        }
        self.heard_ids: set[str] = set()
        self.completed: set[str] = set()
        self.spoken_activity: set[str] = set()
        self.known_offer: Offer | None = None
        self.own_agreements: dict[str, Terms] = {}
        self.performed: set[str] = set()
        self.closed_offers: set[str] = set()
        self.pending: SocialChoice | None = None
        self.planner_calls = 0
        self.planner_expansions = 0
        self.model_calls = 0
        self.information: list[str] = []
        self.private_assent: dict[str, str] = {}
        self.last_plan: tuple[str, ...] = ()
        self.initiated = 0
        self.partner_declines = 0
        self.heard_activities: set[str] = set()
        self.accepted_activities: set[str] = set()
        self.partner_left = False
        self.delivered: set[str] = set()
        self.asked_for_delivery: set[str] = set()
        self.known_resources: set[str] = set()
        self.revision = 0

    def _consideration_value(self, consideration: str) -> float:
        if consideration == "none":
            return 0
        vals = dict(self.disposition.consideration_values)
        return float(vals.get(consideration, self.disposition.pragmatism * .55))

    def activity_value(self, terms: Terms) -> tuple[int, str]:
        """Net *private* utility, not objective morality or proof of liking.

        An actor can find an agreement beneficial without affection. A low
        affinity/high external-benefit agreement remains coded instrumental;
        a threat does not become proof of enjoyment or desire.
        """
        d, e, a = self.disposition, self.emotion, terms.activity
        # Different opportunity/value curves, usable in shipboard contexts.
        if a in ("another_date", "stay_longer", "stay_overnight", "talk_privately", "meet_friends", "future_commitment"):
            intrinsic = .53 * d.affection + .31 * d.companionship + .14 * d.curiosity
            discomfort = .18 * d.caution + .12 * e["uncertainty"]
            if a == "stay_overnight":
                discomfort += 15 + .28 * d.caution
        elif a in ("quiet_company", "sit_together", "move_closer", "walk_together", "share_meal"):
            intrinsic = .42 * d.affection + .41 * d.companionship + .12 * d.curiosity
            discomfort = .16 * d.caution + .10 * e["uncertainty"]
        elif a in ("hold_hands", "hug", "cuddle"):
            intrinsic = .68 * d.affection + .16 * d.companionship + .12 * d.curiosity
            discomfort = .33 * d.caution + .18 * e["uncertainty"]
        elif a in ("kiss", "private_intimacy"):
            intrinsic = .80 * d.affection + .10 * d.curiosity
            discomfort = (.62 * d.caution + .24 * e["uncertainty"]
                          + (22 if a == "private_intimacy" else 0))
        elif a in ("practical_help", "assist_task", "joint_investigation", "shift_swap"):
            intrinsic = .44 * d.duty + .35 * d.pragmatism + .20 * d.reciprocity
            discomfort = .19 * d.caution
        else:
            intrinsic = .38 * d.pragmatism + .28 * d.curiosity + .20 * d.reciprocity
            discomfort = .19 * d.caution
        # Value from obligation, curiosity, social continuity, instrumental
        # payoff is independent of how affectionate the person feels.
        auxiliary = (.16 * d.duty + .09 * d.social_expectation
                     + .07 * d.pragmatism + .12 * e["trust"]
                     + .06 * e["comfort"] - .18 * e["resentment"])
        concession = self._consideration_value(terms.consideration) * .65
        if terms.scope == "limited":
            discomfort *= .55
            intrinsic *= .82
        elif terms.scope == "ongoing":
            discomfort *= 1.8
        elif terms.scope == "later":
            discomfort *= .72
        if e["resentment"] >= 75:
            discomfort += 95  # substantial new aversion can undo prior interest
        utility = round(intrinsic + auxiliary + concession - discomfort - 18)
        reason = "instrumental" if (concession + .20 * d.pragmatism + .12 * d.duty >
                                   intrinsic * .7) else "personal"
        if d.social_expectation >= 80 and d.affection <= 30:
            reason = "social_obligation"
        return utility, reason

    def _perspective_value(self, offer: Offer, terms: Terms) -> tuple[int, str]:
        """Concession is a COST to its promisor and a benefit to the other."""
        value, reason = self.activity_value(terms)
        if self.name == offer.initiator and terms.consideration != "none":
            if terms.consideration not in self.known_resources:
                return -100, "cannot_deliver_promised_consideration"
            # activity_value included the received-benefit term; remove it
            # and debit the issuer's own opportunity cost of delivering it.
            price = self._consideration_value(terms.consideration)
            value -= round(price * 1.10 + price * .65)
            reason = "instrumental_offer_cost"
        return value, reason

    def _response(self, offer: Offer) -> tuple[str, Terms | None, int, str]:
        utility, reason = self._perspective_value(offer, offer.terms)
        if self.emotion["resentment"] >= 75:
            return "decline", None, utility, "resentment"
        if utility >= 35:
            return "accept", None, utility, reason
        candidates: list[tuple[int, Terms]] = []
        t = offer.terms
        if t.scope in ("tonight", "ongoing", "one_time"):
            new = Terms(t.activity, t.consideration, "limited")
            val, _ = self._perspective_value(offer, new)
            if val > utility + 3:
                candidates.append((val, new))
        for replacement in SOFTER.get(t.activity, ()):
            new = Terms(replacement, t.consideration, "limited")
            val, _ = self._perspective_value(offer, new)
            if val > utility + 4:
                candidates.append((val, new))
        for consideration in ("information", "help", "extra_time", "future_favor",
                              "introduction", "shared_risk"):
            if consideration == t.consideration:
                continue
            new = Terms(t.activity, consideration, "limited", "before")
            val, _ = self._perspective_value(offer, new)
            if val > utility + 5:
                candidates.append((val, new))
        if candidates and offer.revision < 4:
            val, terms = max(candidates, key=lambda item: (item[0], -len(item[1].activity)))
            if val >= 31 and self.disposition.assertiveness >= 25:
                return "counter", terms, val, "renegotiate_" + reason
        if utility > -5 and self.disposition.patience >= 60:
            return "defer", None, utility, reason
        return "decline", None, utility, reason

    @staticmethod
    def _proposal_line(terms: Terms, *, counter: bool = False) -> str:
        opener = "Would you consider " if counter else "Would you like to "
        suffix = ""
        if terms.scope == "limited":
            suffix = " just briefly"
        elif terms.scope == "later":
            suffix = " another time"
        elif terms.scope == "ongoing":
            suffix = " regularly"
        line = opener + LABELS[terms.activity] + suffix + "?"
        if terms.consideration != "none":
            benefit = CONSIDERATION_LABELS[terms.consideration]
            if counter:
                line += " If you could offer " + benefit
                line += " first." if terms.exchange_order == "before" else "."
            else:
                line += " In return, I can offer " + benefit + "."
        return line

    def _response_line(self, answer: str, offer: Offer, terms: Terms | None) -> str:
        if answer == "counter":
            assert terms is not None
            return self._proposal_line(terms, counter=True)
        if answer == "accept":
            return "Yes, I agree to " + LABELS[offer.terms.activity] + " under those terms."
        if answer == "defer":
            return "I'm interested in discussing that, but I need more time."
        if answer == "decline":
            return "No, I don't want that arrangement."
        raise ValueError(answer)

    def _proposals(self) -> list[tuple[int, Terms, str]]:
        d, e = self.disposition, self.emotion
        if self.partner_declines > 0 or self.initiated >= 3:
            return []
        acts = (("another_date", "stay_longer", "stay_overnight", "sit_together",
                 "move_closer", "hold_hands", "hug", "cuddle", "kiss",
                 "private_intimacy", "quiet_company", "talk_privately")
                if self.context == "date" else
                ("assist_task", "joint_investigation", "shift_swap",
                 "provide_information", "lend_equipment", "keep_confidence"))
        entries = []
        for activity in acts:
            if activity in self.spoken_activity or activity in self.heard_activities:
                continue
            if (activity in ("kiss", "hug", "cuddle", "private_intimacy") and e["trust"] < 45
                    and d.assertiveness < 90):
                continue
            if activity in ("kiss", "private_intimacy") and e["comfort"] < 46:
                continue
            if activity in ("kiss", "hug", "cuddle", "private_intimacy", "hold_hands") and e["resentment"] > 30:
                continue
            # Proposers get no automatic knowledge of a partner's preference.
            # Scope and concession are independently selected based on expected
            # cost, disposition and plausible practical objectives.
            opts = [Terms(activity, "none", "tonight" if activity == "stay_longer" else "one_time")]
            if d.pragmatism > 65 and "information" in self.known_resources:
                opts.append(Terms(activity, "information", "limited"))
            if d.reciprocity > 65 and "help" in self.known_resources:
                opts.append(Terms(activity, "help", "limited"))
            best = None
            for terms in opts:
                utility, reason = self.activity_value(terms)
                if terms.consideration != "none":
                    price = self._consideration_value(terms.consideration)
                    utility -= round(price * 1.75)
                # Encourage non-verbal closeness when the person values it,
                # without knowing whether the other person reciprocates.
                if activity == "hold_hands":
                    utility += round(max(0, d.affection - 45) * .34)
                if activity in ("hug", "cuddle"):
                    utility += round(max(0, d.affection - 50) * .24)
                if activity in ("kiss", "private_intimacy"):
                    utility += round(max(0, d.affection - 55) * .40)
                if activity in ("another_date", "talk_privately"):
                    utility -= 6
                # More elaborate bargains cost more to make and possibly
                # require giving something; attraction never auto-succeeds.
                offered_cost = 9 if terms.consideration == "none" else 27
                risk = 6 if activity in PHYSICAL else 0
                score = round(utility + d.assertiveness*.12 + e["hope"]*.14
                              - offered_cost - risk - e["fatigue"]*.12)
                if best is None or score > best[0]:
                    best = (score, terms, reason)
            if best:
                # Each offered agreement satisfies some of the actor's aims.
                # There is no infinite incentive to request the whole menu.
                score, terms, reason = best
                score -= self.initiated * 14
                if self.accepted_activities:
                    score -= len(self.accepted_activities) * 7
                if score >= 24:
                    entries.append((score, terms, reason))
        return entries

    def _choose_plan(self, candidates):
        """Compete goal utilities over actual STRIPS paths, not if/elif script."""
        options = []
        for utility, goal, target_fact, extra_action, meta in candidates:
            actions = [a.goap() for a in SOCIAL_OPERATORS if (
                a.category != "proximity" and
                (extra_action is None or a.name != extra_action.name)
            )]
            if extra_action is not None:
                actions.append(extra_action)
            self.planner_calls += 1
            try:
                plan = GoapPlanner(actions, expansion_cap=1600).plan(
                    self.beliefs, (target_fact,),
                )
            except PlanUnavailable:
                continue
            self.planner_expansions += plan.expanded_states
            if not plan.actions:
                continue
            # Limit artificially cheap indirect facts; only plan the first
            # physical/speech action, then re-evaluate after world feedback.
            score = utility - plan.total_cost * 5
            options.append((score, utility, -plan.total_cost,
                            goal, plan, meta, extra_action))
        if not options:
            return None
        return max(options, key=lambda item: (item[0], item[1], item[2], item[3]))

    def propose(self) -> SocialChoice | None:
        if self.pending is not None:
            raise RuntimeError("Unconfirmed social action is still pending")
        if "ended" in self.beliefs:
            return None
        offered: list[tuple[int, str, str, GoapAction | None, object]] = []
        offer = self.known_offer
        if self.partner_left:
            # An actual goodbye is evidence of a conversation ending; a
            # partner cannot make a new offer into someone's absence.
            offered.append((400, "reply_to_goodbye", "ended", None, None))
        if offer and offer.state == "pending" and not self.partner_left:
            if offer.recipient == self.name:
                answer, counter, worth, reason = self._response(offer)
                act = GoapAction(
                    "respond_" + answer, frozenset({"heard_offer"}),
                    frozenset({"response_posted"}), cost=1,
                    verb="say", target="respond_" + answer,
                )
                offered.append((200 + worth//5, "respond_"+answer,
                                "response_posted", act,
                                (offer, answer, counter, reason)))
            else:
                # Wait on the other person's actual choice rather than file a
                # synthetic acceptance on their behalf. Can still converse.
                pass
        if (offer and offer.state == "accepted" and not self.partner_left
                and offer.offer_id not in self.performed):
            if offer.proposer == self.name or offer.recipient == self.name:
                worth, reason = self.activity_value(offer.terms)
                if (offer.terms.consideration != "none"
                        and offer.terms.exchange_order == "before"
                        and offer.offer_id not in self.delivered):
                    if (offer.initiator == self.name
                            and offer.terms.consideration in self.known_resources):
                        delivery = GoapAction(
                            "deliver_consideration", frozenset({"agreement_known"}),
                            frozenset({"consideration_fulfilled"}), cost=2,
                            verb="say", target="deliver_consideration",
                        )
                        offered.append((212, "fulfil_bargain_obligation",
                                        "consideration_fulfilled", delivery,
                                        (offer, "deliver", None, "obligation")))
                    elif (offer.initiator != self.name
                          and offer.offer_id not in self.asked_for_delivery):
                        request = GoapAction(
                            "request_delivery", frozenset({"agreement_known"}),
                            frozenset({"delivery_requested"}), cost=1,
                            verb="say", target="request_delivery",
                        )
                        offered.append((145, "seek_bargain_fulfillment",
                                        "delivery_requested", request,
                                        (offer, "request_delivery", None, reason)))
                if (worth >= 20 and offer.terms.activity in PHYSICAL
                        and (offer.terms.consideration == "none"
                             or offer.terms.exchange_order != "before"
                             or offer.offer_id in self.delivered)):
                    action = GoapAction(
                        "perform_agreement", frozenset({"agreed_"+offer.terms.activity}),
                        frozenset({"performed_"+offer.terms.activity}), cost=2,
                        verb="pose", target=offer.terms.activity,
                    )
                    offered.append((138 + worth//5, "fulfil_specific_agreement",
                                    "performed_"+offer.terms.activity, action,
                                    (offer, "perform", None, reason)))
                elif worth < 0:
                    action = GoapAction(
                        "withdraw_agreement", frozenset({"agreement_known"}),
                        frozenset({"agreement_withdrawn"}), cost=1,
                        verb="say", target="withdraw_agreement",
                    )
                    offered.append((220, "revoke_unwanted_agreement",
                                    "agreement_withdrawn", action,
                                    (offer, "withdraw", None, reason)))
        if "conversation_open" not in self.beliefs:
            offered.append((90, "make_contact", "conversation_open", None, None))
        if "warmth_expressed" not in self.beliefs:
            offered.append((95, "express_appreciation", "warmth_expressed", None, None))
        if "heard_warmth" in self.beliefs and "warmth_returned" not in self.beliefs:
            offered.append((84, "reciprocate", "warmth_returned", None, None))
        if "heard_boundary" in self.beliefs and "boundary_acknowledged" not in self.beliefs:
            offered.append((170, "respect_boundary", "boundary_acknowledged", None, None))
        if "heard_uncertainty" in self.beliefs and "reassured" not in self.beliefs:
            offered.append((110, "offer_reassurance", "reassured", None, None))
        if (self.disposition.caution >= 70 and "uncertainty_expressed" not in self.beliefs
                and "warmth_expressed" in self.beliefs):
            offered.append((90, "express_hesitation", "uncertainty_expressed", None, None))
        if (self.disposition.caution >= 70 and "preference_stated" not in self.beliefs
                and "uncertainty_expressed" in self.beliefs):
            offered.append((91, "communicate_pace", "preference_stated", None, None))
        if "heard_hurt" in self.beliefs and "hurt_acknowledged" not in self.beliefs:
            offered.append((178, "acknowledge_hurt", "hurt_acknowledged", None, None))
        if self.emotion["uncertainty"] >= 73 and "feeling_asked" not in self.beliefs:
            offered.append((78, "understand_other", "feeling_asked", None, None))
        if (self.disposition.anxiety >= 75 and self.emotion["uncertainty"] >= 65
                and "time_requested" not in self.beliefs):
            offered.append((75, "request_time", "time_requested", None, None))
        if (not (offer and offer.state == "pending") and not self.partner_left
                and "warmth_expressed" in self.beliefs):
            for utility, terms, reason in self._proposals():
                fact = "proposed_" + terms.activity
                extra = GoapAction(
                    "propose_" + terms.activity, frozenset({"conversation_open", "warmth_expressed"}),
                    frozenset({fact}), cost=2, verb="say", target=terms.activity,
                )
                offered.append((utility + 52, "pursue_"+terms.activity,
                                fact, extra, (None, "propose", terms, reason)))
        if not (offer and offer.state == "pending") or self.partner_left:
            # Departing is a real option; it becomes attractive with fatigue,
            # disappointment or when no beneficial offers remain.
            fatigue = self.emotion["fatigue"]
            ending = (13 + fatigue // 2 + self.emotion["resentment"] // 2
                      + self.initiated * 16 + self.partner_declines * 100
                      + len(self.accepted_activities) * 12)
            if "warmth_expressed" in self.beliefs:
                offered.append((ending, "conclude_evening", "ended", None, None))
        # Re-adding a one-time speech act is ineligible unless circumstances
        # are materially new. Prevent repeated 'same line' attempts.
        offered = [opt for opt in offered if opt[2] not in self.beliefs]
        selection = self._choose_plan(offered)
        if selection is None:
            return None
        _score, utility, _cost, goal, plan, meta, _extra = selection
        action = plan.actions[0]
        name = action.name
        offer_id = revision = response = terms = None
        reason = ""
        line = ACTION_BY_NAME[name].line if name in ACTION_BY_NAME else ""
        if name.startswith("propose_"):
            assert meta is not None
            _, response, terms, reason = meta
            line = self._proposal_line(terms)
        elif name.startswith("respond_"):
            assert meta is not None
            off, response, terms, reason = meta
            offer_id, revision = off.offer_id, off.revision
            line = self._response_line(response, off, terms)
        elif name in ("perform_agreement", "withdraw_agreement", "deliver_consideration", "request_delivery"):
            assert meta is not None
            off, response, _, reason = meta
            offer_id, revision = off.offer_id, off.revision
            terms = off.terms
            if name == "perform_agreement":
                line = ACTION_BY_NAME[terms.activity].line
            elif name == "deliver_consideration":
                line = "I can now provide the " + CONSIDERATION_LABELS[terms.consideration] + " we agreed on."
            elif name == "request_delivery":
                line = "Before we go ahead, could you provide the " + CONSIDERATION_LABELS[terms.consideration] + " we agreed on?"
            else:
                line = ACTION_BY_NAME["withdraw_agreement"].line
        # A GOAP intermediary action is not secretly upgraded to a planned
        # offer; only an action that actually happens changes speaker facts.
        decision = SocialChoice(
            self.name, goal, name, action.verb, line,
            tuple(a.name for a in plan.actions), plan.total_cost,
            utility, offer_id, revision, response, terms, reason,
        )
        self.pending = decision
        self.last_plan = decision.plan
        return decision

    def confirmed(self, move: SocialChoice) -> None:
        if self.pending != move:
            raise PermissionError("No matching pending speech or action")
        if move.action in ACTION_BY_NAME and move.action != "withdraw_agreement":
            action = ACTION_BY_NAME[move.action].goap()
            if not action.applicable(self.beliefs):
                raise RuntimeError("Social plan became inapplicable before effect")
            self.beliefs.difference_update(action.removes)
            self.beliefs.update(action.adds)
        elif move.action.startswith("propose_"):
            if move.terms is None:
                raise RuntimeError("Proposal missing typed terms")
            self.beliefs.add("proposed_" + move.terms.activity)
            self.spoken_activity.add(move.terms.activity)
            self.initiated += 1
        elif move.action.startswith("respond_"):
            self.beliefs.add("response_posted")
        elif move.action == "perform_agreement":
            self.performed.add(move.offer_id)
            self.beliefs.add("performed_"+move.terms.activity)
        elif move.action == "withdraw_agreement":
            self.beliefs.add("agreement_withdrawn")
        elif move.action == "deliver_consideration":
            self.delivered.add(move.offer_id)
            self.beliefs.add("consideration_fulfilled")
        elif move.action == "request_delivery":
            self.asked_for_delivery.add(move.offer_id)
            self.beliefs.add("delivery_requested")
        else:
            raise ValueError("Unknown GOAP action")
        self.completed.add(move.action)
        self.pending = None
        self.revision += 1
        self.emotion["fatigue"] = clamp(self.emotion["fatigue"] + 3)

    def observe(self, observation: PublicObservation) -> bool:
        if observation.event_id in self.heard_ids:
            return False
        if observation.speaker == self.name:
            return False
        self.heard_ids.add(observation.event_id)
        self.information.append(observation.line)
        kind = observation.kind
        if kind == "speech":
            if observation.line == ACTION_BY_NAME["end_interaction"].line:
                self.partner_left = True
                self.beliefs.add("partner_goodnight")
            if any(s in observation.line.lower() for s in ("enjoyed", "glad", "nice")):
                self.beliefs.add("heard_warmth")
                self.emotion["hope"] = clamp(self.emotion["hope"] + 8)
                self.emotion["comfort"] = clamp(self.emotion["comfort"] + 6)
            if any(s in observation.line.lower() for s in ("nervous", "unsure", "not sure")):
                self.beliefs.add("heard_uncertainty")
                self.emotion["uncertainty"] = clamp(self.emotion["uncertainty"] + 10)
            if any(s in observation.line.lower() for s in ("not comfortable", "take this slowly")):
                self.beliefs.add("heard_boundary")
                self.emotion["comfort"] = clamp(self.emotion["comfort"] - 5)
            if "hurt" in observation.line.lower():
                self.beliefs.add("heard_hurt")
            if "how are you feeling" in observation.line.lower():
                self.beliefs.add("heard_question")
        elif kind in ("proposed", "countered"):
            assert observation.terms is not None and observation.offer_id is not None
            self.known_offer = Offer(
                observation.offer_id, observation.revision,
                observation.speaker, self.name, observation.initiator or observation.speaker,
                observation.terms, "pending", 0, 0,
            )
            self.beliefs.add("heard_offer")
            self.heard_activities.add(observation.terms.activity)
            self.beliefs.discard("response_posted")
            self.emotion["hope"] = clamp(self.emotion["hope"] + 4)
            self.emotion["uncertainty"] = clamp(self.emotion["uncertainty"] + 5)
        elif kind in ("accepted", "declined", "deferred", "withdrawn", "expired"):
            # Offer state is a PUBLIC outcome, not a certification of feelings.
            if self.known_offer and self.known_offer.offer_id == observation.offer_id:
                self.known_offer = Offer(
                    self.known_offer.offer_id, observation.revision,
                    self.known_offer.proposer, self.known_offer.recipient,
                    self.known_offer.initiator, observation.terms, kind, 0, 0,
                    accepted_by=(self.known_offer.proposer, self.known_offer.recipient)
                    if kind == "accepted" else (),
                )
            self.beliefs.discard("heard_offer")
            if kind == "accepted":
                self.beliefs.add("agreed_"+observation.terms.activity)
                self.accepted_activities.add(observation.terms.activity)
                self.beliefs.add("agreement_known")
                self.emotion["hope"] = clamp(self.emotion["hope"] + 14)
                self.emotion["trust"] = clamp(self.emotion["trust"] + 8)
            elif kind == "declined":
                self.beliefs.add("heard_boundary")
                self.partner_declines += 1
                self.emotion["hope"] = clamp(self.emotion["hope"] - 20)
                self.emotion["uncertainty"] = clamp(self.emotion["uncertainty"] + 5)
            elif kind == "withdrawn":
                self.emotion["trust"] = clamp(self.emotion["trust"] - 10)
                self.emotion["uncertainty"] = clamp(self.emotion["uncertainty"] + 18)
        elif kind == "consideration_delivered":
            if self.known_offer and self.known_offer.offer_id == observation.offer_id:
                self.delivered.add(observation.offer_id)
                self.beliefs.add("consideration_fulfilled")
                self.emotion["trust"] = clamp(self.emotion["trust"] + 8)
        elif kind == "performed":
            if self.known_offer and self.known_offer.offer_id == observation.offer_id:
                self.performed.add(observation.offer_id)
                self.beliefs.add("performed_"+observation.terms.activity)
                self.emotion["trust"] = clamp(self.emotion["trust"] + 5)
                self.emotion["comfort"] = clamp(self.emotion["comfort"] + 4)
        self.revision += 1
        return True

    def private_news(self, *, hope_delta: int = 0, comfort_delta: int = 0,
                     resentment_delta: int = 0, uncertainty_delta: int = 0) -> None:
        """External firsthand information can change preferences, not past facts."""
        for key, delta in (("hope", hope_delta), ("comfort", comfort_delta),
                           ("resentment", resentment_delta),
                           ("uncertainty", uncertainty_delta)):
            self.emotion[key] = clamp(self.emotion[key] + delta)
        self.revision += 1


class ApartmentExpanded:
    """Finite deterministic world adapter; not a replacement for Evennia."""

    def __init__(self, clara: SocialGoapMind, ben: SocialGoapMind):
        if clara is ben or clara.name == ben.name:
            raise ValueError("Two independent characters required")
        self.people = (clara, ben)
        self.board = ContractBoard(ttl=12)
        self.trace: list[dict] = []
        self._message_id = 0
        # World-owned demonstration resources, privately observed by holders.
        self.resources = {p.name: {"information": 1, "help": 1, "resource": 1}
                          for p in self.people}
        for p in self.people:
            p.known_resources.update(self.resources[p.name])

    def _broadcast(self, actor: SocialGoapMind, line: str, kind: str,
                   event: NegotiationEvent | None = None) -> None:
        self._message_id += 1
        for p in self.people:
            if p is actor:
                continue
            p.observe(PublicObservation(
                f"spoken-{self._message_id:04d}", actor.name, line, kind,
                event.offer_id if event else None,
                event.revision if event else None,
                event.terms if event else None,
                initiator=self.board.offers[event.offer_id].initiator if event else None,
            ))
        if event and kind == "countered":
            # The new addressee is the old proposer. It only learns the
            # counteroffer from these public terms, not the other mind's score.
            pass

    def step(self, index: int, *, confirmed_choice: SocialChoice | None = None) -> bool:
        """Commit ONE attempt after the outer world reports its command occurred.

        Offline probes use the fake world directly. An authenticated live
        adapter must supply a previously proposed choice *only after*
        confirming the ordinary game client's actual speaker/listener output.
        Neither planned speech nor an unsent gesture receives an effect.
        """
        if not 0 <= index < 2:
            raise IndexError(index)
        mind = self.people[index]
        if confirmed_choice is None:
            choice = mind.propose()
        else:
            if mind.pending != confirmed_choice:
                raise PermissionError("Unmatched or stale externally confirmed choice")
            choice = confirmed_choice
        self.board.turn += 1
        if choice is None:
            return False
        event = None
        try:
            if choice.action.startswith("propose_"):
                recipient = self.people[1-index]
                event = self.board.propose(mind.name, recipient.name, choice.terms)
                kind = event.kind
            elif choice.action.startswith("respond_"):
                event = self.board.reply(
                    mind.name, choice.offer_id, choice.revision, choice.response,
                    counter=choice.terms if choice.response == "counter" else None,
                )
                kind = event.kind
            elif choice.action == "withdraw_agreement":
                event = self.board.withdraw(mind.name, choice.offer_id, choice.revision)
                kind = event.kind
            elif choice.action == "deliver_consideration":
                resource = choice.terms.consideration
                if self.resources[mind.name].get(resource, 0) < 1:
                    raise PermissionError("Insufficient actual world resource")
                event = self.board.deliver_consideration(
                    mind.name, choice.offer_id, choice.revision,
                    f"resource-delivery-{len(self.trace):05d}", world_verified=True,
                )
                self.resources[mind.name][resource] -= 1
                if self.resources[mind.name][resource] == 0:
                    mind.known_resources.discard(resource)
                kind = event.kind
            elif choice.action == "perform_agreement":
                event = self.board.perform(
                    mind.name, choice.offer_id, choice.revision,
                    choice.terms.activity, f"perform-{len(self.trace):05d}",
                    parties_colocated=all("together" in p.beliefs for p in self.people),
                )
                kind = event.kind
            elif choice.action == "request_delivery":
                kind = "speech"
            else:
                kind = "speech"
        except (ValueError, PermissionError, RuntimeError) as exc:
            mind.pending = None
            raise AssertionError(f"Unacceptable fake-world action: {choice.action}: {exc}") from exc
        mind.confirmed(choice)
        # When someone ends the conversation, outstanding commitments remain
        # recorded but no new reply can be fabricated. Outstanding proposals
        # are withdrawn by the world, not accepted in their absence.
        if choice.action == "end_interaction":
            for open_offer in list(self.board.offers.values()):
                if open_offer.state == "pending" and mind.name in (open_offer.proposer, open_offer.recipient):
                    self.board.withdraw(mind.name, open_offer.offer_id, open_offer.revision)
        self._broadcast(mind, choice.line, kind, event)
        # The original proposer must learn public offer facts from its own
        # confirmed command/receipt, without being given recipient motives.
        if event is not None:
            current = self.board.offers[event.offer_id]
            if kind in ("proposed", "countered"):
                mind.known_offer = current
                mind.beliefs.add("agreement_in_discussion")
            elif kind in ("accepted", "declined", "deferred", "withdrawn", "performed", "consideration_delivered"):
                mind.known_offer = current
                if kind == "accepted":
                    mind.beliefs.add("agreement_known")
                    mind.beliefs.add("agreed_"+current.terms.activity)
                    mind.accepted_activities.add(current.terms.activity)
                if kind == "performed":
                    mind.performed.add(event.offer_id)
                if kind == "consideration_delivered":
                    mind.delivered.add(event.offer_id)
        self.trace.append({
            "turn": self.board.turn, "speaker": mind.name,
            "action": choice.action, "goal": choice.goal, "plan": list(choice.plan),
            "goap_cost": choice.cost, "goal_utility": choice.goal_utility,
            "text": choice.line, "kind": kind,
            "offer_id": event.offer_id if event else None,
            "offer_revision": event.revision if event else None,
            "terms": ({"activity": event.terms.activity,
                       "consideration": event.terms.consideration,
                       "scope": event.terms.scope,
                       "exchange_order": event.terms.exchange_order} if event else None),
            "private_motivation": choice.private_motivation,
        })
        return True

    def run(self, *, turn_cap: int = 64,
            private_stimuli: dict[int, tuple[str, dict[str, int]]] | None = None) -> dict:
        if type(turn_cap) is not int or not 1 <= turn_cap <= 120:
            raise ValueError("Finite 1-120 turn cap required")
        idle = 0
        for i in range(turn_cap):
            if private_stimuli and i in private_stimuli:
                who, update = private_stimuli[i]
                subject = next((p for p in self.people if p.name == who), None)
                if subject is None:
                    raise ValueError("Unknown recipient for private world stimulus")
                subject.private_news(**update)
            moved = self.step(i%2)
            idle = 0 if moved else idle+1
            if idle >= 2 or all("ended" in p.beliefs for p in self.people):
                break
        return {
            "status": "complete" if all("ended" in p.beliefs for p in self.people)
                      else "quiescent" if idle >= 2 else "turn_capped",
            "scope": "offline_world_validated_two_actor_goap_negotiation",
            "turns": len(self.trace), "model_calls": 0,
            "operator_count": len(SOCIAL_OPERATORS),
            "negotiation_events": len(self.board.history),
            "offers": [
                {"id": o.offer_id, "revision": o.revision, "activity": o.terms.activity,
                 "consideration": o.terms.consideration, "scope": o.terms.scope,
                 "exchange_order": o.terms.exchange_order, "state": o.state,
                 "performed": o.performed_by,
                 "delivered": o.consideration_delivered_by}
                for o in self.board.offers.values()
            ],
            "planning_calls": {p.name: p.planner_calls for p in self.people},
            "private_final_state": {
                p.name: {"emotions": dict(p.emotion), "beliefs": sorted(p.beliefs),
                         "disposition": {"affection": p.disposition.affection,
                                         "pragmatism": p.disposition.pragmatism}}
                for p in self.people
            },
            "trace": self.trace,
        }


def make_pair(variant: str = "mutual") -> tuple[SocialGoapMind, SocialGoapMind]:
    """Profile inputs, not authored action sequences or guaranteed outcomes."""
    configs = {
        "mutual": (
            Disposition(affection=88, curiosity=65, companionship=82,
                        caution=12, assertiveness=65, anxiety=12),
            Disposition(affection=85, curiosity=70, companionship=82,
                        caution=20, assertiveness=70, anxiety=12),
        ),
        "cautious": (
            Disposition(affection=78, companionship=75, caution=82,
                        assertiveness=68, patience=72, anxiety=65),
            Disposition(affection=80, companionship=80, caution=30,
                        assertiveness=60, patience=72),
        ),
        "instrumental": (
            Disposition(affection=89, companionship=75, caution=14,
                        pragmatism=35, reciprocity=60, assertiveness=82,
                        consideration_values=(("information", 3), ("help", 15))),
            Disposition(affection=18, curiosity=25, companionship=30,
                        pragmatism=94, duty=45, caution=40, assertiveness=64,
                        consideration_values=(("information", 100), ("help", 80))),
        ),
        "mismatch": (
            Disposition(affection=88, curiosity=68, companionship=82,
                        caution=15, assertiveness=67),
            Disposition(affection=8, curiosity=12, companionship=12,
                        caution=80, assertiveness=82),
        ),
        "obligation": (
            Disposition(affection=76, companionship=78, caution=21,
                        assertiveness=70),
            Disposition(affection=20, companionship=40, duty=95,
                        social_expectation=96, caution=24, assertiveness=24),
        ),
        "work_trade": (
            Disposition(affection=0, companionship=30, pragmatism=90,
                        duty=90, reciprocity=75, assertiveness=75,
                        consideration_values=(("help", 80), ("information", 74))),
            Disposition(affection=0, companionship=30, pragmatism=87,
                        duty=72, reciprocity=82, assertiveness=78,
                        consideration_values=(("information", 87), ("help", 68))),
        ),
    }
    if variant == "reconsider":
        configs[variant] = configs["mutual"]
    if variant not in configs:
        raise ValueError("Unknown social experiment profile variant")
    da, db = configs[variant]
    setting = "work" if variant == "work_trade" else "date"
    return SocialGoapMind("Clara", da, context=setting), SocialGoapMind("Ben", db, context=setting)


def run_offline(*, variant: str = "mutual", turn_cap: int = 64) -> dict:
    stimuli = ({6: ("Clara", {"resentment_delta": 100,
                              "hope_delta": -55, "comfort_delta": -35})}
               if variant == "reconsider" else None)
    return ApartmentExpanded(*make_pair(variant)).run(
        turn_cap=turn_cap, private_stimuli=stimuli,
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable model-free social GOAP and bargaining")
    parser.add_argument("--variant", choices=("mutual", "cautious", "instrumental", "mismatch", "obligation", "work_trade", "reconsider"), default="mutual")
    parser.add_argument("--turn-cap", type=int, default=64)
    args = parser.parse_args()
    print(json.dumps(run_offline(variant=args.variant, turn_cap=args.turn_cap), indent=2))
