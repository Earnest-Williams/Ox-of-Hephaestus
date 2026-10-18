"""Durable, actor-scoped work steps over the world-owned WorkReceipt table.

The caller owns a private supervisor journal. A newly proposed work attempt is
checkpointed BEFORE network submission. On reconnection the same ID is
reconciled before anything else; a positive world 'no receipt' permits the
same ID to be submitted, never a replacement ID. Unknown transport outcomes
remain unresolved. Completed steps are never resent.

No handler action is evidence of world truth: the world validates all work,
and each stage's caller must inspect relevant world state before proceeding.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
import uuid

from ox_ai.ports.base import ActionOutcome, ActionRequest
from ox_ai.ports.evennia.durable import DurableEvenniaPort


class SimulatedWorkInterruption(RuntimeError):
    """CI-only crash point; no actual permission or physical side effect."""


class WorkStepLedger:
    """One supervisor's durable stage ledger, not a world truth store."""

    def __init__(
        self,
        record: dict,
        checkpoint: Callable[[], None],
        *,
        character_ids: Mapping[str, str],
    ) -> None:
        self.record = record
        self.checkpoint = checkpoint
        self.character_ids = character_ids
        self.steps = record.setdefault("work_steps", {})

    async def run(
        self, stage: str, role: str, verb: str, target: str,
        port: DurableEvenniaPort,
        *,
        prepare: Callable[[], Awaitable[None]] | None = None,
        arguments: Mapping[str, str] | None = None,
        interrupt_at: str | None = None,
    ) -> ActionOutcome:
        """Execute/reconcile exactly one world attempt under a stable ID.

        Simulation injection strings: '<stage>:prepared' (crash after
        checkpoint but before any send), '<stage>:committed' (world
        acknowledged, crash before outcome checkpoint), and '<stage>:ack'
        (same world result, after receiving ACK but before checkpoint).
        """
        if not isinstance(stage, str) or not stage or len(stage) > 80:
            raise ValueError("Invalid named work stage")
        if role not in self.character_ids:
            raise PermissionError("Unknown world actor for stage")
        actor = self.character_ids[role]
        args = dict(arguments or {})
        pending = self.steps.get(stage)
        if pending is None:
            if prepare is not None:
                await prepare()
            pending = {
                "request_id": uuid.uuid4().hex,
                "actor": actor, "role": role,
                "verb": verb, "target": target,
                "arguments": args, "status": "prepared",
            }
            self.steps[stage] = pending
            self.checkpoint()
            if interrupt_at == stage + ":prepared":
                raise SimulatedWorkInterruption(
                    f"World work {stage} checkpointed before submission"
                )
            # On this first run, send only after the intent is durable.
            action = ActionRequest(pending["request_id"], actor, verb, target, args)
            outcome = await port.submit_work(action)
        else:
            if (
                pending["actor"] != actor
                or pending["role"] != role
                or pending["verb"] != verb
                or pending["target"] != target
                or pending["arguments"] != args
            ):
                raise PermissionError("Recovered step no longer matches its identity")
            if pending["status"] in ("succeeded", "failed"):
                return ActionOutcome(
                    pending["request_id"], pending["status"],
                    str(pending["reason"]), pending.get("source_event_id"),
                )
            if pending["status"] != "prepared":
                raise RuntimeError("Unrecognized persisted work stage")
            # A prior send may have committed, failed, or never reached Evennia.
            outcome = await port.reconcile_work(pending["request_id"])
            if outcome.status == "unknown" and outcome.description == "no_authorised_receipt":
                # Explicit authenticated world absence is the only case
                # permitting a resend, always with the ORIGINAL request ID.
                outcome = await port.submit_work(ActionRequest(
                    pending["request_id"], actor, verb, target, args,
                ))

        # A handler crash after the world effect but before acknowledging it:
        # the durable stage remains 'prepared' and must reconcile on restart.
        if interrupt_at in (stage + ":committed", stage + ":ack"):
            if outcome.status != "succeeded":
                raise RuntimeError("Cannot simulate committed ACK for non-success")
            raise SimulatedWorkInterruption(
                f"World committed {stage}; persisted intent awaits reconciliation"
            )

        if outcome.status == "unknown":
            raise RuntimeError(
                f"Work {stage} outcome unknown; preserving intent {pending['request_id']}"
            )
        if outcome.status not in ("succeeded", "failed"):
            raise RuntimeError("Invalid world work outcome")
        pending["status"] = outcome.status
        pending["reason"] = outcome.description
        pending["source_event_id"] = outcome.source_event_id
        self.checkpoint()
        if outcome.status != "succeeded":
            raise RuntimeError(
                f"World refused {stage}; stored original refusal under "
                f"{pending['request_id']}"
            )
        return outcome
