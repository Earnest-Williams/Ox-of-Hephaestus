"""G3 handoff cannot skip world-addressed events or swap character identity."""
import unittest
from types import SimpleNamespace

from ox_ai.runtime.cooperative_supply import CooperativeSupply, SupplyNotReady

ORDER = "a" * 32


class FakeSupervisor:
    def __init__(self):
        self.ids = {"teo": "#41", "mara": "#42"}
        self.state = {"g3_supply": {
            "version": 1, "requester": "#41", "carrier": "#42",
            "alarm_id": "oxevt-v2-0005", "delivered": False,
            "completed": False, "work_steps": {
                "request": {"request_id": ORDER, "status": "succeeded"},
            },
        }}
        self.private = {
            "teo": [{"kind": "supply_requested", "data": {"order_id": ORDER}}],
            "mara": [],
        }

    async def read_inbox(self, role):
        return list(self.private[role])


class CooperativeSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_mara_knows_nothing_until_world_addresses_her(self):
        sup = FakeSupervisor()
        coordinator = CooperativeSupply(sup)
        self.assertEqual(coordinator._order_id(), ORDER)
        self.assertIsNone(await coordinator._event("mara", "supply_request", ORDER))
        sup.private["mara"].append({
            "kind": "supply_request",
            "data": {"order_id": "b" * 32},
        })
        self.assertIsNone(await coordinator._event("mara", "supply_request", ORDER))
        sup.private["mara"].append({
            "kind": "supply_request",
            "data": {"order_id": ORDER},
        })
        self.assertIsNotNone(await coordinator._event(
            "mara", "supply_request", ORDER,
        ))
        self.assertIsNone(await coordinator._event(
            "teo", "supply_replenished", ORDER,
        ))

    async def test_no_world_request_cannot_be_conjured_from_intent(self):
        sup = FakeSupervisor()
        sup.state["g3_supply"]["work_steps"].clear()
        with self.assertRaises(SupplyNotReady):
            CooperativeSupply(sup)._order_id()

    async def test_coordinator_refuses_foreign_restored_mind(self):
        sup = FakeSupervisor()
        sup.state["g3_supply"]["carrier"] = "#99"
        with self.assertRaises(PermissionError):
            CooperativeSupply(sup)


if __name__ == "__main__":
    unittest.main()
