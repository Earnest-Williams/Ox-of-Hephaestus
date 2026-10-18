"""No-network recovery cases for a world-owned work receipt and private intent."""
from __future__ import annotations

import asyncio
import copy
import unittest

from ox_ai.ports.base import ActionOutcome
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption


class WorldPort:
    def __init__(self):
        self.world_receipts = {}
        self.commands = []
        self.reconciliations = []
        self.online = True

    async def submit_work(self, request):
        self.commands.append(request)
        if request.request_id not in self.world_receipts:
            self.world_receipts[request.request_id] = ActionOutcome(
                request.request_id, "succeeded", "world_accepted", "oxevt-v2-0001",
            )
        return self.world_receipts[request.request_id]

    async def reconcile_work(self, request_id):
        self.reconciliations.append(request_id)
        return self.world_receipts.get(
            request_id,
            ActionOutcome(request_id, "unknown", "no_authorised_receipt"),
        )


class SupervisorState:
    def __init__(self, old=None):
        self.current = copy.deepcopy(old or {})
        self.snapshots = []

    def checkpoint(self):
        self.snapshots.append(copy.deepcopy(self.current))

    def ledger(self):
        return WorkStepLedger(
            self.current, self.checkpoint, character_ids={"ari": "#12", "iona": "#13"},
        )


class WorkStepTests(unittest.IsolatedAsyncioTestCase):
    async def test_crash_before_send_resends_same_world_id_only(self):
        world = WorldPort()
        first = SupervisorState()
        with self.assertRaises(SimulatedWorkInterruption):
            await first.ledger().run(
                "repair", "ari", "repair_pump", "pump", world,
                interrupt_at="repair:prepared",
            )
        saved = first.snapshots[-1]
        self.assertEqual(world.commands, [])
        original_id = saved["work_steps"]["repair"]["request_id"]
        restored = SupervisorState(saved)
        result = await restored.ledger().run(
            "repair", "ari", "repair_pump", "pump", world,
        )
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(world.reconciliations, [original_id])
        self.assertEqual([c.request_id for c in world.commands], [original_id])
        self.assertEqual(restored.current["work_steps"]["repair"]["status"],
                         "succeeded")

    async def test_crash_after_commit_before_ack_never_repeats_effect(self):
        world = WorldPort()
        first = SupervisorState()
        with self.assertRaises(SimulatedWorkInterruption):
            await first.ledger().run(
                "approve", "iona", "approve", "ship", world,
                interrupt_at="approve:committed",
            )
        original = world.commands[0].request_id
        self.assertEqual(first.current["work_steps"]["approve"]["status"],
                         "prepared")
        second = SupervisorState(first.snapshots[-1])
        result = await second.ledger().run(
            "approve", "iona", "approve", "ship", world,
        )
        self.assertEqual(result.source_event_id, "oxevt-v2-0001")
        self.assertEqual([c.request_id for c in world.commands], [original])
        self.assertEqual(world.reconciliations, [original])
        self.assertEqual(second.current["work_steps"]["approve"]["status"],
                         "succeeded")

    async def test_crash_after_ack_before_checkpoint_reconciles_original(self):
        world = WorldPort()
        first = SupervisorState()
        with self.assertRaises(SimulatedWorkInterruption):
            await first.ledger().run(
                "resolve", "ari", "resolve", "ship", world,
                interrupt_at="resolve:ack",
            )
        second = SupervisorState(first.snapshots[-1])
        self.assertEqual((await second.ledger().run(
            "resolve", "ari", "resolve", "ship", world,
        )).status, "succeeded")
        self.assertEqual(len(world.commands), 1)
        self.assertEqual(len(world.reconciliations), 1)
        third = SupervisorState(second.snapshots[-1])
        await third.ledger().run("resolve", "ari", "resolve", "ship", world)
        self.assertEqual(len(world.commands), 1)
        self.assertEqual(len(world.reconciliations), 1)

    async def test_unknown_network_outcome_fails_closed_and_preserves_intent(self):
        class Broken(WorldPort):
            async def submit_work(self, request):
                self.commands.append(request)
                return ActionOutcome(
                    request.request_id, "unknown", "No authoritative receipt",
                )
            async def reconcile_work(self, request_id):
                self.reconciliations.append(request_id)
                return ActionOutcome(
                    request_id, "unknown", "No authoritative receipt",
                )
        world = Broken()
        first = SupervisorState()
        with self.assertRaises(RuntimeError):
            await first.ledger().run(
                "repair", "ari", "repair_pump", "pump", world,
            )
        original = world.commands[0].request_id
        second = SupervisorState(first.snapshots[-1])
        with self.assertRaises(RuntimeError):
            await second.ledger().run(
                "repair", "ari", "repair_pump", "pump", world,
            )
        self.assertEqual(len(world.commands), 1)
        self.assertEqual(world.reconciliations, [original])
        self.assertEqual(second.current["work_steps"]["repair"]["status"],
                         "prepared")

    async def test_wrong_actor_or_action_cannot_rebind_stored_request(self):
        world = WorldPort()
        first = SupervisorState()
        await first.ledger().run(
            "repair", "ari", "repair_pump", "pump", world,
        )
        state = first.snapshots[-1]
        for role, verb, target in (
            ("iona", "repair_pump", "pump"),
            ("ari", "commission_pump", "pump"),
            ("ari", "repair_pump", "cargo"),
        ):
            restored = SupervisorState(state)
            with self.assertRaises(PermissionError):
                await restored.ledger().run(
                    "repair", role, verb, target, world,
                )
        self.assertEqual(len(world.commands), 1)

    async def test_preparation_never_runs_again_after_durable_intent(self):
        world = WorldPort()
        first = SupervisorState()
        calls = []
        async def prepared():
            calls.append("once")
        with self.assertRaises(SimulatedWorkInterruption):
            await first.ledger().run(
                "request", "ari", "request", "ship", world,
                prepare=prepared, interrupt_at="request:prepared",
            )
        second = SupervisorState(first.snapshots[-1])
        async def should_not_run():
            self.fail("Already persisted preparation repeated on restart")
        await second.ledger().run(
            "request", "ari", "request", "ship", world,
            prepare=should_not_run,
        )
        self.assertEqual(calls, ["once"])
