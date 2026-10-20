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
    return tuple(
        SeededMemory(f"g8.{role}.{i}", text, subject,
                     "interpretation" if i == 3 else "recollection",
                     70 if i == 3 else 88, 82)
        for i, (subject, text) in enumerate(SEED_TEXT[role], 1)
    )

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
            "operation": operation, "target": target}

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
            self.locations = d["locations"]
            self.seen = set(d["seen"])
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
            self.locations = {r: "mess" for r in ROSTER}
            self.seen = set()
            for role in ROSTER:
                name, duty, goal = ROLES[role]
                self.brains[role] = CrewAgent(
                    CrewIdentity(f"ox.g8.{role}", "", name, duty, goal),
                    MockModel(), initial_memories=seeds_for(role),
                )
                self.private[role] = {
                    "affection": dict(zip(ROSTER, AFFECTION[role])),
                    "trust": dict(zip(ROSTER, TRUST[role])),
                    "last": {}, "disclosed": [],
                }

    def bind(self, ids):
        """Existing checkpoints are tied to the same authenticated body."""
        for role in ROSTER:
            brain = self.brains[role]
            if brain.identity.character_id == "":
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
            "trace": self.trace, "locations": self.locations,
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
            await c.expect_text(
                "CARGO RESTRAINT GRID" if kind == "cargo"
                else "ATMOSPHERE SCRUBBER A-01", timeout=15)
        elif op == "return":
            await move(c, (("port" if kind == "cargo" else "starboard",
                            "Connecting Passage"), ("mess", "Crew Mess")))
            self.locations[role] = "mess"
        else:
            proof = await work_action(c, op, kind)
            fault["receipts"].append(proof)
        fault["stage"] += 1
        fault["completed"] = fault["stage"] == len(steps)
        self.record(role, "work_" + op, fault=fault["name"], proof=proof)
        return True

    def pending_for(self, role):
        return [(key, entry) for key, entry in self.agreements.items()
                if entry["state"] == "pending" and entry["recipient"] == role]

    def candidate(self, role):
        mind = self.private[role]
        rng = random.Random(self.seed + self.turn * 7919 + ROSTER.index(role))
        options = []
        for other in ROSTER:
            if other == role or self.locations[other] != self.locations[role]:
                continue
            prior = mind["last"].get(other, -60)
            affection = mind["affection"][other]
            trust = mind["trust"][other]
            memory = sum(1 for subject, _ in SEED_TEXT[role] if subject == other)
            value = (affection * .25 + (100-trust) * .11 +
                     min(30, (self.turn-prior) * .22) + memory * 12 +
                     rng.uniform(0, 28))
            options.append((value, other))
        return max(options)[1] if options else None

    def current_offer(self, role, other):
        return next(((key, entry) for key, entry in reversed(list(self.agreements.items()))
                     if {role, other} == {entry["proposer"], entry["recipient"]}
                     and entry["state"] in ("pending", "accepted")), (None, None))

    async def speak(self, clients, ids, role, other, line, intent):
        visible = await spoken(clients, self.locations, role, line)
        for observer in visible:
            if observer == role:
                continue
            self.brains[observer].observe(WorldObservation(
                f"g8-speech-{self.turn}-{role}", ids[observer], float(self.turn),
                f"{ROLES[role][0]} said: {line}", kind="heard_speech",
            ))
        if intent == "reassure":
            self.private[other]["trust"][role] = min(
                100, self.private[other]["trust"][role] + 2)
        if intent == "confront":
            self.private[other]["trust"][role] = max(
                0, self.private[other]["trust"][role] - 3)
        self.record(role, "spoken_" + intent, target=other, heard_by=visible)

    async def social(self, role, clients, ids):
        pending = self.pending_for(role)
        if pending:
            key, agreement = pending[0]
            other = agreement["proposer"]
            m = self.private[role]
            rng = random.Random(self.seed + self.turn * 29)
            score = m["affection"][other] + m["trust"][other] * .25 + rng.randint(-25, 20)
            answer = "accept" if score >= 88 else ("defer" if score >= 71 else "decline")
            receipt, heard = await social_action(
                clients, ids, role, other, "social_reply",
                {"agreement_id": key, "revision": agreement["revision"],
                 "answer": answer})
            agreement["state"] = {"accept": "accepted", "defer": "deferred",
                                  "decline": "declined"}[answer]
            self.record(role, "relationship_" + answer, target=other,
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
        score = mind["affection"][other]
        trust = mind["trust"][other]
        key, agreement = self.current_offer(role, other)
        # The acceptance record belongs to Evennia. The handler may ask to
        # withdraw but cannot edit a durable agreement locally.
        if agreement and agreement["state"] == "accepted" and trust < 48 and rng.random() < .12:
            receipt, heard = await social_action(
                clients, ids, role, other, "social_withdraw",
                {"agreement_id": key, "revision": agreement["revision"]})
            agreement["state"] = "withdrawn"
            self.record(role, "relationship_withdrawn", target=other,
                        agreement=key, receipt=receipt["request_id"],
                        listener_event=heard["event_id"])
            return
        earlier = [k for k, v in self.agreements.items()
                   if {role, other} == {v["proposer"], v["recipient"]}]
        if (not agreement and score > 69 and trust > 48
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
            self.record(role, "relationship_proposed", target=other,
                        agreement=key, receipt=receipt["request_id"],
                        listener_event=heard["event_id"])
            return
        r = rng.random()
        if r < .13 and trust < 72:
            intent = "confront"
        elif r < .33:
            intent = "question"
        elif r < .46:
            intent = "reassure"
        elif r < .59:
            intent = "disclose"
        elif r < .66 and score < 48:
            intent = "boundary"
        elif r < .91:
            intent = "connect"
        else:
            intent = "reflect"
        goal = GOALS[intent]
        plan = GOAP.plan({"together", "conversation_open", "heard_uncertainty"}, {goal})
        if not plan.actions:
            raise AssertionError("Social goal has no GOAP operator")
        selected = plan.actions[0].name
        if intent == "disclose":
            remembered = [(subject, text) for subject, text in SEED_TEXT[role]
                          if subject == other and text not in mind["disclosed"]]
            if remembered:
                line = "I remember this differently: " + remembered[0][1][:145]
                mind["disclosed"].append(remembered[0][1])
            else:
                line = "I have some things I have not quite worked through."
        elif intent == "confront":
            line = "I feel we have not been entirely honest about the past."
            mind["trust"][other] = max(0, trust - 1)
        else:
            line = next((op.line for op in SOCIAL_OPERATORS if op.name == selected),
                        "We should talk.")
        await self.speak(clients, ids, role, other, line, intent)

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
                  "agreements": self.agreements, "trace": self.trace}
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
