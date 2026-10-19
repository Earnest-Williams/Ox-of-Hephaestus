"""G3 physical inventory: real item identity, scarcity, world order receipts."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase
from evennia.utils.create import create_object

from commands.inventory import CmdOxInventory
from typeclasses.ship import CrewCharacter
from world.bootstrap import build_ship
from world.event_journal import inbox
from world.models import InventoryItem, SupplyOrder, WorkReceipt
from world.supply import (
    KIND, available_at, local_stock_for, seed_disposable_cargo_cartridges,
    total_local_spares,
)
from world.work_actions import execute_work, work_receipt

IDS = ["a" * 32, "b" * 32, "c" * 32, "d" * 32,
       "e" * 32, "f" * 32, "1" * 32, "2" * 32]


class SupplyWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.scrubber = self.ship["scrubber"]
        self.scrubber.db.spare_cartridges = 0
        self.teo = self.ship["environment"]
        self.mara = self.ship["cargo"]
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]
        self.assertTrue(self.scrubber.inject_fault()[0])
        self.scrubber.note_inspection(self.teo)
        self.assertTrue(self.scrubber.isolate(self.teo)[0])
        self.assertEqual(self.scrubber.state, "isolated")

    def test_request_accept_collect_travel_deliver_and_consume_once(self):
        serial, = seed_disposable_cargo_cartridges(count=1)
        self.assertEqual(available_at(self.ship["cargo_hold"]), 1)
        original = execute_work(self.teo, IDS[0], "request_supply", "inventory")
        self.assertEqual(original["status"], "succeeded")
        self.assertEqual(original["actor_dbref"], self.teo.dbref)
        self.assertEqual(execute_work(self.teo, IDS[0], "request_supply", "inventory"), original)
        self.assertEqual(SupplyOrder.objects.count(), 1)
        order = SupplyOrder.objects.get(pk=IDS[0])
        self.assertEqual(order.status, "requested")
        self.assertEqual(order.assigned_dbref, self.mara.dbref)
        self.assertEqual(len([e for e in inbox(self.mara)
                              if e["kind"]=="supply_request"]), 1)
        self.assertFalse(execute_work(
            self.ari, IDS[1], "accept_supply", "inventory",
            arguments={"order_id": IDS[0]},
        )["status"] == "succeeded")
        accept = execute_work(self.mara, IDS[2], "accept_supply", "inventory",
                              arguments={"order_id": IDS[0]})
        self.assertEqual(accept["status"], "succeeded")

        take = execute_work(self.mara, IDS[3], "collect_supply", "inventory",
                            arguments={"order_id": IDS[0]})
        self.assertEqual(take["status"], "succeeded")
        item = InventoryItem.objects.get(pk=serial)
        self.assertEqual(item.state, "carried")
        self.assertEqual(item.carrier_dbref, self.mara.dbref)
        self.assertIsNone(item.location_dbref)
        self.assertEqual(available_at(self.ship["cargo_hold"]), 0)
        self.assertEqual(execute_work(self.mara, IDS[3], "collect_supply",
                                      "inventory", arguments={"order_id": IDS[0]}), take)
        # The receipt belongs exclusively to its true world actor.
        self.assertEqual(work_receipt(self.lin, IDS[3])["status"], "unknown")
        with self.assertRaises(PermissionError):
            execute_work(self.lin, IDS[3], "collect_supply", "inventory",
                         arguments={"order_id": IDS[0]})
        # Carrying an item in Cargo Hold is not equivalent to delivery.
        denied = execute_work(self.mara, IDS[4], "deliver_supply", "inventory",
                              arguments={"order_id": IDS[0]})
        self.assertEqual(denied["status"], "failed")
        self.assertEqual(item.state, "carried")
        self.assertTrue(self.mara.move_to(self.ship["environmental"], quiet=True))
        self.assertEqual(execute_work(
            self.mara, IDS[4], "deliver_supply", "inventory",
            arguments={"order_id": IDS[0]},
        ), denied)
        delivery = execute_work(
            self.mara, IDS[5], "deliver_supply", "inventory",
            arguments={"order_id": IDS[0]},
        )
        self.assertEqual(delivery["status"], "succeeded")
        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.state, "stored")
        self.assertEqual(item.location_dbref, self.ship["environmental"].dbref)
        self.assertIsNone(item.carrier_dbref)
        self.assertEqual(order.status, "delivered")
        self.assertEqual(total_local_spares(self.scrubber), 1)
        self.assertEqual(self.scrubber.db.spare_cartridges, 0)
        self.assertEqual(len([e for e in inbox(self.teo)
                              if e["kind"]=="supply_replenished"]), 1)
        self.assertEqual(execute_work(
            self.mara, IDS[5], "deliver_supply", "inventory",
            arguments={"order_id": IDS[0]},
        ), delivery)
        # Real local A-01 action consumes precisely that physical serialized item.
        self.assertEqual(execute_work(
            self.teo, IDS[6], "replace", "scrubber",
        )["status"], "succeeded")
        item.refresh_from_db()
        self.assertEqual(item.state, "consumed")
        self.assertIsNone(item.location_dbref)
        self.assertEqual(item.consumed_by_dbref, self.teo.dbref)
        self.assertEqual(total_local_spares(self.scrubber), 0)
        self.assertEqual(execute_work(self.teo, IDS[6], "replace", "scrubber")["status"],
                         "succeeded")
        self.assertEqual(InventoryItem.objects.count(), 1)
        self.assertEqual(InventoryItem.objects.filter(state="consumed").count(), 1)
        self.assertEqual(SupplyOrder.objects.count(), 1)
        self.assertEqual(len([e for e in self.scrubber.db.event_history
                              if e["operation"] == "replace"]), 1)

    def test_no_stock_does_not_become_zero_until_local_observation(self):
        self.assertIsNone(local_stock_for(self.lin, IDS[0])["local_cartridges"])
        with self.assertRaises(ValueError):
            local_stock_for(self.lin, "bad")
        self.assertEqual(local_stock_for(self.mara, IDS[0])["local_cartridges"], 0)
        self.assertEqual(local_stock_for(self.teo, IDS[0])["local_cartridges"], 0)
        for current in (self.ari, self.lin):
            self.assertEqual(local_stock_for(current, IDS[0])["carried"], [])
        serial, = seed_disposable_cargo_cartridges(count=1)
        self.assertEqual(local_stock_for(self.mara, IDS[0])["local_cartridges"], 1)
        self.assertIsNone(local_stock_for(self.lin, IDS[0])["local_cartridges"])
        # The standard ship bootstrap is idempotent and never mints new stock.
        build_ship()
        self.assertEqual(InventoryItem.objects.count(), 1)
        self.assertEqual(InventoryItem.objects.get(pk=serial).state, "stored")
        cmd = CmdOxInventory()
        cmd.caller = self.mara
        cmd.args = IDS[0]
        with patch.object(self.mara, "msg") as output:
            cmd.func()
        packet = output.call_args.kwargs["ox_inventory"]
        self.assertEqual(json.loads(packet[0][0])["actor_dbref"], self.mara.dbref)

    def test_world_refuses_remote_or_wrong_role_and_never_spontaneously_stocks(self):
        self.assertEqual(InventoryItem.objects.count(), 0)
        self.assertEqual(execute_work(
            self.ari, IDS[0], "request_supply", "inventory"
        )["status"], "failed")
        self.assertEqual(SupplyOrder.objects.count(), 0)
        self.assertTrue(self.teo.move_to(self.ship["mess"], quiet=True))
        self.assertEqual(execute_work(
            self.teo, IDS[1], "request_supply", "inventory"
        )["status"], "failed")
        self.assertEqual(SupplyOrder.objects.count(), 0)
        self.assertTrue(self.teo.move_to(self.ship["environmental"], quiet=True))
        self.assertEqual(execute_work(
            self.teo, IDS[2], "request_supply", "inventory"
        )["status"], "succeeded")
        self.assertEqual(InventoryItem.objects.count(), 0)
        self.assertEqual(execute_work(
            self.mara, IDS[3], "collect_supply", "inventory",
            arguments={"order_id": IDS[2]},
        )["status"], "failed")

    def test_two_orders_cannot_collect_one_cartridge_twice(self):
        serial, = seed_disposable_cargo_cartridges()
        # Simulate two legitimate accepted world work orders assigned to
        # distinct real cargo-role people, sharing a single physical unit.
        other = create_object("typeclasses.ship.CrewCharacter", key="Cargo Relief",
                              location=self.ship["cargo_hold"])
        other.db.crew_role = "cargo_officer"
        order1 = SupplyOrder.objects.create(
            order_id=IDS[0], requester_dbref=self.teo.dbref,
            assigned_dbref=self.mara.dbref, item_kind=KIND,
            delivery_room_dbref=self.ship["environmental"].dbref,
            status="accepted", created_game_time=1,
        )
        order2 = SupplyOrder.objects.create(
            order_id=IDS[1], requester_dbref=self.teo.dbref,
            assigned_dbref=other.dbref, item_kind=KIND,
            delivery_room_dbref=self.ship["environmental"].dbref,
            status="accepted", created_game_time=1,
        )
        first = execute_work(self.mara, IDS[2], "collect_supply", "inventory",
                             arguments={"order_id":order1.order_id})
        second = execute_work(other, IDS[3], "collect_supply", "inventory",
                              arguments={"order_id":order2.order_id})
        self.assertEqual([first["status"], second["status"]], ["succeeded", "failed"])
        self.assertEqual(InventoryItem.objects.get(pk=serial).carrier_dbref,
                         self.mara.dbref)
        self.assertEqual(InventoryItem.objects.filter(state="carried").count(), 1)
        self.assertEqual(SupplyOrder.objects.get(pk=IDS[1]).status, "accepted")

    def test_atomic_world_rollback_preserves_stock_and_private_event_history(self):
        serial, = seed_disposable_cargo_cartridges()
        order = execute_work(self.teo, IDS[0], "request_supply", "inventory")
        self.assertEqual(order["status"], "succeeded")
        self.assertEqual(execute_work(self.mara, IDS[1], "accept_supply", "inventory",
                                      arguments={"order_id": IDS[0]})["status"], "succeeded")
        count = len(inbox(self.mara))
        with self.assertRaises(RuntimeError), transaction.atomic():
            work = execute_work(self.mara, IDS[2], "collect_supply", "inventory",
                                arguments={"order_id": IDS[0]})
            self.assertEqual(work["status"], "succeeded")
            raise RuntimeError("simulate crash before commit")
        self.assertEqual(InventoryItem.objects.get(pk=serial).state, "stored")
        self.assertEqual(SupplyOrder.objects.get(pk=IDS[0]).status, "accepted")
        self.assertFalse(WorkReceipt.objects.filter(pk=IDS[2]).exists())
        self.assertEqual(len(inbox(self.mara)), count)


    def test_unique_pending_shortage_across_distinct_work_ids(self):
        original = execute_work(self.teo, IDS[0], "request_supply", "inventory")
        self.assertEqual(original["status"], "succeeded")
        duplicate = execute_work(self.teo, IDS[1], "request_supply", "inventory")
        self.assertEqual(duplicate["status"], "failed")
        self.assertEqual(SupplyOrder.objects.count(), 1)
        self.assertEqual(len([e for e in inbox(self.mara)
                              if e["kind"] == "supply_request"]), 1)
        self.assertEqual(execute_work(self.teo, IDS[1], "request_supply", "inventory"),
                         duplicate)



if __name__ == "__main__":
    import unittest
    unittest.main()
