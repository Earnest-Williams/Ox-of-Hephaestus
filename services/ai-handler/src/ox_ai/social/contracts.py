"""World-facing, reusable negotiation protocol, independent of relationship goals.

The contract board records public proposals, replies, revision histories, and
revocations. Neither private motives nor goal selection are stored here. A
proposal is NOT agreement; an agreement is NOT desire, affection, fulfilment,
or consent to a different activity. World adapters must authorize their own
physical work and consult the current agreement where appropriate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


# Non-explicit relationship and general-purpose cooperation/trading terms.
ACTIVITIES = frozenset({
    "another_date", "stay_longer", "stay_overnight", "sit_together",
    "move_closer", "hold_hands", "cuddle", "hug", "kiss", "private_intimacy",
    "quiet_company", "walk_together", "talk_privately", "share_secret",
    "provide_information", "offer_introduction", "practical_help",
    "shift_swap", "lend_equipment", "share_supplies", "assist_task",
    "joint_investigation", "protect_reputation", "keep_confidence",
    "share_meal", "exchange_contact", "emotional_support", "lend_money",
    "give_transport", "provide_shelter", "exchange_funds", "contract_work",
    "public_endorsement", "share_credit", "meet_friends", "future_commitment",
})
CONSIDERATIONS = frozenset({
    "none", "extra_time", "help", "information", "future_favor",
    "confidentiality", "shared_risk", "resource", "introduction",
    "payment", "shelter", "transport", "protection", "public_credit",
})
SCOPES = frozenset({"one_time", "tonight", "later", "limited", "ongoing"})
ORDERS = frozenset({"before", "after", "simultaneous"})
PHYSICAL = frozenset({
    "sit_together", "move_closer", "hold_hands", "hug", "cuddle", "kiss",
    "private_intimacy", "walk_together",
})


@dataclass(frozen=True, slots=True)
class Terms:
    activity: str
    consideration: str = "none"
    scope: str = "one_time"
    exchange_order: str = "after"

    def __post_init__(self) -> None:
        if self.activity not in ACTIVITIES:
            raise ValueError("Unsupported negotiated activity")
        if self.consideration not in CONSIDERATIONS:
            raise ValueError("Unsupported negotiation consideration")
        if self.scope not in SCOPES:
            raise ValueError("Unsupported negotiation scope")
        if self.exchange_order not in ORDERS:
            raise ValueError("Unsupported exchange sequence")
        if self.consideration == "none" and self.exchange_order != "after":
            raise ValueError("No consideration exists to deliver before the action")


@dataclass(frozen=True, slots=True)
class Offer:
    offer_id: str
    revision: int
    proposer: str
    recipient: str
    initiator: str
    terms: Terms
    state: Literal["pending", "accepted", "declined", "deferred", "withdrawn", "expired"]
    opened_at: int
    expires_at: int
    accepted_by: tuple[str, str] = ()
    performed_by: str | None = None
    consideration_delivered_by: str | None = None


@dataclass(frozen=True, slots=True)
class NegotiationEvent:
    event_id: str
    kind: str
    actor: str
    offer_id: str
    revision: int
    terms: Terms


class ContractBoard:
    """Typed public contract state; versioned and monotonic, never silent overwrite.

    Caller supplies actual world turn. Expiry protects against stale promises.
    In production, an authoritative persisted game-side implementation would
    own this state; the offline test uses this implementation as its fake world.
    """

    def __init__(self, *, ttl: int = 10):
        if not 2 <= ttl <= 100:
            raise ValueError("Offer TTL must be bounded")
        self.ttl = ttl
        self.turn = 0
        self._counter = 0
        self._event_counter = 0
        self.offers: dict[str, Offer] = {}
        self.history: list[NegotiationEvent] = []
        self.receipts: dict[str, tuple[str, str, str, NegotiationEvent]] = {}

    def _event(self, kind: str, actor: str, offer: Offer) -> NegotiationEvent:
        self._event_counter += 1
        event = NegotiationEvent(
            f"social-{self._event_counter:05d}", kind, actor,
            offer.offer_id, offer.revision, offer.terms,
        )
        self.history.append(event)
        return event

    def _get(self, actor: str, offer_id: str, revision: int) -> Offer:
        offer = self.offers.get(offer_id)
        if offer is None:
            raise ValueError("Unknown offer")
        if revision != offer.revision:
            raise ValueError("Stale offer revision")
        if actor not in (offer.proposer, offer.recipient):
            raise PermissionError("Actor is not a party to this offer")
        if self.turn > offer.expires_at and offer.state == "pending":
            offer = replace(offer, state="expired")
            self.offers[offer_id] = offer
            self._event("expired", actor, offer)
        return offer

    def propose(self, actor: str, recipient: str, terms: Terms) -> NegotiationEvent:
        if not actor or not recipient or actor == recipient:
            raise ValueError("Proposal needs two distinct named parties")
        if not isinstance(terms, Terms):
            raise TypeError("Typed Terms required")
        if any(
            o.state == "pending" and {o.proposer, o.recipient} == {actor, recipient}
            for o in self.offers.values()
        ):
            raise ValueError("Only one unresolved proposal per pair")
        self._counter += 1
        offer = Offer(
            f"offer-{self._counter:04d}", 1, actor, recipient, actor, terms,
            "pending", self.turn, self.turn + self.ttl,
        )
        self.offers[offer.offer_id] = offer
        return self._event("proposed", actor, offer)

    def reply(
        self, actor: str, offer_id: str, revision: int,
        answer: Literal["accept", "decline", "defer", "counter"],
        *, counter: Terms | None = None,
    ) -> NegotiationEvent:
        offer = self._get(actor, offer_id, revision)
        if offer.state != "pending":
            raise ValueError("Offer is no longer pending")
        if actor != offer.recipient:
            raise PermissionError("Only addressee may answer an offer")
        if answer == "counter":
            if counter is None or counter == offer.terms:
                raise ValueError("Counteroffer must contain changed typed terms")
            # Both parties must explicitly accept the SAME version: no
            # original proposal persists as an automatic acceptance.
            offer = replace(
                offer, revision=revision + 1, proposer=actor,
                recipient=offer.proposer, terms=counter,
                opened_at=self.turn, expires_at=self.turn + self.ttl,
            )
            kind = "countered"
        elif answer == "accept":
            if counter is not None:
                raise ValueError("An acceptance cannot silently change terms")
            offer = replace(
                offer, state="accepted",
                accepted_by=(offer.proposer, actor),
            )
            kind = "accepted"
        elif answer in ("decline", "defer"):
            if counter is not None:
                raise ValueError("Decline/defer cannot silently substitute terms")
            offer = replace(offer, state="declined" if answer == "decline" else "deferred")
            kind = answer + "d"
        else:
            raise ValueError("Unknown offer response")
        self.offers[offer_id] = offer
        return self._event(kind, actor, offer)

    def withdraw(self, actor: str, offer_id: str, revision: int) -> NegotiationEvent:
        offer = self._get(actor, offer_id, revision)
        if offer.state not in ("pending", "accepted"):
            raise ValueError("Offer cannot be withdrawn after closure")
        if offer.performed_by is not None:
            raise ValueError("Cannot retroactively undo a performed activity")
        offer = replace(offer, state="withdrawn")
        self.offers[offer_id] = offer
        return self._event("withdrawn", actor, offer)

    def perform(
        self, actor: str, offer_id: str, revision: int,
        activity: str, receipt_id: str, *, parties_colocated: bool,
    ) -> NegotiationEvent:
        offer = self._get(actor, offer_id, revision)
        if not receipt_id or len(receipt_id) > 128:
            raise ValueError("Bounded stable receipt identity required")
        if receipt_id in self.receipts:
            earlier = self.receipts[receipt_id]
            if earlier[:3] != (actor, offer_id, activity):
                raise ValueError("Conflicting action receipt identity")
            return earlier[3]
        if offer.state != "accepted" or activity != offer.terms.activity:
            raise PermissionError("Current exact-version agreement required")
        if (offer.terms.consideration != "none"
                and offer.terms.exchange_order == "before"
                and offer.consideration_delivered_by != offer.initiator):
            raise PermissionError("Promised advance consideration is not verified")
        if len(set(offer.accepted_by)) != 2:
            raise PermissionError("Mutual explicit acceptance is absent")
        if activity in PHYSICAL and not parties_colocated:
            raise PermissionError("Physical activity requires actual co-location")
        if offer.performed_by is not None:
            raise ValueError("Agreement already performed")
        offer = replace(offer, performed_by=actor)
        self.offers[offer_id] = offer
        event = self._event("performed", actor, offer)
        self.receipts[receipt_id] = (actor, offer_id, activity, event)
        return event

    def deliver_consideration(
        self, actor: str, offer_id: str, revision: int,
        receipt_id: str, *, world_verified: bool,
    ) -> NegotiationEvent:
        """Fulfil a separately world-verified concession, never by mere assent."""
        offer = self._get(actor, offer_id, revision)
        if offer.state != "accepted" or offer.terms.consideration == "none":
            raise PermissionError("No accepted, outstanding exchange consideration")
        if actor != offer.initiator:
            raise PermissionError("Only party promising consideration can deliver it")
        if not world_verified:
            raise PermissionError("Claimed delivery is not actual world verification")
        if offer.consideration_delivered_by is not None:
            raise ValueError("Consideration was already delivered")
        if not receipt_id or receipt_id in self.receipts:
            raise ValueError("Consideration receipt must be new and stable")
        offer = replace(offer, consideration_delivered_by=actor)
        self.offers[offer_id] = offer
        event = self._event("consideration_delivered", actor, offer)
        self.receipts[receipt_id] = (actor, offer_id, offer.terms.consideration, event)
        return event
