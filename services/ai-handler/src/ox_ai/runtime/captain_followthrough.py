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
        assigned = messages.latest(
            "captain_assignment_recorded", data={"ticket_id": ticket_id},
        )
        if assigned is None:
            return False
        order = assigned["data"]
        role = order.get("role")
        if role not in ROLES or order.get("kind") not in ("analyzer_anomaly", "atmosphere_alarm"):
            raise PermissionError("Invalid assignment addressed to captain")
        assigned_id = order.get("order_id")
        if not isinstance(assigned_id, str) or len(assigned_id) != 32:
            raise PermissionError("Malformed world-owned assignment")
        response = messages.latest(
            "captain_order_response", data={"order_id": assigned_id},
        )
        if response is None:
            worker_events = await self.s.read_inbox(role)
            order_notice = worker_events.latest(
                "captain_order_received",
                data={"ticket_id": ticket_id, "order_id": assigned_id},
            )
            if (order_notice is None
                    or order_notice["sender_dbref"] != self.s.ids["captain"]):
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
        answer = response["data"]
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
            due = messages.latest(
                "captain_review_due", data={"ticket_id": ticket_id},
                after=response["sequence"],
            )
            physically_changed = messages.latest(
                "captain_equipment_change", data={"ticket_id": ticket_id},
                after=response["sequence"],
            )
            if due is None and physically_changed is None:
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
        reported = messages.latest(
            "captain_followup_evidence", data={"order_id": assigned_id},
        )
        if reported is None:
            await self.s.ensure_station(role, STATIONS[role])
            own = await self.s.read_inbox(role)
            if own.latest(
                "anomaly_report_recorded", data={"case_id": ticket_id},
            ) is None:
                await self.s.clients[role].send_line("oxsample " + ticket_id)
                await self.s.clients[role].expect_text(
                    "OX_ANOMALY_SAMPLE " + ticket_id, timeout=12,
                )
                await self._work(
                    record, "initial:" + assigned_id, role,
                    "anomaly_report", {"case_id": ticket_id},
                )
                return True
            if (own.latest(
                    "anomaly_question_recorded", data={"case_id": ticket_id},
                ) is None and own.latest(
                    "anomaly_challenge_recorded", data={"case_id": ticket_id},
                ) is None):
                await self._work(
                    record, "question:" + assigned_id, role,
                    "anomaly_question", {"case_id": ticket_id},
                )
                return True
            if own.latest(
                "anomaly_probe_report_recorded", data={"case_id": ticket_id},
            ) is None:
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
        # Open/closed transition state is derived from this captain's own
        # addressed world events in the same SQLite ingest transaction.
        # Do not rescan all historical resolved tickets each dispatch.
        notices = list(messages.pending("captain"))
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
            # Fact-finding is *optional* and only offered if Evennia
            # reported actual local diagnostic competence. A captain's
            # authority to delegate does not magically confer that skill.
            if "inspection_choice" not in record:
                if data.get("can_personally_inspect") is True:
                    selected = await self._decide("captain", [
                        CommandOption(
                            "Use your qualified diagnostics skill to inspect bridge telemetry",
                            "inspect",
                        ),
                        CommandOption(
                            "Delegate to specialists without your own instrument reading",
                            "delegate",
                        ),
                    ])
                    if selected not in ("inspect", "delegate"):
                        raise PermissionError("Invalid captain fact-finding choice")
                else:
                    selected = "delegate"
                record["inspection_choice"] = selected
                self.s.checkpoint()
            if (record["inspection_choice"] == "inspect"
                    and "captain_inspection" not in record.get("work_steps", {})):
                await self.s.ensure_station("captain", "Bridge")
                observed = await self._work(
                    record, "captain_inspection", "captain", "captain_inspect",
                    {"ticket_id": ticket_id},
                )
                own = await self.s.read_inbox("captain")
                if own.get(
                    observed.source_event_id, kind="captain_firsthand_observation",
                ) is None:
                    raise RuntimeError("Captain's personal observation lacks a world receipt")
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
            order_events = list(messages.select(
                kind="captain_assignment_recorded", data={"ticket_id": ticket_id},
            ))
            if order_events:
                current = order_events[-1]["data"]
                order_id = current["order_id"]
                # A real report/decline/blocked response is needed before
                # overwriting an active order; the world validates it again.
                finished = messages.latest(
                    "captain_followup_evidence", data={"order_id": order_id},
                ) is not None or any(
                    e["data"].get("status") in ("blocked", "declined")
                    for e in messages.select(
                        kind="captain_order_response",
                        data={"order_id": order_id},
                    )
                )
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
                e["data"]["role"] for e in messages.select(
                    kind="captain_specialist_test_logged",
                    data={"ticket_id": ticket_id},
                )
                if e["data"].get("role") in ROLES
            )
            candidates = ["teo"] if kind == "atmosphere_alarm" else list(ROLES)
            remaining = [role for role in candidates if role not in used]
            # A world-timed reminder permits re-review after escalation.
            if record.get("waiting_due"):
                due = messages.latest(
                    "captain_review_due", data={"ticket_id": ticket_id},
                    after=record["waiting_due"],
                )
                if due is None:
                    continue
                record.pop("waiting_due")
                self.s.checkpoint()
                await self._work(
                    record, "periodic:" + str(due["sequence"]),
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
                record["waiting_due"] = (await self.s.read_inbox("captain")).through
                self.s.checkpoint()
        return False
