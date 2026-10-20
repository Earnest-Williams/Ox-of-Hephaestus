"""Two independent GOAP agents converse through REAL Evennia character sessions.

This is a disposable opt-in experiment, never an ambient ship supervisor.
The alternating turn scheduler does NOT select a conversation goal or
utterance. Each participant's own GOAP planner selects an action from private
beliefs. The world executes ordinary 'say'; BOTH authenticated clients must
observe the actual utterance before the agent marks its action completed.
No LLM, synthetic server receipts, shared hidden feelings or predetermined
happy ending. The first trial only tests bounded spoken interaction.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.scenarios.apartment_goap import make_pair

ROLES = ("clara", "ben")
NAMES = ("OxSocialClara", "OxSocialBen")
URL = "ws://127.0.0.1:4002"


async def run(*, variant: str, turn_cap: int) -> dict:
    if os.environ.get("OX_SOCIAL_GOAP_LIVE_CI") != "1":
        raise PermissionError("Real apartment social GOAP requires disposable opt-in")
    if not (1 <= turn_cap <= 100):
        raise ValueError("A finite turn cap is required")
    ids = json.loads(Path(".ox-state/g7-social-ids.json").read_text(encoding="utf-8"))
    if set(ids) != set(ROLES) or len(set(ids.values())) != 2:
        raise PermissionError("Expected two separate authenticated character IDs")
    password = os.environ["OX_PROBE_PASSWORD"]
    controllers = dict(zip(ROLES, make_pair(variant=variant)))
    clients = {
        role: EvenniaWebSocketClient(
            URL, username, password, ids[role], timeout=15,
        )
        for role, username in zip(ROLES, NAMES)
    }
    transcript = []
    try:
        await asyncio.gather(*(client.open() for client in clients.values()))
        if not all(client.authenticated for client in clients.values()):
            raise PermissionError("Both separate identities must be authenticated")
        for role in ROLES:
            await clients[role].send_line("look")
            await clients[role].expect_text("Clara's Apartment", timeout=15)

        for turn in range(turn_cap):
            role = ROLES[turn % 2]
            listener_role = ROLES[1 - turn % 2]
            brain = controllers[role]
            listener = controllers[listener_role]
            proposed = brain.propose()
            if proposed is None:
                if all("said_goodnight" in c.facts for c in controllers.values()):
                    break
                continue
            if any(c in proposed.line for c in "\r\n\x00"):
                raise ValueError("An utterance must fit one ordinary Evennia command")
            await clients[role].send_line("say " + proposed.line)
            # No projected effect is committed until the real server reports
            # that the authenticated speaker spoke AND the listener heard it.
            await clients[role].expect_text(proposed.line, timeout=15)
            await clients[listener_role].expect_text(proposed.line, timeout=15)
            brain.confirm_spoken(proposed.line)
            listener.hear(
                sender=brain.name, event_id=f"world-heard-{turn + 1}",
                line=proposed.line,
            )
            transcript.append({
                "speaker": brain.name,
                "line": proposed.line,
                "goal": proposed.goal,
                "plan": list(proposed.plan),
                "action": proposed.action,
                "goap_cost": proposed.cost,
                "speaker_echo_confirmed": True,
                "other_actor_heard": True,
            })
            if all("said_goodnight" in c.facts for c in controllers.values()):
                break
        complete = all("said_goodnight" in c.facts for c in controllers.values())
        return {
            "scope": "two_authenticated_evennia_clients_model_free_goap",
            "status": "complete" if complete else "turn_capped",
            "variant": variant,
            "turn_cap": turn_cap,
            "turns": len(transcript),
            "model_calls": 0,
            "world_speech": len(transcript),
            "planning_calls": {role: c.planning_calls for role, c in controllers.items()},
            # Operator-only trace. Never supplied to the other participant.
            "private_facts": {role: sorted(c.facts) for role, c in controllers.items()},
            "transcript": transcript,
        }
    finally:
        await asyncio.gather(*(client.close() for client in clients.values()),
                             return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-person live Evennia social GOAP")
    parser.add_argument("--variant", choices=("cautious", "mutual", "mismatch"),
                        default="cautious")
    parser.add_argument("--turn-cap", type=int, default=24)
    parser.add_argument("--out", type=Path,
                        default=Path(".ox-state/g7-social-trial.json"))
    args = parser.parse_args()
    result = asyncio.run(run(variant=args.variant, turn_cap=args.turn_cap))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for item in result["transcript"]:
        print(f'{item["speaker"]}: {item["line"]}')
    print("OX_G7_SOCIAL_GOAP_PASS" if result["status"] == "complete"
          else "OX_G7_SOCIAL_GOAP_INCOMPLETE")
    if result["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
