"""G3f captain: persistent command follow-through, not a sixth oracle.

Captains take ownership, select expert assignments, see whether work actually
happened, and reassign/escalate if blocked. Specialists may refuse unsafe
requests; physical permissions never derive from a captain's order. The
handler sees addressed world events, never the world's hidden cause.
"""
from __future__ import annotations

from ox_ai.agents.crew import CommandOption
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.work_steps import WorkStepLedger

ROLES = ("teo", "iona", "ari", "mara")
STATIONS = {
    "teo": "Environmental Plant",
    "iona": "Engineering",
    "ari": "Engineering",
    "mara": "Cargo Hold",
}


class CaptainFollowthrough:
    def __init__(self, supervisor):
        self.s = supervisor
        cases = supervisor.state.setdefault("captain_cases", {})
        if not isinstance(cases, dict):
            raise PermissionError("Invalid captain command checkpoint")
        self.cases = cases

    def _ledger(self, record):
        return WorkStepLedger(
            record, self.s.checkpoint, character_ids=self.s.ids,
        )

    async def _work(self, record, step, role, verb, args):
        result = await self._ledger(record).run(
            step, role, verb, "ship",
            DurableEvenniaPort(self.s.clients[role]),
            arguments=args,
        )
        if result.status != "succeeded" or not result.source_event_id:
            raise RuntimeError("World declined or could not prove captain duty " + verb)
        return result

    async def _decide(self, role, options):
        choice = await self.s.cognition.decide(
            role, self.s.brains[role].agent, options,
        )
        self.s.brains[role].selected_procedure(choice)
        return choice.verb

    async def _assigned(self, ticket_id, record, messages) -> bool:
        order_events = [
            e for e in messages if e["kind"] == "captain_assignment_recorded"
            and e["data"].get("ticket_id") == ticket_id
        ]
        if not order_events:
            return False
        order = order_events[-1]["data"]
        role = order.get("role")
        if role not in ROLES or order.get("kind") not in ("analyzer_anomaly", "atmosphere_alarm"):
            raise PermissionError("Invalid assignment addressed to captain")
        assigned_id = order.get("order_id")
        if not isinstance(assigned_id, str) or len(assigned_id) != 32:
            raise PermissionError("Malformed world-owned assignment")
        responses = [
            e for e in messages if e["kind"] == "captain_order_response"
            and e["data"].get("order_id") == assigned_id
        ]
        if not responses:
            worker_events = await self.s.read_inbox(role)
            order_notices = [
                e for e in worker_events if e["kind"] == "captain_order_received"
                and e["data"].get("ticket_id") == ticket_id
                and e["data"].get("order_id") == assigned_id
                and e["sender_dbref"] == self.s.ids["captain"]
            ]
            if not order_notices:
                raise PermissionError("No authenticated captain assignment reached worker")
            answer_key = "answer:" + assigned_id
            if answer_key not in record.get("decisions", {}):
                decision = await self._decide(role, [
                    CommandOption("Accept and carry out this local authorized follow-up", "accept"),
                    CommandOption("Decline this work as unsuitable", "decline"),
                    CommandOption("Report unable to proceed safely", "blocked"),
                ])
                record.setdefault("decisions", {})[answer_key] = decision
                self.s.checkpoint()
            mode = record["decisions"][answer_key]
            if mode not in ("accept", "decline", "blocked"):
                raise PermissionError("Unrecognized worker follow-up decision")
            await self._work(
                record, answer_key, role, "captain_answer",
                {"ticket_id": ticket_id, "mode": mode},
            )
            return True
        answer = responses[-1]["data"]
        if answer.get("role") != role:
            raise PermissionError("Foreign worker response")
        status = answer.get("status")
        if status in ("declined", "blocked"):
            if record.get("last_reviewed_order") != assigned_id:
                await self._work(
                    record, "review:" + assigned_id, "captain", "captain_review",
                    {"ticket_id": ticket_id},
                )
                record["last_reviewed_order"] = assigned_id
                self.s.checkpoint()
                return True
            return False
        if status != "accepted":
            raise PermissionError("Invalid accepted-work state")
        if order["kind"] == "atmosphere_alarm":
            # The existing Teo A-01 safety/repair machinery has precedence.
            # A captain cannot bypass isolation, spares or local inspection.
            if record.get("last_reviewed_order") == assigned_id:
                return False
            # Wait for an actual world event / clock review before inspecting.
            due = [
                e for e in messages if e["kind"] == "captain_review_due"
                and e["data"].get("ticket_id") == ticket_id
                and e["sequence"] > responses[-1]["sequence"]
            ]
            physically_changed = [
                e for e in messages if e["kind"] == "captain_equipment_change"
                and e["data"].get("ticket_id") == ticket_id
                and e["sequence"] > responses[-1]["sequence"]
            ]
            if not due and not physically_changed:
                return False
            await self._work(
                record, "review:" + assigned_id, "captain", "captain_review",
                {"ticket_id": ticket_id},
            )
            record["last_reviewed_order"] = assigned_id
            self.s.checkpoint()
            return True
        # The same specialist has a real captain order but may never have
        # joined the initial voluntary investigation. They can now gather
        # evidence under their own ordinary local inspection permissions.
        reported = [
            e for e in messages if e["kind"] == "captain_followup_evidence"
            and e["data"].get("order_id") == assigned_id
        ]
        if not reported:
            await self.s.ensure_station(role, STATIONS[role])
            own = await self.s.read_inbox(role)
            if not any(
                e["kind"] == "anomaly_report_recorded"
                and e["data"].get("case_id") == ticket_id
                for e in own
            ):
                await self.s.clients[role].send_line("oxsample " + ticket_id)
                await self.s.clients[role].expect_text(
                    "OX_ANOMALY_SAMPLE " + ticket_id, timeout=12,
                )
                await self._work(
                    record, "initial:" + assigned_id, role,
                    "anomaly_report", {"case_id": ticket_id},
                )
                return True
            if not any(
                e["kind"] in ("anomaly_question_recorded", "anomaly_challenge_recorded")
                and e["data"].get("case_id") == ticket_id
                for e in own
            ):
                await self._work(
                    record, "question:" + assigned_id, role,
                    "anomaly_question", {"case_id": ticket_id},
                )
                return True
            if not any(
                e["kind"] == "anomaly_probe_report_recorded"
                and e["data"].get("case_id") == ticket_id
                for e in own
            ):
                # Probe returns a persisted repeat-safe local measurement;
                # no claimed result is fabricated from the captain's theory.
                await self.s.clients[role].send_line("oxprobe " + ticket_id)
                sample = await self.s.clients[role].expect_text(
                    "OX_ANOMALY_PROBE " + ticket_id + " ", timeout=12,
                )
                self.s.brains[role].observe_local(
                    "Captain-assigned independent evidence", sample,
                )
                await self._work(
                    record, "probe:" + assigned_id, role,
                    "anomaly_probe_report", {"case_id": ticket_id},
                )
                return True
            # A report that predates the assignment does not complete it;
            # the captain must redirect or escalate, never reuse old evidence.
            if record.get("last_reviewed_order") != assigned_id:
                await self._work(
                    record, "review:" + assigned_id, "captain", "captain_review",
                    {"ticket_id": ticket_id},
                )
                record["last_reviewed_order"] = assigned_id
                self.s.checkpoint()
                return True
            return False
        if record.get("last_reviewed_order") != assigned_id:
            await self._work(
                record, "review:" + assigned_id, "captain", "captain_review",
                {"ticket_id": ticket_id},
            )
            record["last_reviewed_order"] = assigned_id
            self.s.checkpoint()
            return True
        return False

    async def advance(self) -> bool:
        messages = await self.s.read_inbox("captain")
        notices = [
            e for e in messages if e["kind"] == "captain_problem_open"
        ]
        if not notices:
            return False
        # Higher priority real-world problems are always considered first.
        for notice in sorted(
            notices, key=lambda e: (-int(e["data"]["priority"]), e["sequence"]),
        ):
            data = notice["data"]
            ticket_id = data.get("ticket_id")
            kind = data.get("kind")
            if (not isinstance(ticket_id, str) or len(ticket_id) != 32
                    or kind not in ("analyzer_anomaly", "atmosphere_alarm")):
                raise PermissionError("Invalid captain's world-issued problem")
            resolved = [
                e for e in messages if e["kind"] == "captain_world_resolved"
                and e["data"].get("ticket_id") == ticket_id
            ]
            if resolved:
                continue
            record = self.cases.get(ticket_id)
            if record is None:
                record = {"captain": self.s.ids["captain"],
                          "ticket_id": ticket_id, "kind": kind,
                          "decisions": {}, "used": [], "last_reviewed_order": None}
                self.cases[ticket_id] = record
                self.s.checkpoint()
            if (record.get("captain") != self.s.ids["captain"]
                    or record.get("ticket_id") != ticket_id
                    or record.get("kind") != kind):
                raise PermissionError("Captain checkpoint rebound to another case")
            if "claim" not in record.get("work_steps", {}):
                await self._work(
                    record, "claim", "captain", "captain_claim",
                    {"ticket_id": ticket_id},
                )
                return True
            if (kind == "atmosphere_alarm"
                    and "initial_review" not in record.get("work_steps", {})):
                # Urgent Teo work may have finished before command could act.
                # Inspect world truth first, rather than ordering redundant
                # procedures against an already restored A-01.
                await self._work(
                    record, "initial_review", "captain", "captain_review",
                    {"ticket_id": ticket_id},
                )
                return True
            order_events = [
                e for e in messages if e["kind"] == "captain_assignment_recorded"
                and e["data"].get("ticket_id") == ticket_id
            ]
            if order_events:
                current = order_events[-1]["data"]
                order_id = current["order_id"]
                # A real report/decline/blocked response is needed before
                # overwriting an active order; the world validates it again.
                finished = [
                    e for e in messages
                    if e["data"].get("order_id") == order_id
                    and (e["kind"] == "captain_followup_evidence"
                         or (e["kind"] == "captain_order_response"
                             and e["data"].get("status") in ("blocked", "declined")))
                ]
                if not finished or record.get("last_reviewed_order") != order_id:
                    if await self._assigned(ticket_id, record, messages):
                        return True
                    if not finished:
                        continue
            # Each new assignment must come from this captain's ordinary
            # world-addressed history, not handler-guessed staff activity.
            used = {
                e["data"]["role"] for e in order_events
                if e["data"].get("role") in ROLES
            }
            # World-addressed prior test receipts prevent a captain from
            # reassigning work that could not produce a fresh measurement.
            used.update(
                e["data"]["role"] for e in messages
                if e["kind"] == "captain_specialist_test_logged"
                and e["data"].get("ticket_id") == ticket_id
                and e["data"].get("role") in ROLES
            )
            candidates = ["teo"] if kind == "atmosphere_alarm" else list(ROLES)
            remaining = [role for role in candidates if role not in used]
            # A world-timed reminder permits re-review after escalation.
            if record.get("waiting_due"):
                due = [
                    e for e in messages if e["kind"] == "captain_review_due"
                    and e["data"].get("ticket_id") == ticket_id
                    and e["sequence"] > record["waiting_due"]
                ]
                if not due:
                    continue
                record.pop("waiting_due")
                self.s.checkpoint()
                await self._work(
                    record, "periodic:" + str(due[-1]["sequence"]),
                    "captain", "captain_review", {"ticket_id": ticket_id},
                )
                return True
            if remaining:
                if "next_role" not in record:
                    options = [
                        CommandOption(
                            "Keep unresolved problem moving: assign " + role
                            + " to take an independently verified next step",
                            "assign:" + role,
                        ) for role in remaining
                    ]
                    options.append(CommandOption(
                        "No safe immediate assignment; escalate open problem",
                        "escalate",
                    ))
                    selected = await self._decide("captain", options)
                    if selected != "escalate" and selected not in {
                        "assign:" + role for role in remaining
                    }:
                        raise PermissionError("Invalid captain assignment proposal")
                    record["next_role"] = selected
                    self.s.checkpoint()
                choice = record["next_role"]
                if choice != "escalate":
                    role = choice.removeprefix("assign:")
                    number = len(order_events) + 1
                    await self._work(
                        record, "assign:" + str(number), "captain",
                        "captain_assign", {"ticket_id": ticket_id, "role": role},
                    )
                    record.pop("next_role", None)
                    self.s.checkpoint()
                    return True
                record.pop("next_role", None)
                self.s.checkpoint()
            # No choice, or all local tests exhausted: an escalation is work,
            # but never a fictional scientific resolution.
            key = "escalate:" + str(len(order_events))
            if key not in record.get("work_steps", {}):
                await self._work(
                    record, key, "captain", "captain_escalate",
                    {"ticket_id": ticket_id},
                )
                self.s.checkpoint()
                return True
            if not record.get("waiting_due"):
                record["waiting_due"] = max(
                    e["sequence"] for e in await self.s.read_inbox("captain")
                )
                self.s.checkpoint()
        return False
