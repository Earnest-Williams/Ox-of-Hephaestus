"""G3c five-crew supply cooperation across *actual* world work and movement.

This is a small, restart-safe dispatcher, not a magical collective mind.
Teo and Mara have separate authenticated sockets, event inboxes, native
Concordia choices, private epistemic ledgers and individually bound WorkReceipt
IDs. The supervisor coordinates stages but never gives one actor another
actor's private memories or bypasses a physical precondition.
"""
from __future__ import annotations

import uuid

from ox_ai.agents.crew import CommandOption
from ox_ai.ports.base import ActionOutcome
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.ports.evennia.inventory import InventoryPort
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption


class SupplyNotReady(RuntimeError):
    """Unverified source/destination conditions; do not submit physical work."""


class CooperativeSupply:
    """One demonstrated Teo-to-Mara cartridge dependency per supervisor."""

    def __init__(self, supervisor):
        self.sup = supervisor
        self.record = supervisor.state.get("g3_supply")
        if self.record is not None:
            if (not isinstance(self.record, dict)
                    or set(self.record) != {
                        "version", "requester", "carrier", "alarm_id",
                        "work_steps", "delivered", "completed",
                    } or self.record["version"] != 1
                    or self.record["requester"] != supervisor.ids["teo"]
                    or self.record["carrier"] != supervisor.ids["mara"]
                    or not isinstance(self.record["work_steps"], dict)
                    or type(self.record["delivered"]) is not bool
                    or type(self.record["completed"]) is not bool):
                raise PermissionError("Foreign or invalid world-supply checkpoint")

    def _ledger(self):
        if self.record is None:
            raise RuntimeError("No source-grounded world supply task")
        return WorkStepLedger(
            self.record, self.sup.checkpoint,
            character_ids=self.sup.ids,
        )

    def _stage_state(self, name):
        if self.record is None:
            return None
        return self.record["work_steps"].get(name, {}).get("status")

    def _order_id(self):
        entry = self.record["work_steps"].get("request")
        if not entry or entry["status"] != "succeeded":
            raise SupplyNotReady("No world-confirmed original supply order ID")
        return entry["request_id"]

    async def _event(self, role: str, kind: str, order_id: str) -> dict | None:
        # Do not allow Mara to learn that Teo wants help through a shared
        # supervisor variable. She must receive her own *world addressed*
        # order; Teo must separately receive the world delivery notice.
        messages = await self.sup.read_inbox(role)
        return next(
            (e for e in reversed(messages)
             if e["kind"] == kind
             and e["data"].get("order_id") == order_id),
            None,
        )

    async def _work(self, stage: str, role: str, verb: str, *, order_id=None,
                    interrupt_at=None):
        ledger = self._ledger()
        args = {} if order_id is None else {"order_id": order_id}
        if stage not in ledger.steps:
            # Every major transition is independently proposed by the
            # selected person through the existing nonblocking cognition
            # scheduler. Deferral is not an executed physical operation.
            chosen = await self.sup.choose(
                role,
                CommandOption(
                    "Perform my verified " + verb.replace("_", " ") + " obligation",
                    verb, "inventory", args,
                ),
                alternative="Defer while I verify the world conditions",
            )
            if chosen.verb != verb:
                self.sup.brains[role].agent.record_outcome(ActionOutcome(
                    chosen.request_id, "succeeded",
                    "Private deferral; no world work attempted",
                ))
                return False
            self.sup.brains[role].selected_procedure(chosen)
        port = DurableEvenniaPort(self.sup.clients[role])
        outcome = await ledger.run(
            stage, role, verb, "inventory", port,
            arguments=args, interrupt_at=interrupt_at,
        )
        if outcome.status != "succeeded" or not outcome.source_event_id:
            raise SupplyNotReady("World refused or could not confirm supply step")
        return True

    async def _start(self) -> bool:
        """Only a genuinely blocked Teo and verified local zero can request."""
        if self.record is not None:
            return True
        await self.sup._start_job("teo")
        job = self.sup.state["specialist_jobs"]["teo"]
        if job is None:
            return False
        if not job["deferred"]:
            await self.sup._advance_job("teo")
        job = self.sup.state["specialist_jobs"]["teo"]
        if job is None or not job["deferred"]:
            return False
        await self.sup.ensure_station("teo", "Environmental Plant")
        observed = await InventoryPort(self.sup.clients["teo"]).observe()
        if observed.local_cartridges is None:
            raise SupplyNotReady("Teo lacks direct local stock evidence")
        self.sup.epistemics["teo"].observe_verified(
            "scrubber.spares", observed.local_cartridges,
            evidence_id="worldinv-" + uuid.uuid4().hex,
            at=observed.game_time, valid_for=0, source="world_local",
        )
        if observed.local_cartridges != 0:
            return False
        self.sup.epistemics["teo"].ask(
            "cargo.reserve", reason="Only cargo crew can physically verify the reserve",
        )
        self.record = {
            "version": 1, "requester": self.sup.ids["teo"],
            "carrier": self.sup.ids["mara"], "alarm_id": job["event_id"],
            "work_steps": {}, "delivered": False, "completed": False,
        }
        self.sup.state["g3_supply"] = self.record
        self.sup.checkpoint()
        return True

    async def advance(self, *, stop_after_request=False,
                      drop_delivery_ack=False) -> str:
        """Progress one world-grounded supply dependency through real crew.

        All known and unknown work outcomes are persisted by WorkStepLedger.
        A deliberately lost delivery ACK leaves the stage prepared, and the
        next handler process first reconciles the SAME ID with Evennia.
        """
        self.sup.lease.assert_held()
        if not await self._start():
            return "not_required"
        if self.record["completed"]:
            return "completed"
        if not await self._work("request", "teo", "request_supply"):
            return "teo_deferred"
        order_id = self._order_id()
        if stop_after_request:
            return "requested"

        if await self._event("mara", "supply_request", order_id) is None:
            return "awaiting_mara_world_event"
        self.sup.epistemics["mara"].ask(
            "cargo.reserve", reason="A request is not evidence of cargo on hand",
        )
        if not await self._work("accept", "mara", "accept_supply", order_id=order_id):
            return "mara_deferred"

        if self._stage_state("collect") != "succeeded":
            await self.sup.ensure_station("mara", "Cargo Hold")
            reading = await InventoryPort(self.sup.clients["mara"]).observe()
            if reading.local_cartridges is None:
                return "stock_unknown"
            self.sup.epistemics["mara"].observe_verified(
                "cargo.reserve", reading.local_cartridges,
                evidence_id="worldinv-" + uuid.uuid4().hex,
                at=reading.game_time, valid_for=0, source="world_local",
            )
            if reading.local_cartridges == 0:
                self.sup.epistemics["mara"].ask(
                    "cargo.next_restock_at",
                    reason="No replenishment is physically observed at Cargo Hold",
                )
                self.sup.checkpoint()
                return "awaiting_cargo_stock"
            if not await self._work("collect", "mara", "collect_supply", order_id=order_id):
                return "mara_deferred"

        collected = await self._event("mara", "supply_collected", order_id)
        if collected is None:
            return "awaiting_mara_collection_receipt"
        item_id = collected["data"].get("item_id")
        if not isinstance(item_id, str) or not item_id.startswith("oxitem-"):
            raise PermissionError("Collection had no authentic serial evidence")

        await self.sup.ensure_station("mara", "Environmental Plant")
        if self._stage_state("deliver") is None:
            carried = await InventoryPort(self.sup.clients["mara"]).observe()
            if item_id not in carried.carried_items:
                # In-transit reports are not a physical handoff or proof of
                # current carriage. Refuse to dispatch unsupported delivery.
                return "physical_carriage_not_verified"
        if not await self._work(
            "deliver", "mara", "deliver_supply", order_id=order_id,
            interrupt_at=("deliver:committed" if drop_delivery_ack else None),
        ):
            return "mara_deferred"

        delivered = await self._event("teo", "supply_replenished", order_id)
        if delivered is None or delivered["data"].get("item_id") != item_id:
            return "awaiting_teo_world_delivery_evidence"
        await self.sup.ensure_station("teo", "Environmental Plant")
        stock = await InventoryPort(self.sup.clients["teo"]).observe()
        if stock.local_cartridges is None or stock.local_cartridges < 1:
            return "delivery_not_locally_confirmed"
        self.sup.epistemics["teo"].observe_verified(
            "scrubber.spares", stock.local_cartridges,
            evidence_id="worldinv-" + uuid.uuid4().hex,
            at=stock.game_time, valid_for=0, source="world_local",
        )
        self.record["delivered"] = True
        self.sup.checkpoint()
        progressed = await self.sup._advance_job("teo")
        job = self.sup.state["specialist_jobs"]["teo"]
        if job is None:
            self.record["completed"] = True
            self.sup.checkpoint()
            return "completed"
        return "awaiting_teo_maintenance" if not progressed else "teo_work_in_progress"
