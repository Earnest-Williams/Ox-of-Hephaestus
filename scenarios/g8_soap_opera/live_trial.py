"""G8: bounded six-client social/maintenance trial on the authoritative Evennia ship.

Six independently authenticated ordinary characters use private seeded
Concordia memory and shared symbolic GOAP actions. Every public conversation
is actually spoken and heard. Agreements and repairs require world receipts.
A trusted CI operator injects faults BETWEEN process segments, never through
an agent or its proposed actions. No model calls; no sexual scenes.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from collections import Counter
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import secrets

from concordia.testing.mock_model import MockModel
from ox_ai.agents.crew import CrewAgent, CrewIdentity
from ox_ai.agents.live_concordia import ROLES
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.ports.base import WorldObservation
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.social.domain import SOCIAL_OPERATORS

ROSTER = ("lin", "ari", "iona", "mara", "teo", "captain")
USERS = {
    "lin": "OxBotLin", "ari": "OxBotAri", "iona": "OxBotIona",
    "mara": "OxBotMara", "teo": "OxBotTeo", "captain": "OxBotCaptain",
}
SEED_TEXT = {
    "lin": (("ari", "Ari and I are still married, but we avoid talking about it."),
            ("mara", "Mara and I have been privately seeing one another."),
            ("iona", "I think Iona saw Mara and me leave the lounge together.")),
    "ari": (("lin", "Lin is still my spouse; we have never agreed to separate."),
            ("iona", "Iona and I were once partners."),
            ("mara", "I suspect Lin and Mara have become unusually close.")),
    "iona": (("ari", "I ended things with Ari years ago but still care for them."),
             ("lin", "I saw Lin and Mara together late at night."),
             ("captain", "The Captain and I are casually dating, not exclusive.")),
    "mara": (("lin", "Lin said their marriage was effectively over; I believed it."),
             ("teo", "I regard my relationship with Teo as over."),
             ("iona", "Iona warned me not to trust Lin's promises.")),
    "teo": (("mara", "I thought Mara and I were on a break rather than finished."),
            ("lin", "I suspect Lin has feelings for Mara."),
            ("captain", "I may have misread the Captain's kindness as attraction.")),
    "captain": (("iona", "Iona and I have been dating; I want more commitment."),
                ("ari", "I know Iona has history with Ari."),
                ("teo", "Teo once mistook my support for romantic interest.")),
}
# (when, impact on trust, impact on interest), all subjective, not truth.
# Event occurrence is different from when the character learned about it.
SEED_TIMELINE = {
    "lin": ((-900, -11, 8), (-32, 9, 17), (-65, -13, -5)),
    "ari": ((-900, -16, 10), (-610, 8, 9), (-63, -17, -4)),
    "iona": ((-610, 8, 10), (-65, -16, -7), (-92, 8, 11)),
    "mara": ((-32, -8, 17), (-280, -6, -17), (-72, 9, 3)),
    "teo": ((-280, -11, 15), (-70, -11, -6), (-120, -7, 4)),
    "captain": ((-92, 8, 14), (-610, -5, -2), (-120, 2, -6)),
}
# Typed *subjective* claims from individual prehistories. Keys mean a
# proposition is being entertained, never that it is true. Other characters
# can later hear contradictory statements without getting omniscient facts.
# (claim_key, subject_of_claim, stance, correlated_source)
CLAIM_SEEDS = {
    "lin": {
        0: ("lin_ari_separated", "ari", -1, "lin.marriage_account"),
        1: ("lin_mara_involved", "mara", 1, "lin.own_encounters"),
    },
    "ari": {
        0: ("lin_ari_separated", "lin", -1, "ari.marriage_account"),
        2: ("lin_mara_involved", "mara", 1, "ari.suspicion"),
    },
    "iona": {
        1: ("lin_mara_involved", "lin", 1, "iona.lounge_sighting"),
        2: ("iona_captain_exclusive", "captain", -1, "iona.relationship_view"),
    },
    "mara": {
        0: ("lin_ari_separated", "lin", 1, "lin.marriage_account"),
        1: ("mara_teo_finished", "teo", 1, "mara.relationship_view"),
        2: ("lin_is_reliable", "lin", -1, "iona.warning"),
    },
    "teo": {
        0: ("mara_teo_finished", "mara", -1, "teo.relationship_view"),
        1: ("lin_mara_involved", "lin", 1, "teo.suspicion"),
    },
    "captain": {
        0: ("iona_captain_exclusive", "iona", -1, "captain.relationship_view"),
    },
}
# Scenario-specific consequences of believing the listed hypotheses.
# The second coordinate is willingness to *approach*, NOT romantic desire.
CLAIM_FOCUS = {
    "lin_ari_separated": "lin",
    "mara_teo_finished": "mara",
    "lin_mara_involved": "lin",
    "iona_captain_exclusive": "iona",
    "lin_is_reliable": "lin",
}
CLAIM_EFFECTS = {
    "lin_ari_separated": (16, 14),
    "mara_teo_finished": (-6, -12),
    "lin_mara_involved": (-11, -4),
    "iona_captain_exclusive": (0, -12),
    "lin_is_reliable": (20, 4),
    "willing_to_negotiate": (0, 9),
}
CLAIM_DESCRIPTIONS = {
    "lin_ari_separated": "Lin and Ari had separated",
    "mara_teo_finished": "Mara and Teo had broken up",
    "lin_mara_involved": "Lin and Mara were involved",
    "iona_captain_exclusive": "Iona and the Captain were exclusive",
    "lin_is_reliable": "Lin could be relied upon",
    "willing_to_negotiate": "a proposal would be welcomed",
}
AFFECTION = {
    "lin": (65, 80, 32, 84, 20, 40),
    "ari": (76, 50, 73, 15, 45, 45),
    "iona": (30, 80, 50, 62, 45, 55),
    "mara": (83, 24, 68, 50, 20, 46),
    "teo": (12, 48, 45, 79, 50, 45),
    "captain": (48, 44, 84, 50, 48, 50),
}
TRUST = {
    "lin": (50, 69, 45, 62, 35, 60),
    "ari": (57, 50, 73, 39, 74, 68),
    "iona": (38, 79, 50, 68, 70, 60),
    "mara": (60, 48, 74, 50, 53, 60),
    "teo": (35, 70, 65, 44, 50, 68),
    "captain": (55, 65, 58, 59, 71, 50),
}
SCHEDULE = (("cargo", 35), ("scrubber", 138), ("cargo", 256),
            ("scrubber", 367), ("cargo", 444))
WORK = {
    "cargo": ("travel", "inspect", "restow", "inspect_again", "certify", "return"),
    "scrubber": ("travel", "inspect", "isolate", "replace",
                 "inspect_again", "restart", "return"),
}
ROOM = {"cargo": "Cargo Hold", "scrubber": "Environmental Plant"}
GOAP = GoapPlanner(tuple(a.goap() for a in SOCIAL_OPERATORS))
GOALS = {
    "connect": "interest_expressed",
    "question": "question_asked",
    "confront": "uncertainty_expressed",
    "reassure": "reassured",
    "boundary": "boundary_stated",
    "disclose": "motive_shared",
    "reflect": "topic_changed",
}

def seeds_for(role):
    result = []
    for i, (subject, text) in enumerate(SEED_TEXT[role]):
        event_time, trust_bias, interest_bias = SEED_TIMELINE[role][i]
        claim = CLAIM_SEEDS[role].get(i)
        result.append(SeededMemory(
            f"g8.{role}.{i + 1}", text, subject,
            "interpretation" if i == 2 else "recollection",
            70 if i == 2 else 88, 82,
            occurred_turn=event_time, learned_turn=0,
            trust_effect=trust_bias, interest_effect=interest_bias,
            claim_key=claim[0] if claim else None,
            claim_subject=CLAIM_FOCUS.get(claim[0], claim[1]) if claim else None,
            claim_stance=claim[2] if claim else 0,
            source_group=claim[3] if claim else None,
            claim_credibility=78 if claim else 70,
        ))
    return tuple(result)

def token(value):
    return base64.urlsafe_b64encode(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")

def packet_data(packet):
    if packet.args and isinstance(packet.args[0], dict):
        return packet.args[0]
    if isinstance(packet.options, dict):
        return packet.options
    return {}

async def match(client, kind, predicate=lambda d: True):
    async with asyncio.timeout(20):
        p = await client.receive_matching(
            lambda v: v.kind == kind and predicate(packet_data(v)),
            frame_budget=512,
        )
    return packet_data(p)

async def spoken(clients, locations, speaker, line):
    if any(c in line for c in "\r\n\x00") or len(line) > 190:
        raise ValueError("Bounded single-line dialogue required")
    visible = [r for r in ROSTER if locations[r] == locations[speaker]]
    await clients[speaker].send_line("say " + line)
    for role in visible:
        text = await clients[role].expect_text(line, timeout=15)
        if line not in text:
            raise AssertionError("One character did not hear confirmed speech")
    return visible

async def move(client, directions):
    for direction, expected in directions:
        await client.send_line(direction)
        await client.expect_text(expected, timeout=15)

async def work_action(client, operation, target):
    request = secrets.token_hex(16)
    await client.send_line(f"oxwork {request} {operation} {target}")
    data = await match(client, "ox_receipt",
                       lambda d: d.get("request_id") == request)
    if data.get("actor_dbref") != client.character_dbref:
        raise PermissionError("World returned a different actor's receipt")
    if data.get("status") != "succeeded" or not data.get("source_event_id"):
        raise AssertionError("World work denied: " + repr(data))
    return {"request_id": request, "source_event_id": data["source_event_id"],
            "operation": operation, "target": target, "state": data.get("state")}

async def social_action(clients, ids, role, other, operation, payload):
    request = secrets.token_hex(16)
    await clients[role].send_line(
        f"oxwork {request} {operation} social {token(payload)}")
    receipt = await match(clients[role], "ox_receipt",
                          lambda d: d.get("request_id") == request)
    if (receipt.get("actor_dbref") != ids[role]
            or receipt.get("status") != "succeeded"
            or not receipt.get("source_event_id")):
        raise AssertionError("Unverified social change: " + repr(receipt))
    heard = await match(
        clients[other], "ox_event",
        lambda d: d.get("kind") == "social_" + receipt.get("event_kind", "")
        and d.get("datum_history_id") == receipt.get("history_id")
        and d.get("sender_dbref") == ids[role],
    )
    if heard.get("datum_agreement_id") != receipt.get("agreement_id"):
        raise AssertionError("Recipient did not receive exact agreement")
    return receipt, heard

class Trial:
    def __init__(self, seed, root):
        self.seed = seed
        self.root = root
        self.file = root / "state.json"
        self.brains = {}
        if self.file.exists():
            d = json.loads(self.file.read_text())
            if d["seed"] != seed:
                raise ValueError("Changed seed during a 500-turn run")
            self.turn = d["turn"]
            self.private = d["private"]
            self.agreements = d["agreements"]
            self.faults = d["faults"]
            self.trace = d["trace"]
            self.reinterpretations = d.get("reinterpretations", [])
            self.locations = d["locations"]
            self.seen = {tuple(item) for item in d["seen"]}
            for role in ROSTER:
                self.brains[role] = CrewAgent.from_checkpoint(
                    root / f"{role}.brain.json", MockModel())
        else:
            self.turn = 0
            self.private = {}
            self.agreements = {}
            self.faults = [
                {"name": f"g8-{i}", "kind": kind, "at": at,
                 "seen": False, "stage": 0, "receipts": [], "completed": False}
                for i, (kind, at) in enumerate(SCHEDULE)
            ]
            self.trace = []
            self.reinterpretations = []
            self.locations = {r: "mess" for r in ROSTER}
            self.seen = set()
            for role in ROSTER:
                name, duty, goal = ROLES[role]
                self.brains[role] = None  # Bind new brains only after authenticated IDs.
                self.private[role] = {
                    "affection": dict(zip(ROSTER, AFFECTION[role])),
                    "trust": dict(zip(ROSTER, TRUST[role])),
                    "last": {}, "disclosed": [],
                }

    def bind(self, ids):
        """Existing checkpoints are tied to the same authenticated body."""
        for role in ROSTER:
            brain = self.brains[role]
            if brain is None:
                name, duty, goal = ROLES[role]
                self.brains[role] = CrewAgent(
                    CrewIdentity(f"ox.g8.{role}", ids[role], name, duty, goal),
                    MockModel(), initial_memories=seeds_for(role),
                )
            elif brain.identity.character_id != ids[role]:
                raise PermissionError("Restored brain cannot puppet another body")

    def record(self, role, kind, **extra):
        self.trace.append({"turn": self.turn, "actor": role, "kind": kind, **extra})

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for role in ROSTER:
            self.brains[role].save_checkpoint(self.root / f"{role}.brain.json")
        state = {
            "seed": self.seed, "turn": self.turn, "private": self.private,
            "agreements": self.agreements, "faults": self.faults,
            "trace": self.trace, "reinterpretations": self.reinterpretations,
            "locations": self.locations,
            "seen": sorted(self.seen),
        }
        staging = self.file.with_suffix(".tmp")
        staging.write_text(json.dumps(state, indent=2), encoding="utf-8")
        staging.replace(self.file)

    def owner_fault(self, role):
        kind = {"mara": "cargo", "teo": "scrubber"}.get(role)
        return next((f for f in self.faults
                     if f["kind"] == kind and f["seen"] and not f["completed"]), None)

    async def read_inbox(self, clients, ids):
        for role in ROSTER:
            c = clients[role]
            await c.send_line("oxinbox 0")
            count = 0
            while True:
                count += 1
                if count > 1000:
                    raise RuntimeError("World inbox did not terminate")
                p = await asyncio.wait_for(c.receive(), 16)
                if p.kind == "ox_inbox_done":
                    break
                if p.kind != "ox_event":
                    continue
                data = packet_data(p)
                eid = data.get("event_id")
                if not isinstance(eid, str) or not eid:
                    raise AssertionError("World event missing identity")
                if data.get("recipient_dbref") != ids[role]:
                    raise PermissionError("Cross-character world event leakage")
                if (role, eid) in self.seen:
                    continue
                self.seen.add((role, eid))
                self.brains[role].observe(WorldObservation(
                    eid, ids[role], float(data.get("game_time", 0.0)),
                    str(data.get("text", "")), eid,
                ))
                expected = {"cargo_shift": ("mara", "cargo"),
                            "atmosphere_alarm": ("teo", "scrubber")}.get(data.get("kind"))
                if expected and expected[0] == role:
                    old = next((f for f in self.faults if f["seen"] and not f["completed"]
                                and f["kind"] == expected[1]), None)
                    if old is None:
                        new = next((f for f in self.faults if f["kind"] == expected[1]
                                    and not f["seen"] and f["at"] <= self.turn + 1), None)
                        if new:
                            new["seen"] = True

    async def do_work(self, role, clients):
        fault = self.owner_fault(role)
        if fault is None:
            return False
        steps = WORK[fault["kind"]]
        stage = fault["stage"]
        if stage >= len(steps):
            raise AssertionError("Unfinished fault exhausted action plan")
        facts = {"observed"} | set(steps[:stage])
        # Validate a real GOAP path, then attempt ONE step; effects enter
        # planning belief state only after an authenticated world response.
        operations = [
            GoapAction(name, frozenset({"observed"} if i == 0 else {steps[i-1]}),
                       frozenset({name}), verb=name)
            for i, name in enumerate(steps)
        ]
        plan = GoapPlanner(operations).plan(facts, {steps[-1]})
        if not plan.actions or plan.actions[0].name != steps[stage]:
            raise AssertionError("GOAP procedure diverged from acknowledged steps")
        op = steps[stage]
        c = clients[role]
        kind = fault["kind"]
        proof = None
        if op == "travel":
            if self.locations[role] != "mess":
                raise AssertionError("Expected worker at crew mess")
            await move(c, (("out", "Connecting Passage"),
                           ("starboard" if kind == "cargo" else "port", ROOM[kind])))
            self.locations[role] = kind
        elif op in ("inspect", "inspect_again"):
            await c.send_line("inspect " + kind)
            output = await c.expect_text(
                "CARGO RESTRAINT GRID" if kind == "cargo"
                else "ATMOSPHERE SCRUBBER A-01", timeout=15)
            state = ({"cargo": ("UNSECURED", "RESTOWED"),
                      "scrubber": ("SATURATED", "SERVICED")}[kind]
                     [0 if op == "inspect" else 1])
            if state not in output:
                raise AssertionError("World inspection disagrees with GOAP: "
                                     + repr((kind, op, output)))
        elif op == "return":
            await move(c, (("port" if kind == "cargo" else "starboard",
                            "Connecting Passage"), ("mess", "Crew Mess")))
            self.locations[role] = "mess"
        else:
            proof = await work_action(c, op, kind)
            expected_end = {"certify": "secured", "restart": "nominal"}.get(op)
            if expected_end and proof["state"] != expected_end:
                raise AssertionError("World receipt reports incorrect final state")
            fault["receipts"].append(proof)
        fault["stage"] += 1
        fault["completed"] = fault["stage"] == len(steps)
        self.record(role, "work_" + op, fault=fault["name"], proof=proof)
        return True

    def pending_for(self, role):
        return [(key, entry) for key, entry in self.agreements.items()
                if entry["state"] == "pending" and entry["recipient"] == role]

    def interpreted_influence(self, role, other):
        """One character's opinion about another; never share the ledger."""
        trust_delta = 0
        approach_delta = 0
        doubt = False
        views = []
        for view in self.brains[role].interpretations.for_subject(other):
            influence = CLAIM_EFFECTS.get(view.claim_key)
            if influence is None:
                continue
            confidence = (view.confidence - 50) / 50
            trust_delta += round(influence[0] * confidence)
            approach_delta += round(influence[1] * confidence)
            doubt |= view.contradictory or view.view == "unsettled"
            views.append({
                "claim": view.claim_key, "confidence": view.confidence,
                "view": view.view, "contradictory": view.contradictory,
                "sources": view.evidence_ids,
            })
        return (
            max(-25, min(25, trust_delta)),
            max(-20, min(20, approach_delta)),
            doubt, tuple(views),
        )

    def perspective(self, role, other, *, rehearse=False):
        bank = self.brains[role].temporal_memories
        trust_bias, interest_bias, sources = bank.appraisal(other, self.turn)
        belief_trust, _approach, _doubt, _views = self.interpreted_influence(
            role, other)
        if rehearse:
            # This person consciously recalls at most three episodes;
            # rehearsal changes future accessibility, never the historical date.
            self.brains[role].rehearse_memories(other, self.turn, limit=3)
        mind = self.private[role]
        return (
            max(0, min(100, mind["trust"][other] + trust_bias + belief_trust)),
            max(0, min(100, mind["affection"][other] + interest_bias)),
            sources,
        )

    def candidate(self, role):
        mind = self.private[role]
        rng = random.Random(self.seed + self.turn * 7919 + ROSTER.index(role))
        options = []
        for other in ROSTER:
            if other == role or self.locations[other] != self.locations[role]:
                continue
            prior = mind["last"].get(other, -60)
            trust, affection, sources = self.perspective(role, other)
            recalled = self.brains[role].temporal_memories.retrieve(
                other, self.turn, limit=2)
            relevance = sum(entry.importance(self.turn) for entry in recalled)
            _belief_trust, approach, doubt, _views = self.interpreted_influence(
                role, other)
            # Doubt may provoke a conversation even when attraction is low.
            # It does not automatically grant intimacy or actual permission.
            value = (affection * .34 + (100-trust) * .14 + approach * .75
                     + (7 if doubt else 0)
                     + min(30, (self.turn-prior) * .22)
                     + relevance * 18 + rng.uniform(0, 26))
            options.append((value, other))
        return max(options)[1] if options else None

    def remember_episode(self, observer, episode):
        """Append only an actor-heard event; audit revisions separately.

        The experiment's aggregate trace can inspect many minds; agents never
        read each other's private interpretations when planning their moves.
        """
        brain = self.brains[observer]
        if not brain.remember_timed(episode) or episode.claim_key is None:
            return
        view = brain.interpretations.get(
            episode.claim_subject or episode.subject, episode.claim_key)
        if view is None or not view.revisions:
            return
        last = view.revisions[-1]
        if last.evidence_id != episode.memory_id:
            return
        self.reinterpretations.append({
            "turn": self.turn, "actor": observer,
            "subject": view.subject, "claim": view.claim_key,
            "before": last.previous_confidence, "after": last.new_confidence,
            "old_view": last.previous_view, "new_view": last.new_view,
            "reason": last.reason, "opposing_sources": last.opposing_sources,
            "memory_id": last.evidence_id, "source_id": episode.source_event_id,
        })

    def remember_contract(self, role, other, receipt, kind):
        # Only a successful world operation + witnessed counterpart delivery
        # reaches this method. Neither agent gets to manufacture assent.
        effects = {
            "proposed": (3, 0), "accepted": (13, 0),
            "deferred": (-4, -3), "declined": (-13, -9),
            "withdrawn": (-18, -12),
        }
        trust_bias, interest_bias = effects[kind]
        event_id = str(receipt["source_event_id"])
        for observer, subject in ((role, other), (other, role)):
            # Only the counterpart can infer something about the ACTOR's
            # willingness to negotiate. Neither actor infers romantic desire.
            typed = observer == other and kind in (
                "proposed", "accepted", "declined", "withdrawn")
            self.remember_episode(observer, TemporalMemory(
                memory_id=f"g8.world.{receipt['request_id']}.{observer}",
                source_event_id=event_id, subject=subject,
                text=f"{ROLES[role][0]} {kind} a commitment involving {ROLES[other][0]}.",
                kind="world_receipt", occurred_turn=self.turn,
                learned_turn=self.turn, confidence=100, salience=88,
                trust_effect=trust_bias, interest_effect=interest_bias,
                claim_key="willing_to_negotiate" if typed else None,
                claim_subject=role if typed else None,
                claim_stance=(1 if kind in ("proposed", "accepted") else -1)
                             if typed else 0,
                source_group=f"world.negotiation.{role}.{other}" if typed else None,
                claim_credibility=100,
            ))

    def current_offer(self, role, other):
        return next(((key, entry) for key, entry in reversed(list(self.agreements.items()))
                     if {role, other} == {entry["proposer"], entry["recipient"]}
                     and entry["state"] in ("pending", "accepted")), (None, None))

    async def speak(self, clients, ids, role, other, line, intent, *,
                    statement=None):
        visible = await spoken(clients, self.locations, role, line)
        attitude = {
            "reassure": (7, 2), "confront": (-10, -5),
            "connect": (2, 4), "boundary": (-7, -4),
            "question": (1, 0), "disclose": (2, 1), "reflect": (0, 0),
        }
        for observer in visible:
            if observer == role:
                continue
            msg_id = f"g8-speech-{self.turn}-{role}"
            self.brains[observer].observe(WorldObservation(
                msg_id, ids[observer], float(self.turn),
                f"{ROLES[role][0]} said: {line}", kind="heard_speech",
            ))
            trust_bias, interest_bias = (attitude[intent] if observer == other
                                         else (0, 0))
            # A real observer knows the speaker SAID the words. The optional
            # assertion inside those words is evaluated as defeasible
            # testimony, with the observer's own credibility assessment.
            attributed = statement is not None and statement.claim_key is not None
            credibility = min(
                statement.claim_credibility if attributed else 70,
                max(10, self.perspective(observer, role)[0]),
            )
            self.remember_episode(observer, TemporalMemory(
                memory_id=f"g8.speech.{self.turn}.{role}.{observer}",
                subject=role, text=f"{ROLES[role][0]} said: {line}",
                source_event_id=msg_id, kind="witnessed_speech",
                occurred_turn=self.turn, learned_turn=self.turn,
                confidence=100, salience=78 if attributed else (
                    52 if observer == other else 30),
                trust_effect=trust_bias, interest_effect=interest_bias,
                claim_key=statement.claim_key if attributed else None,
                claim_subject=statement.claim_subject if attributed else None,
                claim_stance=statement.claim_stance if attributed else 0,
                source_group=(statement.source_group or
                              f"speech.{role}.{statement.claim_key}")
                             if attributed else None,
                claim_credibility=credibility,
            ))
        self.record(role, "spoken_" + intent, target=other, heard_by=visible)

    async def social(self, role, clients, ids):
        pending = self.pending_for(role)
        if pending:
            key, agreement = pending[0]
            other = agreement["proposer"]
            m = self.private[role]
            rng = random.Random(self.seed + self.turn * 29)
            trust, affection, sources = self.perspective(role, other, rehearse=True)
            _belief_trust, approach, _doubt, _views = self.interpreted_influence(
                role, other)
            score = affection + trust * .25 + approach * .4 + rng.randint(-25, 20)
            answer = "accept" if score >= 88 else ("defer" if score >= 71 else "decline")
            receipt, heard = await social_action(
                clients, ids, role, other, "social_reply",
                {"agreement_id": key, "revision": agreement["revision"],
                 "answer": answer})
            agreement["state"] = {"accept": "accepted", "defer": "deferred",
                                  "decline": "declined"}[answer]
            self.remember_contract(role, other, receipt, agreement["state"])
            self.record(role, "relationship_" + answer, target=other,
                        remembered=sources, appraisal=(trust, affection),
                        agreement=key, receipt=receipt["request_id"],
                        listener_event=heard["event_id"])
            return
        other = self.candidate(role)
        if other is None:
            self.record(role, "private_reflection")
            return
        mind = self.private[role]
        mind["last"][other] = self.turn
        rng = random.Random(self.seed + self.turn * 127 + ROSTER.index(role))
        trust, score, sources = self.perspective(role, other, rehearse=True)
        _belief_trust, approach, uncertain, active_views = (
            self.interpreted_influence(role, other))
        key, agreement = self.current_offer(role, other)
        # The acceptance record belongs to Evennia. The handler may ask to
        # withdraw but cannot edit a durable agreement locally.
        if agreement and agreement["state"] == "accepted" and trust < 48 and rng.random() < .12:
            receipt, heard = await social_action(
                clients, ids, role, other, "social_withdraw",
                {"agreement_id": key, "revision": agreement["revision"]})
            agreement["state"] = "withdrawn"
            self.remember_contract(role, other, receipt, "withdrawn")
            self.record(role, "relationship_withdrawn", target=other,
                        remembered=sources, appraisal=(trust, score),
                        agreement=key, receipt=receipt["request_id"],
                        listener_event=heard["event_id"])
            return
        earlier = [k for k, v in self.agreements.items()
                   if {role, other} == {v["proposer"], v["recipient"]}]
        if (not agreement and score > 69 and score + approach > 70 and trust > 48
                and (not earlier or self.turn - self.agreements[earlier[-1]]["turn"] > 100)
                and rng.random() < .19):
            receipt, heard = await social_action(clients, ids, role, other, "social_propose", {
                "recipient": ids[other],
                "terms": {"activity": "future_commitment", "consideration": "none",
                          "scope": "ongoing", "exchange_order": "after"},
            })
            key = receipt["agreement_id"]
            self.agreements[key] = {
                "proposer": role, "recipient": other, "state": "pending",
                "revision": receipt["revision"], "turn": self.turn,
            }
            self.remember_contract(role, other, receipt, "proposed")
            self.record(role, "relationship_proposed", target=other,
                        remembered=sources, appraisal=(trust, score),
                        agreement=key, receipt=receipt["request_id"],
                        listener_event=heard["event_id"])
            return
        # Goal priority responds to recalled, time-weighted experiences.
        # No event dictates an outcome or confers permission for intimacy.
        options = ("confront", "question", "reassure", "disclose",
                   "boundary", "connect", "reflect")
        weights = (
            max(1, 28 - trust * .32) + (8 if uncertain else 0),
            12 + (18 if uncertain else 0),
            max(2, trust * .19),
            (13 if sources else 6) + (6 if uncertain else 0),
            max(1, 35 - score) * .35,
            max(2, score * .31) + max(-5, min(6, approach * .4)),
            8,
        )
        intent = rng.choices(options, weights=weights)[0]
        goal = GOALS[intent]
        plan = GOAP.plan({"together", "conversation_open", "heard_uncertainty"}, {goal})
        if not plan.actions:
            raise AssertionError("Social goal has no GOAP operator")
        selected = plan.actions[0].name
        disclosed_statement = None
        if intent == "disclose":
            # A person may disclose their *own* recollection of a third party,
            # especially in a tangled relationship. Do not peek into the
            # listener's private memories or require a predetermined outcome.
            bank = self.brains[role].temporal_memories
            authored = [bank.get(seed.memory_id) for seed in seeds_for(role)]
            available = [
                entry for entry in authored
                if entry is not None and entry.memory_id not in mind["disclosed"]
            ]
            available.sort(key=lambda entry: (
                -(entry.importance(self.turn)
                  + (.20 if entry.subject == other else 0)
                  + (.12 if entry.claim_subject == other else 0)),
                entry.memory_id,
            ))
            if available:
                disclosed_statement = available[0]
                episode = disclosed_statement
                intro = ("Someone told me: " if episode.kind == "testimony"
                         else "I believe: " if episode.kind == "interpretation"
                         else "I remember: ")
                line = intro + episode.text[:140]
                mind["disclosed"].append(episode.memory_id)
            else:
                line = "I've been reconsidering what I remember about us."
        elif intent in ("confront", "question", "reflect") and uncertain and active_views:
            unsettled = next(
                (view for view in active_views
                 if view["contradictory"] or view["view"] == "unsettled"),
                active_views[0],
            )
            description = CLAIM_DESCRIPTIONS.get(
                unsettled["claim"], "that story")
            if intent == "question":
                line = f"Can we talk about whether {description}?"
            elif intent == "confront":
                line = f"I've heard conflicting accounts about whether {description}."
            else:
                line = f"I'm rethinking what I believe about whether {description}."
        elif intent == "confront":
            old = self.brains[role].temporal_memories.retrieve(
                other, self.turn, limit=1, affective_only=True)
            line = ("That conversation left me thinking about our past."
                    if old else "I feel we have not been entirely honest.")
        else:
            line = next((op.line for op in SOCIAL_OPERATORS if op.name == selected),
                        "We should talk.")
        await self.speak(clients, ids, role, other, line, intent,
                         statement=disclosed_statement)
        # Explain the subjective sources of a decision without declaring
        # those memories accurate or publishing the whole private bank.
        self.trace[-1]["remembered"] = sources
        self.trace[-1]["appraisal"] = [trust, score]
        self.trace[-1]["interpretation_views"] = active_views

    async def run_phase(self, ids, start, end):
        if self.turn != start - 1:
            raise ValueError(f"Discontinuous turn cursor: {self.turn} vs {start}")
        clients = {
            role: EvenniaWebSocketClient(
                "ws://127.0.0.1:4002", USERS[role], os.environ["OX_PROBE_PASSWORD"],
                ids[role], timeout=18)
            for role in ROSTER
        }
        try:
            await asyncio.gather(*(c.open() for c in clients.values()))
            if not all(c.authenticated for c in clients.values()):
                raise PermissionError("Six independent logins were not authenticated")
            for role in ROSTER:
                await clients[role].send_line("look")
                name = {"mess": "Crew Mess", "cargo": ROOM["cargo"],
                        "scrubber": ROOM["scrubber"]}[self.locations[role]]
                await clients[role].expect_text(name)
            await self.read_inbox(clients, ids)
            for turn in range(start, end + 1):
                self.turn = turn
                role = ROSTER[(turn - 1) % 6]
                if not await self.do_work(role, clients):
                    await self.social(role, clients, ids)
            self.save()
        finally:
            await asyncio.gather(*(c.close() for c in clients.values()),
                                 return_exceptions=True)

    def verify(self):
        if self.turn != 500 or len(self.trace) != 500:
            raise AssertionError("All 500 authenticated decisions required")
        for f in self.faults:
            if not f["seen"] or not f["completed"]:
                raise AssertionError("Unrepaired world fault: " + str(f))
            required = sum(x in ("restow", "certify", "isolate", "replace", "restart")
                           for x in WORK[f["kind"]])
            if len(f["receipts"]) != required:
                raise AssertionError("Missing authoritative repair receipt")
        ids = [r["request_id"] for f in self.faults for r in f["receipts"]]
        if len(ids) != len(set(ids)):
            raise AssertionError("Duplicated work requests")
        counts = dict(Counter(t["kind"] for t in self.trace))
        report = {"status": "verified_500_turns", "turns": self.turn,
                  "actors": list(ROSTER), "authenticated_client_sessions": 36,
                  "world": "real_evennia", "model_calls": 0,
                  "faults": self.faults, "counts": counts,
                  "agreements": self.agreements, "trace": self.trace,
                  "reinterpretations": self.reinterpretations,
                  "interpretation_change_count": sum(
                      1 for revision in self.reinterpretations
                      if revision["old_view"] != revision["new_view"]),
                  "interpretation_counts": {
                      role: len(self.brains[role].interpretations.to_records()["states"])
                      for role in ROSTER},
                  "temporal_memory_counts": {role: len(self.brains[role].temporal_memories)
                                             for role in ROSTER}}
        (self.root / "final.json").write_text(json.dumps(report, indent=2))
        return report

def identities():
    base = Path(".ox-state")
    five = json.loads((base / "p4e-ids.json").read_text())
    captain = json.loads((base / "p4f-captain-id.json").read_text())
    ids = {**five, **captain}
    if set(ids) != set(ROSTER) or len(set(ids.values())) != 6:
        raise PermissionError("Six unique persisted world identities required")
    return ids

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    p.add_argument("--seed", type=int, default=241)
    p.add_argument("--root", type=Path, default=Path(".ox-state/g8"))
    args = p.parse_args()
    if os.environ.get("OX_G8_LIVE_CI") != "1":
        raise PermissionError("Disposable six-actor CI fixture only")
    if not (1 <= args.start <= args.end <= 500):
        raise ValueError("Bounded 500-decision trial required")
    trial = Trial(args.seed, args.root)
    ids = identities()
    trial.bind(ids)
    asyncio.run(trial.run_phase(ids, args.start, args.end))
    if args.end == 500:
        summary = trial.verify()
        print(json.dumps({k: v for k, v in summary.items()
                          if k not in ("trace", "agreements")}, indent=2))
        print("OX_G8_REAL_500_TURN_PASS")

if __name__ == "__main__":
    main()
