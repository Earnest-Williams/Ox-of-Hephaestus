"""Seeded restart/ACK-loss trials for the *handler* work-step protocol.

This bounded fake port tests crash ordering and request-ID conservation,
not the real Evennia world authorization (covered by separate live/PG jobs).
"""
from __future__ import annotations

import copy
import random
import unittest

from ox_ai.ports.base import ActionOutcome
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption

ACTORS = {"lin": "#21", "ari": "#22", "mara": "#23", "teo": "#24"}


class ReceiptWorld:
    def __init__(self):
        self.receipts = {}
        self.submit_counts = {}
        self.drop_ack_once = False
        self.refuse_next = False

    async def submit_work(self, request):
        identity = request.request_id
        self.submit_counts[identity] = self.submit_counts.get(identity, 0) + 1
        if identity not in self.receipts:
            status = "failed" if self.refuse_next else "succeeded"
            self.refuse_next = False
            self.receipts[identity] = ActionOutcome(
                identity, status, "world_refused" if status == "failed"
                else "world_accepted",
                None if status == "failed" else "oxevt-confirmed-" + identity,
            )
        if self.drop_ack_once:
            self.drop_ack_once = False
            return ActionOutcome(identity, "unknown", "Lost ACK")
        return self.receipts[identity]

    async def reconcile_work(self, identity):
        return self.receipts.get(
            identity, ActionOutcome(identity, "unknown", "no_authorised_receipt")
        )


class DurableSnapshot:
    def __init__(self):
        self.live = {}
        self.saved = {}

    def checkpoint(self):
        self.saved = copy.deepcopy(self.live)

    def recover(self):
        self.live = copy.deepcopy(self.saved)
        return WorkStepLedger(self.live, self.checkpoint, character_ids=ACTORS)

    def ledger(self):
        return WorkStepLedger(self.live, self.checkpoint, character_ids=ACTORS)


class AdversarialLedgerTests(unittest.IsolatedAsyncioTestCase):
    async def test_seeded_crash_matrix_multiple_actors_and_exact_requests(self):
        for seed in (7, 57, 20261019):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                world = ReceiptWorld()
                snapshots = DurableSnapshot()
                for index in range(24):
                    stage = f"seed-{seed}-step-{index}"
                    role = rng.choice(tuple(ACTORS))
                    interrupt = rng.choice(
                        (None, "prepared", "committed", "ack", "ack")
                    )
                    previous = snapshots.ledger()
                    request_crash = (
                        stage + ":" + interrupt if interrupt else None
                    )
                    if interrupt:
                        with self.assertRaises(SimulatedWorkInterruption):
                            await previous.run(
                                stage, role, "radio", "ship", world,
                                interrupt_at=request_crash,
                            )
                        # A process crash discards in-memory changes *after*
                        # the last durable checkpoint, but not world receipts.
                        recovered = snapshots.recover()
                        outcome = await recovered.run(
                            stage, role, "radio", "ship", world
                        )
                    else:
                        outcome = await previous.run(
                            stage, role, "radio", "ship", world
                        )
                    self.assertEqual(outcome.status, "succeeded")
                    identity = snapshots.saved["work_steps"][stage]["request_id"]
                    self.assertEqual(world.submit_counts[identity], 1)
                    self.assertEqual(world.receipts[identity], outcome)
                    self.assertEqual(
                        (await snapshots.recover().run(
                            stage, role, "radio", "ship", world)),
                        outcome,
                    )
                self.assertEqual(len(world.receipts), 24)
                self.assertEqual(set(world.submit_counts), set(world.receipts))

    async def test_lost_transport_ack_reconciles_without_new_id(self):
        world = ReceiptWorld()
        snapshots = DurableSnapshot()
        world.drop_ack_once = True
        with self.assertRaises(RuntimeError):
            await snapshots.ledger().run(
                "teo-replace", "teo", "replace_scrubber",
                "scrubber", world,
            )
        first_id = snapshots.saved["work_steps"]["teo-replace"]["request_id"]
        self.assertEqual(snapshots.saved["work_steps"]["teo-replace"]["status"],
                         "prepared")
        result = await snapshots.recover().run(
            "teo-replace", "teo", "replace_scrubber", "scrubber", world,
        )
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(world.submit_counts[first_id], 1)
        self.assertEqual(set(world.receipts), {first_id})

    async def test_failed_world_receipt_is_never_upgraded_on_replay(self):
        world = ReceiptWorld()
        world.refuse_next = True
        snapshots = DurableSnapshot()
        with self.assertRaises(RuntimeError):
            await snapshots.ledger().run(
                "scarce-item", "mara", "collect_supply", "inventory", world,
                arguments={"order_id": "b" * 32},
            )
        stored = snapshots.saved["work_steps"]["scarce-item"]
        self.assertEqual(stored["status"], "failed")
        identity = stored["request_id"]
        with self.assertRaises(PermissionError):
            await snapshots.recover().run(
                "scarce-item", "teo", "collect_supply", "inventory", world,
                arguments={"order_id": "b" * 32},
            )
        result = await snapshots.recover().run(
            "scarce-item", "mara", "collect_supply", "inventory", world,
            arguments={"order_id": "b" * 32},
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(world.submit_counts[identity], 1)
        self.assertEqual(len(world.receipts), 1)


if __name__ == "__main__":
    unittest.main()
