"""A bounded, inspectable Concordia-to-Evennia pump-repair experiment.

This is a LOCAL IN-PROCESS TEST HARNESS, not the planned external AI
transport. The agent may only choose ordinary player-visible commands. Real
Evennia command parsing, exit traversal, access locks and pump transitions
remain authoritative. It never receives the pump's database state or writes it.

The deterministic model used by CI verifies integration, not intelligence.
A separate opt-in live trial can be run with a configured model endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from unittest.mock import patch

from evennia.utils import gametime

from world.bootstrap import build_ship
from typeclasses.ship import CoolingPump, FixedFixture


@dataclass(frozen=True)
class TrialStep:
    """One proposed command and the in-world text returned to the character."""

    command: str
    response: str


@dataclass(frozen=True)
class TrialResult:
    """Operator-side verdict, NOT information shown to the agent."""

    success: bool
    reason: str
    steps: tuple[TrialStep, ...]
    inference_calls: int
    pump_state: str
    event_history: tuple[dict, ...]


class LocalCharacterTerminal:
    """Capture what an unpuppeted character sees when executing MUD commands.

    Calling the character's regular `execute_cmd` uses the same cmdhandler,
    exits and permission checks as a normal player. Messages are captured from
    the character's `msg` method because this short experiment has no socket
    session. No out-of-band object readout is returned to the agent.
    """

    def __init__(self, character):
        self.character = character

    def command(self, line: str) -> str:
        """Issue exactly one ordinary in-world command and collect its text."""
        if not line or "\n" in line or "\r" in line:
            raise ValueError("Exactly one nonempty MUD command is required")
        received = []

        def collect(text=None, **kwargs):
            if text is None:
                return
            if isinstance(text, tuple):
                text = text[0]
            received.append(str(text))

        with patch.object(self.character, "msg", side_effect=collect):
            deferred = self.character.execute_cmd(line)
            errors = []
            deferred.addErrback(lambda failure: errors.append(failure))
            if not deferred.called or deferred.paused:
                raise RuntimeError(
                    "Command did not complete synchronously; use a normal "
                    "session transport for asynchronous game commands"
                )
            if errors:
                errors[0].raiseException()
        return "\n".join(received).strip() or "(The command produced no text.)"

    def options(self):
        """Offer commands for locally visible objects/exits, not future state.

        A visible pump provides generic operations regardless of whether
        they are permitted or would currently succeed. World rules adjudicate.
        """
        from ox_ai.agents.crew import CommandOption

        body = self.character
        place = body.location
        if place is None:
            raise RuntimeError("Character has no physical location")
        options = [CommandOption("Look around", "look")]
        for exit_obj in sorted(place.exits, key=lambda item: item.key):
            if exit_obj.access(body, "view"):
                options.append(
                    CommandOption(f"Go {exit_obj.key}", exit_obj.key)
                )
        for obj in sorted(place.contents, key=lambda item: item.key):
            if obj == body or not isinstance(obj, FixedFixture):
                continue
            if not obj.access(body, "view"):
                continue
            if callable(getattr(obj, "readout", None)):
                # Only visible object names are shared; no remote metadata.
                short_name = "pump" if isinstance(obj, CoolingPump) else (
                    "console" if "Console" in obj.key else "roster"
                )
                options.append(
                    CommandOption(f"Inspect {obj.key}", "inspect", short_name)
                )
            if isinstance(obj, CoolingPump):
                for verb in ("isolate", "repair", "commission"):
                    options.append(
                        CommandOption(
                            f"{verb.capitalize()} {obj.key}", verb, "pump"
                        )
                    )
        options.append(CommandOption("Finish trial (claim completed)", "finish"))
        return tuple(options)


def _mud_line(request) -> str:
    """Render a tightly bounded proposal as one ordinary player command."""
    if request.arguments:
        raise ValueError("This experiment does not accept command arguments")
    if request.verb == "finish":
        return "finish"
    if request.target is not None:
        if request.target not in {"pump", "console", "roster"}:
            raise ValueError("Unrecognised equipment target")
        return f"{request.verb} {request.target}"
    return request.verb


def _visible_observation(agent, text: str, serial: int) -> None:
    """Provide only command output to this agent, never fixture internals."""
    from ox_ai.ports.base import WorldObservation

    agent.observe(
        WorldObservation(
            observation_id=f"local-trial-{serial}",
            character_id=agent.identity.character_id,
            game_time=float(gametime.gametime(absolute=True)),
            text=text,
        )
    )


def conduct_repair_trial(
    model,
    *,
    max_steps: int = 16,
    trace_path: Path | None = None,
) -> TrialResult:
    """Run a single Concordia engineer through human-equivalent commands.

    OPERATOR SETUP: The builder finds the existing ship, places Ari on the
    bridge and triggers a fault if the pump is normal. These actions happen
    *before* the AI starts and are not agent commands. No history is reset.
    If already faulted/isolated/repaired, the test resumes existing state.

    OPERATOR VERDICT: Success requires the AI to choose Finish and the
    authoritative Evennia event log to contain AI-character isolation,
    repair and commissioning of the pump during this trial.
    """
    from ox_ai.agents.crew import CrewAgent, CrewIdentity
    from ox_ai.ports.base import ActionOutcome

    if max_steps < 1 or max_steps > 50:
        raise ValueError("max_steps must be between 1 and 50")
    ship = build_ship()
    pump = ship["pump"]
    body = ship["watch"]

    if pump.state == "normal":
        ok, reason = pump.inject_fault()  # Test-operator scenario event.
        if not ok:
            raise RuntimeError(reason)
    if pump.state not in ("low_pressure", "isolated", "repaired"):
        raise RuntimeError(f"Unexpected pump state {pump.state!r}")

    # Only the test fixture is allowed to reposition this body. After this
    # point all navigation and engineering work uses player commands.
    if not body.move_to(ship["bridge"], quiet=True):
        raise RuntimeError("Could not stage the engineer on the bridge")
    start_event = int(pump.db.event_seq or 0)
    identity = CrewIdentity(
        agent_id="ox.repair.trial",
        character_id=f"evennia:{body.dbref}",
        name="Ari Sen",
        duty="You are the engineer on watch. You must physically travel to equipment.",
        goal=(
            "Investigate the cooling loop problem. Restore Pump P-01 safely "
            "by using ordinary in-world commands. Inspect and verify the "
            "result; choose Finish only when you believe the work is complete. "
            "You cannot teleport or edit ship state."
        ),
    )
    agent = CrewAgent(identity, model, journal_path=trace_path)
    terminal = LocalCharacterTerminal(body)
    steps: list[TrialStep] = []

    # The agent sees the real bridge through the same look command as a human.
    initial = terminal.command("look")
    _visible_observation(agent, initial, 0)

    ended = False
    for index in range(1, max_steps + 1):
        choices = terminal.options()
        request = agent.decide(choices, expected_revision=agent.revision)
        valid = {
            (_mud_line_from_option(option))
            for option in choices
        }
        line = _mud_line(request)
        if line not in valid:
            raise PermissionError(f"Agent attempted an unoffered command: {line}")

        if line == "finish":
            message = "Agent ended the trial without further game commands."
            steps.append(TrialStep("finish", message))
            agent.record_outcome(
                ActionOutcome(request.request_id, "succeeded", message)
            )
            ended = True
            break

        response = terminal.command(line)
        # In Evennia a player normally gets an arrival description. Obtain
        # it explicitly with a second, ordinary `look` after moving, and
        # record it as part of the same reported step.
        if request.target is None and line != "look":
            if any(line == obj.key for obj in ship["bridge"].exits + ship["passage"].exits + ship["engineering"].exits):
                response += "\n" + terminal.command("look")
        steps.append(TrialStep(line, response))
        # The handler only claims the command returned, not that it repaired
        # anything. The game output is delivered to the agent as observation.
        agent.record_outcome(
            ActionOutcome(
                request.request_id,
                "succeeded",
                f"Command delivered; world response: {response}",
            )
        )
        _visible_observation(agent, f"Command '{line}' returned:\n{response}", index)

    # Never pass these values back to the cognitive loop: external scoring.
    new_events = tuple(
        dict(e) for e in (pump.db.event_history or [])
        if int(e["event_id"].split("-")[-1]) > start_event
    )
    ai_ops = [
        e["operation"] for e in new_events
        if e["actor_dbref"] == body.dbref
    ]
    did_repair = all(
        operation in ai_ops for operation in ("isolate", "repair", "commission")
    )
    in_order = (
        "isolate" in ai_ops and "repair" in ai_ops and "commission" in ai_ops
        and ai_ops.index("isolate") < ai_ops.index("repair") < ai_ops.index("commission")
    )
    success = ended and pump.state == "normal" and did_repair and in_order
    if success:
        reason = "Verified: AI-character commands isolated, repaired and commissioned P-01."
    elif not ended:
        reason = "Step budget exhausted before the agent chose Finish."
    else:
        reason = "Agent claimed completion without a full authorised repair cycle."

    return TrialResult(
        success=success,
        reason=reason,
        steps=tuple(steps),
        inference_calls=agent.usage.total_calls,
        pump_state=pump.state,
        event_history=new_events,
    )


def _mud_line_from_option(option) -> str:
    """Map an offered command to the exact line sent through Evennia."""
    from types import SimpleNamespace

    return _mud_line(
        SimpleNamespace(
            verb=option.verb,
            target=option.target,
            arguments=option.arguments,
        )
    )


def live_trial() -> TrialResult:
    """Opt-in LLM trial from `evennia shell` in a local, trusted game.

    Environment:
      OPENAI_API_KEY       Required unless local endpoint uses a dummy key.
      OX_LLM_MODEL         Model ID, e.g. a local model ID or API model name.
      OX_LLM_BASE_URL      Optional OpenAI-compatible URL for local inference.
      OX_TRIAL_TRACE       Optional path for a JSONL decision/observation log.
    """
    from concordia.contrib.language_models.openai.gpt_model import (
        GptLanguageModel,
    )

    model_name = os.getenv("OX_LLM_MODEL")
    api_key = os.getenv("OPENAI_API_KEY")
    if not model_name or not api_key:
        raise RuntimeError(
            "Set OX_LLM_MODEL and OPENAI_API_KEY explicitly; no live "
            "inference will be initiated without them."
        )
    model = GptLanguageModel(
        model_name=model_name,
        api_key=api_key,
        api_base=os.getenv("OX_LLM_BASE_URL") or None,
    )
    raw = os.getenv("OX_TRIAL_TRACE")
    result = conduct_repair_trial(
        model, trace_path=Path(raw) if raw else None
    )
    for num, step in enumerate(result.steps, start=1):
        print(f"\n[{num}] Ari enters: {step.command}\n{step.response}")
    print(f"\nVerdict: {result.reason}")
    print(f"Physical pump state: {result.pump_state}")
    print(f"Inference calls: {result.inference_calls}")
    return result
