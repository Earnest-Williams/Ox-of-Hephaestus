"""Typed global work protocol over ordinary Evennia client framing."""

import unittest
from collections import deque

from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.client import WebPacket
from ox_ai.ports.evennia.durable import DurableEvenniaPort


class FakeClient:
    def __init__(self, character="#44", *, authenticated=True):
        self.character_dbref = character
        self.authenticated = authenticated
        self.commands = []
        self.responses = deque()

    async def send_line(self, command):
        self.commands.append(command)

    async def receive(self):
        return self.responses.popleft()

    def receipt(self, request_id, status="succeeded", event_id="oxevt-v2-0042"):
        self.responses.append(
            WebPacket(
                "ox_receipt",
                (
                    {
                        "request_id": request_id,
                        "actor_dbref": self.character_dbref,
                        "status": status,
                        "reason": "world_accepted",
                        "source_event_id": event_id,
                    },
                ),
                {},
            )
        )


class GlobalWorkPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_lesson_port_accepts_activity_parameters_and_answers_not_learning_claims(self):
        """All three stages serialize safely, without accepting credit or rubric inputs."""
        client = FakeClient()
        port = DurableEvenniaPort(client)
        lesson_id = "d" * 32
        cases = (
            (
                "lesson_offer",
                {"course_id": "mechanical.controlled_comparison.v1", "learner_dbref": "#55"},
                " mechanical.controlled_comparison.v1 #55",
            ),
            ("lesson_begin", {"lesson_id": lesson_id}, " " + lesson_id),
            (
                "lesson_answer",
                {
                    "lesson_id": lesson_id,
                    "supported_factor": "drive_bus",
                    "controlled_factor": "speed",
                },
                " " + lesson_id + " drive_bus speed",
            ),
        )
        for index, (verb, args, suffix) in enumerate(cases):
            request_id = f"{index + 1:032x}"
            client.receipt(request_id)
            result = await port.submit_work(
                ActionRequest(request_id, "#44", verb, "learning", args)
            )
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(client.commands[-1], f"oxwork {request_id} {verb} learning{suffix}")
        for verb, args in (
            (
                "lesson_offer",
                {"course_id": "mechanical.course\nshipfault pump", "learner_dbref": "#55"},
            ),
            (
                "lesson_offer",
                {"course_id": "mechanical.course", "learner_dbref": "#55", "mastery": 100},
            ),
            ("lesson_begin", {"lesson_id": lesson_id, "credit_units": 1}),
            (
                "lesson_answer",
                {
                    "lesson_id": lesson_id,
                    "supported_factor": "drive_bus",
                    "controlled_factor": "invented",
                },
            ),
            ("grant_knowledge", {"mastery": 100}),
        ):
            with self.subTest(verb=verb, args=args), self.assertRaises(ValueError):
                await port.submit_work(ActionRequest("e" * 32, "#44", verb, "learning", args))
        self.assertEqual(len(client.commands), 3)

    async def test_global_equipment_request_and_recovery_uses_same_id(self):
        client = FakeClient()
        port = DurableEvenniaPort(client)
        request_id = "a" * 32
        request = ActionRequest(request_id, "#44", "replace_scrubber", "scrubber")
        client.receipt(request_id)
        first = await port.submit_work(request)
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(client.commands[0], "oxwork " + request_id + " replace scrubber")
        client.receipt(request_id)
        same = await port.reconcile_work(request_id)
        self.assertEqual(client.commands[1], "oxworkreceipt " + request_id)
        self.assertEqual(first.source_event_id, same.source_event_id)

    async def test_private_social_hail_has_only_bounded_typed_arguments(self):
        client = FakeClient()
        port = DurableEvenniaPort(client)
        request_id = "b" * 32
        request = ActionRequest(
            request_id,
            "#44",
            "answer",
            "ship",
            {"hail_id": "hail-0001", "mode": "ack"},
        )
        client.receipt(request_id)
        self.assertEqual((await port.submit_work(request)).status, "succeeded")
        self.assertEqual(
            client.commands,
            [
                "oxwork " + request_id + " answer ship hail-0001 ack",
            ],
        )
        for args in (
            {"hail_id": "hail-0001", "mode": "isolate"},
            {"hail_id": "hail-0001\nshipfault pump", "mode": "ack"},
            {"hail_id": "hail-0001", "mode": "ack", "other": "x"},
        ):
            with self.assertRaises(ValueError):
                await port.submit_work(
                    ActionRequest(
                        "c" * 32,
                        "#44",
                        "answer",
                        "ship",
                        args,
                    )
                )
        self.assertEqual(len(client.commands), 1)

    async def test_identity_and_operation_whitelist_fail_before_submission(self):
        client = FakeClient()
        port = DurableEvenniaPort(client)
        for req in (
            ActionRequest("a" * 32, "#55", "radio", "ship"),
            ActionRequest("a" * 32, "#44", "teleport", "ship"),
            ActionRequest("a" * 32, "#44", "repair_pump", "cargo"),
            ActionRequest("a" * 32, "#44", "radio", "ship", {"x": "y"}),
        ):
            with self.assertRaises((PermissionError, ValueError)):
                await port.submit_work(req)
        self.assertEqual(client.commands, [])
        client.authenticated = False
        with self.assertRaises(PermissionError):
            await port.submit_work(ActionRequest("a" * 32, "#44", "radio", "ship"))
        with self.assertRaises(PermissionError):
            await port.reconcile_work("a" * 32)
