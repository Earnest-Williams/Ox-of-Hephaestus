"""G3e-3: evidence-first autonomy, without requiring disagreement.

No Evennia internals or operator-only cause enter this handler. Four existing
specialists may independently pursue a known unknown after a verified first
report. Lin receives world-verified instrument reports and may form a tentative
conclusion even after declining an initial diagnosis. The old G3e-2 workflow
remains available for controlled A/B observations.
"""
from __future__ import annotations

from collections import Counter

from ox_ai.agents.crew import CommandOption
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.investigation_followup import (
    CAUSES, SPECIALISTS, STATIONS, FollowupInvestigation, _case_id, _own,
)
from ox_ai.runtime.work_steps import WorkStepLedger


class IndependentInquiry(FollowupInvestigation):
    """Per-character event-driven inquiry on the original five-person ship."""

    async def _specialist_question(self, role: str) -> bool:
        events = await self.s.read_inbox(role)
        notice = events.latest("anomaly_notice")
        if notice is None:
            return False
        case_id = _case_id(notice)
        first = self.s.state.get("g3e_investigations", {}).get(role)
        if (not isinstance(first, dict)
                or first.get("actor") != self.s.ids[role]
                or first.get("case_id") != case_id
                or not first.get("done") or not first.get("selected")):
            return False
        # This character knows a question exists because they personally
        # received the symptom notice, not because the operator knows its cause.
        fact = "anomaly." + case_id + ".cause"
        self.s.epistemics[role].ask(
            fact, reason="Firsthand analyzer discrepancy remains unexplained",
        )
        explanations = [
            e for e in _own(events, kind="anomaly_hypothesis_shared", case_id=case_id)
            if e["data"].get("hypothesis") in CAUSES
        ]
        bridge_claim = explanations[-1]["data"]["hypothesis"] if explanations else None
        record = self.records.get(role)
        if record is not None and (
            record.get("actor") != self.s.ids[role]
            or record.get("case_id") != case_id
            or record.get("initial_hypothesis") != bridge_claim
        ):
            raise PermissionError("Foreign, stale or reassigned inquiry checkpoint")
        indicator, tested = STATIONS[role][1:]
        if record is None:
            # Research is a genuine independent choice, not mandatory
            # disagreement. A specialist can also expressly defer.
            choices = [
                CommandOption(
                    f"Independently test {indicator}; the cause is still "
                    "unknown and no challenge to Lin is necessary",
                    "question",
                ),
            ]
            if bridge_claim:
                choices.extend(
                    CommandOption(f"Challenge Lin with alternative {cause}", "challenge:" + cause)
                    for cause in CAUSES if cause != bridge_claim
                )
            choices.append(CommandOption("Do no more investigation at present", "defer"))
            decision = await self._choose(role, choices)
            if decision not in ("question", "defer") and not (
                decision.startswith("challenge:") and bridge_claim
                and decision.partition(":")[2] in CAUSES
                and decision.partition(":")[2] != bridge_claim
            ):
                raise PermissionError("Unrecognized independent inquiry choice")
            record = {
                "actor": self.s.ids[role], "case_id": case_id,
                "initial_hypothesis": bridge_claim,
                "inquiry_choice": decision, "done": False,
            }
            self.records[role] = record
            self._checkpoint()
        if record.get("done"):
            return False
        decision = record["inquiry_choice"]
        if decision == "defer":
            record["done"] = True
            self._checkpoint()
            return True
        if decision == "question":
            verb = "anomaly_question"
            args = {"case_id": case_id}
            expected_kind = "anomaly_question_recorded"
        else:
            proposed = decision.partition(":")[2]
            if (not bridge_claim or not decision.startswith("challenge:")
                    or proposed not in CAUSES or proposed == bridge_claim):
                raise PermissionError("Invalid persisted case challenge")
            verb = "anomaly_challenge"
            args = {"case_id": case_id, "hypothesis": proposed}
            expected_kind = "anomaly_challenge_recorded"

        destination, expected_indicator, tested_hypothesis = STATIONS[role]
        await self.s.ensure_station(role, destination)
        client = self.s.clients[role]
        port = DurableEvenniaPort(client)
        initiated = await self._ledger(record).run(
            "initiate", role, verb, "ship", port, arguments=args,
        )
        if not initiated.source_event_id:
            raise RuntimeError("World did not authorize an investigation")
        own_events = await self.s.read_inbox(role)
        if not any(e["event_id"] == initiated.source_event_id
                   for e in _own(own_events, kind=expected_kind, case_id=case_id)):
            raise RuntimeError("Independently initiated inquiry lacks world provenance")
        if decision == "question":
            self.s.epistemics[role].ask(
                fact, reason="Independent control reading required to investigate discrepancy",
            )
        else:
            self.s.epistemics[role].believe(
                fact, proposed, confidence=0.4,
                basis="Challenged hypothesis " + initiated.source_event_id,
            )
        self._checkpoint()

        if "report" not in record.get("work_steps", {}):
            await client.send_line("oxprobe " + case_id)
            text = await client.expect_text("OX_ANOMALY_PROBE " + case_id + " ", timeout=12)
            self.s.brains[role].observe_local(
                "Firsthand independent control measurement " + expected_indicator, text,
            )
        own_events = await self.s.read_inbox(role)
        samples = _own(own_events, kind="anomaly_probe_sampled", case_id=case_id)
        if not samples:
            raise RuntimeError("Follow-up result did not reach its examining character")
        sample = samples[-1]
        if (sample["recipient_dbref"] != self.s.ids[role]
                or sample["data"].get("indicator") != expected_indicator
                or sample["data"].get("tested_hypothesis") != tested_hypothesis
                or sample["data"].get("reading") not in ("supports", "does_not_support")):
            raise PermissionError("Unaddressed or malformed probe evidence")
        self.s.epistemics[role].observe_verified(
            "anomaly." + case_id + ".probe", sample["data"]["reading"],
            evidence_id=sample["event_id"], at=float(sample["game_time"]),
            source="world_event",
        )
        self._checkpoint()
        result = await self._ledger(record).run(
            "report", role, "anomaly_probe_report", "ship", port,
            arguments={"case_id": case_id},
        )
        if not result.source_event_id:
            raise RuntimeError("No world-receipted follow-up measurement")
        own_events = await self.s.read_inbox(role)
        if not any(e["event_id"] == result.source_event_id
                   for e in _own(own_events, kind="anomaly_probe_report_recorded", case_id=case_id)):
            raise RuntimeError("Follow-up test report has no firsthand source")

        if "post_test_choice" not in record:
            # Evidence alters the menu context; it never certifies a cause.
            # Deferral remains an offered and genuine action.
            candidates = list(CAUSES)
            candidates.remove(tested_hypothesis)
            if sample["data"]["reading"] == "supports":
                candidates.insert(0, tested_hypothesis)
            else:
                candidates.append(tested_hypothesis)
            record["post_test_choice"] = await self._choose(
                role,
                [
                    *[CommandOption(
                        f"After {expected_indicator} {sample['data']['reading']}, "
                        f"offer tentative hypothesis {cause}", cause,
                    ) for cause in candidates],
                    CommandOption(
                        "Report instrument result without asserting a cause", "defer",
                    ),
                ],
            )
            self._checkpoint()
        opinion = record["post_test_choice"]
        if opinion == "defer":
            record["done"] = True
            self._checkpoint()
            return True
        if opinion not in CAUSES:
            raise PermissionError("Unrecognized recovered post-test hypothesis")
        proposed = await self._ledger(record).run(
            "position", role, "anomaly_reconsider", "ship", port,
            arguments={"case_id": case_id, "hypothesis": opinion},
        )
        if not proposed.source_event_id:
            raise RuntimeError("No world provenance for post-test hypothesis")
        own_events = await self.s.read_inbox(role)
        if not any(e["event_id"] == proposed.source_event_id
                   for e in _own(own_events, kind="anomaly_reconsideration_recorded", case_id=case_id)):
            raise RuntimeError("Missing personally addressed hypothesis receipt")
        self.s.epistemics[role].believe(
            fact, opinion, confidence=0.45,
            basis="Post-test, provisional " + proposed.source_event_id,
        )
        record["done"] = True
        self._checkpoint()
        return True

    async def _bridge_question(self) -> bool:
        own = await self.s.read_inbox("lin")
        first = self.s.state.get("g3e_investigations", {}).get("lin")
        if (not isinstance(first, dict) or not first.get("done")
                or not first.get("selected") or not first.get("assessment_done")
                or first.get("actor") != self.s.ids["lin"]):
            return False
        case_id = first.get("case_id")
        if not isinstance(case_id, str) or len(case_id) != 32:
            raise PermissionError("Invalid bridge case identity")
        original = first.get("hypothesis")
        if original not in (*CAUSES, "defer"):
            raise PermissionError("No verified initial bridge decision")
        if original == "defer":
            self.s.epistemics["lin"].ask(
                "anomaly." + case_id + ".cause",
                reason="Original world symptom could not yet be explained",
            )
        tests = _own(own, kind="anomaly_probe_report", case_id=case_id)
        # These are addressed world events with firsthand sample provenance.
        # Other characters' beliefs and private memories are not accessed.
        latest = {e["sender_dbref"]: e for e in tests}
        engineer = {self.s.ids[r] for r in ("ari", "iona")}
        specialist = {self.s.ids[r] for r in ("mara", "teo")}
        if not set(latest).intersection(engineer) or not set(latest).intersection(specialist):
            return False
        if any(
            e["data"].get("tested_hypothesis") not in CAUSES
            or e["data"].get("reading") not in ("supports", "does_not_support")
            or not isinstance(e["data"].get("sample_event_id"), str)
            for e in latest.values()
        ):
            raise PermissionError("Malformed world-addressed experimental report")
        record = self.records.get("lin")
        if record is not None and (
            record.get("actor") != self.s.ids["lin"]
            or record.get("case_id") != case_id
            or record.get("initial_hypothesis") != (
                original if original in CAUSES else None
            )
        ):
            raise PermissionError("Foreign bridge question checkpoint")
        if record is None:
            counts = Counter(
                (e["data"]["tested_hypothesis"], e["data"]["reading"])
                for e in latest.values()
            )
            candidate = await self._choose(
                "lin", [
                    *[CommandOption(
                        f"Provisional cause {cause}: independent follow-up "
                        f"tests supporting={counts[(cause, 'supports')]}, "
                        f"not-supporting={counts[(cause, 'does_not_support')]}",
                        cause,
                    ) for cause in CAUSES],
                    CommandOption(
                        "Keep cause unknown while retaining all reported measurements",
                        "defer",
                    ),
                ],
            )
            record = {
                "actor": self.s.ids["lin"], "case_id": case_id,
                "initial_hypothesis": original if original in CAUSES else None,
                "post_test_choice": candidate, "done": False,
            }
            self.records["lin"] = record
            self._checkpoint()
        if record.get("done"):
            return False
        position = record["post_test_choice"]
        if position == "defer":
            record["done"] = True
            self._checkpoint()
            return True
        if position not in CAUSES:
            raise PermissionError("Malformed bridge follow-up decision")
        await self.s.ensure_station("lin", "Bridge")
        reassessed = await self._ledger(record).run(
            "reassessment", "lin", "anomaly_reassess", "ship",
            DurableEvenniaPort(self.s.clients["lin"]),
            arguments={"case_id": case_id, "hypothesis": position},
        )
        if not reassessed.source_event_id:
            raise RuntimeError("World did not accept a tentative follow-up explanation")
        own = await self.s.read_inbox("lin")
        if not any(e["event_id"] == reassessed.source_event_id
                   for e in _own(own, kind="anomaly_reassessment_recorded", case_id=case_id)):
            raise RuntimeError("Bridge did not receive its own world reassessment")
        self.s.epistemics["lin"].believe(
            "anomaly." + case_id + ".cause", position,
            confidence=0.5, basis="Independent investigations " + reassessed.source_event_id,
        )
        record["done"] = True
        self._checkpoint()
        return True

    async def advance(self) -> bool:
        for role in SPECIALISTS:
            if await self._specialist_question(role):
                return True
        return await self._bridge_question()
