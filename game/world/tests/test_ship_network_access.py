"""Pure checks for source privacy, opaque acknowledgements and replay limits."""

from types import SimpleNamespace
import unittest

from world.ship_access_contact import LINK, SENSOR, OBSERVED
from world.ship_network_access import (
    DELIVERED, PRINCIPAL, NetworkAccessError, capture, present_delivery,
    seal, thermally_ready, unseal, valid_limit,
)

SECRET = "ab" * 32
EPOCH = "cd" * 16


def sample():
    return SimpleNamespace(
        operation=OBSERVED, component_key="equipment:" + SENSOR,
        sequence=41, source_event_id="35",
        before={"setting": "closed"},
        after={"setting": "open", "link_id": LINK,
               "sensor_revision": 2, "cable_revision": 1,
               "evidence_id": "operator-checked"},
        actor_dbref=None, request_id=None, game_time=1080.0,
    )


class NetworkAccessPolicyTests(unittest.TestCase):
    def test_real_contact_capsule_is_anonymous_and_provenance_preserving(self):
        packet = capture(sample())
        self.assertEqual(packet["sensor_event_id"], "41")
        self.assertEqual(packet["physical_hatch_event_id"], "35")
        self.assertEqual(packet["setting_after"], "open")
        self.assertNotIn("actor_dbref", packet)
        self.assertNotIn("request_id", packet)
        wrapped = SimpleNamespace(
            sequence=45, operation=DELIVERED, component_key=PRINCIPAL,
            after={**packet, "epoch": EPOCH}, source_event_id="41",
            actor_dbref=None, request_id=None, game_time=1080.0,
        )
        final = present_delivery(wrapped, epoch=EPOCH)
        self.assertEqual(final["delivery_event_id"], "ox-net-45")
        self.assertEqual(final["source_time"], 1080.0)
        self.assertEqual(final["reader_id"], SENSOR)

    def test_reject_ordinary_traversal_nontransition_or_spoofed_identity(self):
        e = sample()
        e.operation = "crew_traverse"
        with self.assertRaises(NetworkAccessError):
            capture(e)
        e.operation = OBSERVED
        e.after["setting"] = "closed"
        with self.assertRaises(NetworkAccessError):
            capture(e)
        e.after["setting"] = "open"
        e.actor_dbref = "#100"
        with self.assertRaises(NetworkAccessError):
            capture(e)
        e.actor_dbref = None
        e.source_event_id = "unproven"
        with self.assertRaises(NetworkAccessError):
            capture(e)

    def test_token_cannot_change_account_event_or_enrollment(self):
        tok = seal(SECRET, 7, EPOCH, 405)
        self.assertEqual(unseal(tok, SECRET, 7, EPOCH), 405)
        for pk, epoch, token in (
            (8, EPOCH, tok),
            (7, "ef" * 16, tok),
            (7, EPOCH, tok[:-1] + ("0" if tok[-1] != "0" else "1")),
            (7, EPOCH, "v1.196." + tok.split(".")[-1]),
        ):
            with self.assertRaises(NetworkAccessError):
                unseal(token, SECRET, pk, epoch)

    def test_delivery_refuses_leaked_identity_or_wrong_principal(self):
        p = capture(sample())
        capsule = SimpleNamespace(
            sequence=50, operation=DELIVERED, component_key=PRINCIPAL,
            after={**p, "epoch": EPOCH}, source_event_id="41",
            actor_dbref=None, request_id=None,
        )
        capsule.after["actor_dbref"] = "#44"
        with self.assertRaises(NetworkAccessError):
            present_delivery(capsule, epoch=EPOCH)
        del capsule.after["actor_dbref"]
        capsule.component_key = "principal:other"
        with self.assertRaises(NetworkAccessError):
            present_delivery(capsule, epoch=EPOCH)
        capsule.component_key = PRINCIPAL
        with self.assertRaises(NetworkAccessError):
            present_delivery(capsule, epoch="ef" * 16)

    def test_page_limits_fail_closed(self):
        for limit in (False, 0, -1, 33, 1000000, 1.5, "32"):
            with self.assertRaises(NetworkAccessError):
                valid_limit(limit)
        self.assertEqual(valid_limit(32), 32)


class CoolingAdmissionTests(unittest.TestCase):
    def test_rejector_failure_uses_real_buffer_and_preserves_sibling(self):
        from types import SimpleNamespace
        from world.ship_mind_support import initial_cooling_ledger, load_support

        support = load_support()
        pod = support["cooling_islands"][0]
        ids = set(pod["machines"])
        bank = initial_cooling_ledger(support)
        store = bank["units"][pod["independent_buffer_id"]]
        store.update(surveyed=True, capacity_kj=720, free_kj=720,
                     initial_free_kj=720)
        rows = {
            "equipment:" + name: SimpleNamespace(condition="serviceable")
            for name in (
                pod["heat_rejector_id"], pod["independent_buffer_id"],
                *pod["individual_cold_plates"],
            )
        }
        rows["equipment:" + pod["heat_rejector_id"]].condition = "failed"
        heat = {name: 2.0 for name in ids}
        self.assertEqual(
            thermally_ready(support, bank, rows, {}, ids, heat), ids)
        # One broken plate must not kill the healthy machine beside it.
        rows["equipment:" + pod["individual_cold_plates"][0]].condition = "failed"
        result = thermally_ready(support, bank, rows, {}, ids, heat)
        self.assertEqual(result, ids - {pod["machines"][0]})
        # Stored headroom is genuinely finite.
        store["free_kj"] = 0.0
        store["initial_free_kj"] = 0.0
        self.assertFalse(thermally_ready(
            support, bank, rows, {}, ids, heat))

    def test_measured_rejection_can_serve_when_buffer_is_exhausted(self):
        from types import SimpleNamespace
        from world.ship_mind_support import initial_cooling_ledger, load_support

        support = load_support()
        pod = support["cooling_islands"][0]
        ids = set(pod["machines"])
        ledger = initial_cooling_ledger(support)
        store = ledger["units"][pod["independent_buffer_id"]]
        store.update(surveyed=True, capacity_kj=720, free_kj=0.0,
                     initial_free_kj=0.0)
        rows = {
            "equipment:" + name: SimpleNamespace(condition="serviceable")
            for name in (
                pod["heat_rejector_id"], pod["independent_buffer_id"],
                *pod["individual_cold_plates"],
            )
        }
        receipt = {pod["id"]: {"generated_kj": 30.0,
                                "rejected_kj": 30.0}}
        heat = {name: 2.0 for name in ids}
        self.assertEqual(
            thermally_ready(support, ledger, rows, receipt, ids, heat), ids)
        rows["equipment:" + pod["heat_rejector_id"]].condition = "failed"
        self.assertFalse(thermally_ready(
            support, ledger, rows, receipt, ids, heat))
