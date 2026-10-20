"""G7b: actual two-client speech/pose loop, independently planned by GOAP.

The only physical scene affordance here is an observed Evennia POSE. It is
NOT a world-enforced contact/consent ledger. A handler-side typed agreement
check is required before sending that pose, and the two authentic clients
must confirm the actual game output. Information/resource consideration is
tested only in the offline world-owned fake; do not simulate a delivered
world item over speech.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
from html import unescape

from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.scenarios.apartment_extended import ApartmentExpanded, make_pair
from ox_ai.social.contracts import PHYSICAL

ROLES = ("clara", "ben")
NAMES = ("OxSocialClara", "OxSocialBen")
URL = "ws://127.0.0.1:4002"


def _plaintext(value: str) -> str:
    """Discard presentation markup before comparing actual game output."""
    value = unescape(value)
    return re.sub(r"\|[A-Za-z]", "", value)


def _prevalidate_pose(scene: ApartmentExpanded, index: int, choice) -> None:
    if choice.action != "perform_agreement":
        return
    mind = scene.people[index]
    agreement = scene.board.offers.get(choice.offer_id)
    if (agreement is None or agreement.state != "accepted"
            or agreement.revision != choice.revision
            or agreement.terms != choice.terms
            or agreement.terms.activity not in PHYSICAL
            or mind.name not in agreement.accepted_by
            or agreement.performed_by is not None):
        raise PermissionError("Refusing unagreed, stale or duplicate contact pose")
    if (agreement.terms.consideration != "none"
            and agreement.terms.exchange_order == "before"
            and agreement.consideration_delivered_by != agreement.initiator):
        raise PermissionError("Required advance consideration was not fulfilled")


async def run(*, variant: str = "mutual", turn_cap: int = 64) -> dict:
    if os.environ.get("OX_SOCIAL_GOAP_LIVE_CI") != "1":
        raise PermissionError("Requires deliberately disposable two-character world")
    if variant not in ("mutual", "mismatch", "reconsider"):
        raise ValueError("Live test supports only zero-consideration cases")
    if type(turn_cap) is not int or not 1 <= turn_cap <= 100:
        raise ValueError("Finite 1-100 turn cap required")
    identities = json.loads(
        Path(".ox-state/g7-social-ids.json").read_text(encoding="utf-8")
    )
    if set(identities) != set(ROLES) or len(set(identities.values())) != 2:
        raise PermissionError("Two distinct ordinary Evennia actors are required")
    password = os.environ["OX_PROBE_PASSWORD"]
    scene = ApartmentExpanded(*make_pair(variant))
    clients = {
        role: EvenniaWebSocketClient(
            URL, username, password, identities[role], timeout=15,
        )
        for role, username in zip(ROLES, NAMES)
    }
    idle = 0
    try:
        await asyncio.gather(*(client.open() for client in clients.values()))
        if not all(c.authenticated for c in clients.values()):
            raise PermissionError("World did not authenticate both persons")
        for role in ROLES:
            await clients[role].send_line("look")
            await clients[role].expect_text("Clara's Apartment", timeout=15)

        for turn in range(turn_cap):
            index = turn % 2
            role, counterpart = ROLES[index], ROLES[1-index]
            mind = scene.people[index]
            # This is an operator-authored private event, not an instruction
            # to withdraw; GOAP chooses in response to its new own state.
            if variant == "reconsider" and turn == 6:
                mind.private_news(
                    resentment_delta=100, hope_delta=-55, comfort_delta=-35,
                )
            choice = mind.propose()
            if choice is None:
                idle += 1
                if idle >= 2:
                    break
                continue
            idle = 0
            if not choice.line or any(c in choice.line for c in "\r\n\x00"):
                raise ValueError("Proposed action must be one bounded world command")
            if len(choice.line) > 400:
                raise ValueError("Oversize typed social utterance")
            _prevalidate_pose(scene, index, choice)

            # The actual world's ordinary say/pose command executes here.
            # No planned effect is confirmed before BOTH distinct characters
            # have observed the real server's output.
            await clients[role].send_line(choice.verb + " " + choice.line)
            own = _plaintext(await clients[role].expect_text(choice.line, timeout=15))
            other = _plaintext(await clients[counterpart].expect_text(
                choice.line, timeout=15,
            ))
            if choice.verb == "say":
                if "You say," not in own or choice.line not in own:
                    raise AssertionError("No actual speaker speech confirmation")
                if not re.search(r"\b" + re.escape(mind.name) + r"\s+says,", other):
                    raise AssertionError("Listener did not hear the identified speaker")
            elif choice.verb == "pose":
                if (mind.name + " " + choice.line not in own
                        or mind.name + " " + choice.line not in other):
                    raise AssertionError("World did not show the named person's pose")
            else:
                raise AssertionError("GOAP tried an unoffered social game verb")
            scene.step(index, confirmed_choice=choice)
            if (choice.verb == "pose"
                    and scene.board.offers[choice.offer_id].performed_by != mind.name):
                raise AssertionError("A spoken pose did not match the accepted terms")
            if all("ended" in a.beliefs for a in scene.people):
                break

        ended = all("ended" in a.beliefs for a in scene.people)
        result = {
            "status": "complete" if ended else "quiescent" if idle >= 2 else "turn_capped",
            "scope": "G7b_two_authenticated_evennia_clients_live_goap",
            "variant": variant,
            "turns": len(scene.trace),
            "model_calls": 0,
            "planning_calls": {a.name: a.planner_calls for a in scene.people},
            "world_confirmed_speech_or_pose": len(scene.trace),
            "poses": sum(t["action"] == "perform_agreement" for t in scene.trace),
            "offers": [
                {
                    "id": o.offer_id, "activity": o.terms.activity,
                    "revision": o.revision, "state": o.state,
                    "performed_by": o.performed_by, "consideration": o.terms.consideration,
                }
                for o in scene.board.offers.values()
            ],
            "trace": list(scene.trace),
        }
        if result["status"] != "complete":
            raise AssertionError("A finite social GOAP conversation did not conclude")
        if variant == "mutual":
            if result["poses"] < 1:
                raise AssertionError("Mutual variant did not produce agreed physical closeness")
        elif variant in ("mismatch", "reconsider"):
            if result["poses"]:
                raise AssertionError("No physical pose should follow refusal or revoked choice")
        return result
    finally:
        await asyncio.gather(*(c.close() for c in clients.values()),
                             return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="G7b real two-client social GOAP")
    parser.add_argument("--variant", choices=("mutual", "mismatch", "reconsider"),
                        default="mutual")
    parser.add_argument("--turn-cap", type=int, default=64)
    parser.add_argument("--out", type=Path,
                        default=Path(".ox-state/g7b-live.json"))
    args = parser.parse_args()
    result = asyncio.run(run(variant=args.variant, turn_cap=args.turn_cap))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for t in result["trace"]:
        print(f'{t["speaker"]} ({t["action"]}): {t["text"]}')
    print("OX_G7B_LIVE_GOAP_PASS")


if __name__ == "__main__":
    main()
