"""G3e-2: independent specialist challenges and world-grounded reconsideration.

No import of world internals, world DB, hidden cause, or operator-only audit.
Five ordinary authenticated characters navigate, sample, share disagreement,
and choose new hypotheses using only their own world-addressed messages.
A world WorkReceipt, not an inference response, establishes every report.
"""
from __future__ import annotations

from collections import Counter
import re

from ox_ai.agents.crew import CommandOption
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.work_steps import WorkStepLedger

CAUSES = ("cargo_vapors", "scrubber_bypass", "bus_interference")
SPECIALISTS = ("ari", "iona", "mara", "teo")
STATIONS = {
    "ari": ("Engineering", "bus_reference", "bus_interference"),
    "iona": ("Engineering", "thermal_reference", "scrubber_bypass"),
    "mara": ("Cargo Hold", "cargo_blank", "cargo_vapors"),
    "teo": ("Environmental Plant", "scrubber_differential", "scrubber_bypass"),
}
_CASE_ID = re.compile(r"[0-9a-f]{32}")


def _case_id(source: dict) -> str:
    cid = source.get("data", {}).get("case_id")
    if not isinstance(cid, str) or _CASE_ID.fullmatch(cid) is None:
        raise PermissionError("Malformed world investigation identity")
    return cid


def _own(events: list[dict], *, kind: str, case_id: str) -> list[dict]:
    return [
        e for e in events
        if e["kind"] == kind and e["data"].get("case_id") == case_id
    ]


class FollowupInvestigation:
    """Scoped case process, not a generalized investigation agent."""

    def __init__(self, supervisor):
        self.s = supervisor
        state = supervisor.state.setdefault("g3e_followup", {})
        if not isinstance(state, dict) or any(role not in supervisor.ids for role in state):
            raise PermissionError("Unrecognized or cross-character investigation state")
        self.records = state

    def _checkpoint(self):
        self.s.checkpoint()

    async def _choose(self, role: str, choices: list[CommandOption]):
        choice = await self.s.cognition.decide(
            role, self.s.brains[role].agent, choices,
        )
        # Selection is a *local hypothesis*, never a physical effect.
        self.s.brains[role].selected_procedure(choice)
        return choice.verb

    def _ledger(self, record):
        return WorkStepLedger(
            record, self._checkpoint, character_ids=self.s.ids,
        )

    async def _specialist(self, role: str) -> bool:
        messages = await self.s.read_inbox(role)
        explanations = [e for e in messages if e["kind"] == "anomaly_hypothesis_shared"]
        if not explanations:
            return False
        initial = explanations[-1]
        case_id = _case_id(initial)
        hypothesis = initial["data"].get("hypothesis")
        if hypothesis not in CAUSES:
            raise PermissionError("Invalid originating world hypothesis")
        first_stage = self.s.state.get("g3e_investigations", {}).get(role)
        if (not isinstance(first_stage, dict)
                or first_stage.get("actor") != self.s.ids[role]
                or first_stage.get("case_id") != case_id
                or not first_stage.get("done")):
            return False
        record = self.records.get(role)
        if record is not None and (
            record.get("actor") != self.s.ids[role]
            or record.get("case_id") != case_id
            or record.get("initial_hypothesis") != hypothesis
        ):
            raise PermissionError("Old private follow-up record belongs to another case")
        if record is None:
            # Options are alternatives, not world facts. A hosted model may
            # disagree, or defer entirely; MockModel only tests the protocol.
            other_causes = [x for x in CAUSES if x != hypothesis]
            option = await self._choose(
                role, [
                    *[CommandOption("Challenge bridge with hypothesis " + x, x)
                      for x in other_causes],
                    CommandOption("No evidence for a challenge; defer", "defer"),
                ],
            )
            record = {
                "actor": self.s.ids[role], "case_id": case_id,
                "initial_hypothesis": hypothesis, "challenge_choice": option,
                "done": False,
            }
            self.records[role] = record
            self._checkpoint()
        if record.get("done"):
            return False
        if record["challenge_choice"] == "defer":
            record["done"] = True
            self._checkpoint()
            return True
        if record["challenge_choice"] not in CAUSES:
            raise PermissionError("Invalid recovered challenge")
        destination, expected_indicator, tested_hypothesis = STATIONS[role]
        # First-hand physical position is world-checked both when sampling
        # and when filing every global work receipt.
        await self.s.ensure_station(role, destination)
        client = self.s.clients[role]
        port = DurableEvenniaPort(client)
        challenged = await self._ledger(record).run(
            "challenge", role, "anomaly_challenge", "ship", port,
            arguments={"case_id": case_id,
                       "hypothesis": record["challenge_choice"]},
        )
        if not challenged.source_event_id:
            raise RuntimeError("World gave no proof of challenge")
        messages = await self.s.read_inbox(role)
        if not any(
            e["event_id"] == challenged.source_event_id
            and e["kind"] == "anomaly_challenge_recorded"
            for e in _own(messages, kind="anomaly_challenge_recorded", case_id=case_id)
        ):
            raise RuntimeError("Author never received their world-recorded challenge")
        self.s.epistemics[role].believe(
            "anomaly." + case_id + ".cause", record["challenge_choice"],
            confidence=0.4, basis="Hypothesis challenged via " + challenged.source_event_id,
        )
        self._checkpoint()

        # Real sampling is repeat-safe even after a lost textual response.
        # World persists an instrument reading and its own event ID.
        if "probe_report" not in record.get("work_steps", {}):
            await client.send_line("oxprobe " + case_id)
            text = await client.expect_text("OX_ANOMALY_PROBE " + case_id + " ", timeout=12)
            self.s.brains[role].observe_local(
                "Firsthand controlled diagnostic " + expected_indicator, text,
            )
        own_events = await self.s.read_inbox(role)
        samples = _own(own_events, kind="anomaly_probe_sampled", case_id=case_id)
        if not samples:
            raise RuntimeError("Character lacks addressed experimental reading")
        sample = samples[-1]
        if (sample["recipient_dbref"] != self.s.ids[role]
                or sample["data"].get("indicator") != expected_indicator
                or sample["data"].get("tested_hypothesis") != tested_hypothesis
                or sample["data"].get("reading") not in ("supports", "does_not_support")):
            raise PermissionError("Foreign or malformed experimental reading")
        self.s.epistemics[role].observe_verified(
            "anomaly." + case_id + ".probe", sample["data"]["reading"],
            evidence_id=sample["event_id"], at=float(sample["game_time"]),
            source="world_event",
        )
        self._checkpoint()

        reported = await self._ledger(record).run(
            "probe_report", role, "anomaly_probe_report", "ship", port,
            arguments={"case_id": case_id},
        )
        if not reported.source_event_id:
            raise RuntimeError("No world proof of follow-up experiment report")
        own_events = await self.s.read_inbox(role)
        if not any(
            e["event_id"] == reported.source_event_id
            for e in _own(own_events, kind="anomaly_probe_report_recorded", case_id=case_id)
        ):
            raise RuntimeError("World did not send experiment report proof")

        # Evidence influences the order of suggestions, never an enforced
        # answer: 'does_not_support' is not the same as falsification.
        # No hidden cause, oracle confidence, or other actor's memory here.
        if "reconsider_choice" not in record:
            candidates = list(CAUSES)
            if sample["data"]["reading"] == "supports":
                candidates.remove(tested_hypothesis)
                candidates.insert(0, tested_hypothesis)
            else:
                candidates.remove(tested_hypothesis)
                candidates.append(tested_hypothesis)
            record["reconsider_choice"] = await self._choose(
                role, [
                    *[CommandOption(
                        "After " + expected_indicator + " "
                        + sample["data"]["reading"] + ", favor " + x, x,
                    ) for x in candidates],
                    CommandOption("Defer opinion after inconclusive evidence", "defer"),
                ],
            )
            self._checkpoint()
        position = record["reconsider_choice"]
        if position == "defer":
            record["done"] = True
            self._checkpoint()
            return True
        if position not in CAUSES:
            raise PermissionError("Invalid recovered specialist position")
        revised = await self._ledger(record).run(
            "reconsider", role, "anomaly_reconsider", "ship", port,
            arguments={"case_id": case_id, "hypothesis": position},
        )
        if not revised.source_event_id:
            raise RuntimeError("Unproven world reconsideration")
        updated_events = await self.s.read_inbox(role)
        if not any(
            e["event_id"] == revised.source_event_id
            for e in _own(updated_events, kind="anomaly_reconsideration_recorded", case_id=case_id)
        ):
            raise RuntimeError("No individually addressed reconsideration proof")
        self.s.epistemics[role].believe(
            "anomaly." + case_id + ".cause", position,
            confidence=0.45, basis="Post-experiment view " + revised.source_event_id,
        )
        record["done"] = True
        self._checkpoint()
        return True

    async def _bridge(self) -> bool:
        own = await self.s.read_inbox("lin")
        first_stage = self.s.state.get("g3e_investigations", {}).get("lin")
        if (not isinstance(first_stage, dict) or not first_stage.get("done")
                or first_stage.get("actor") != self.s.ids["lin"]):
            return False
        case_id = first_stage.get("case_id")
        if not isinstance(case_id, str) or _CASE_ID.fullmatch(case_id) is None:
            raise PermissionError("Invalid case in bridge checkpoint")
        if "hypothesis" not in first_stage or first_stage["hypothesis"] not in CAUSES:
            # Earlier first-phase deferral means there is no bridge theory yet.
            return False
        reconsidered = _own(own, kind="anomaly_crew_reconsidered", case_id=case_id)
        reported = _own(own, kind="anomaly_probe_report", case_id=case_id)
        eng = {self.s.ids[r] for r in ("ari", "iona")}
        specialist = {self.s.ids[r] for r in ("mara", "teo")}
        senders = {e["sender_dbref"] for e in reconsidered}
        if not senders.intersection(eng) or not senders.intersection(specialist):
            return False
        if not {e["sender_dbref"] for e in reported}.issuperset(senders):
            return False
        record = self.records.get("lin")
        if record is not None and (
            record.get("actor") != self.s.ids["lin"]
            or record.get("case_id") != case_id
            or record.get("initial_hypothesis") != first_stage["hypothesis"]
        ):
            raise PermissionError("Foreign bridge reassessment checkpoint")
        if record is None:
            # Count independent, world-addressed claims; these are testimony,
            # not votes that can turn a theory into canonical physics.
            latest = {e["sender_dbref"]: e["data"].get("hypothesis")
                      for e in reconsidered}
            if any(x not in CAUSES for x in latest.values()):
                raise PermissionError("Malformed authenticated specialist view")
            votes = Counter(latest.values())
            order = sorted(CAUSES, key=lambda x: (-votes[x], x))
            candidate = await self._choose(
                "lin", [
                    *[CommandOption(
                        f"Provisional reassessment: {x} ({votes[x]} independent views)", x,
                    ) for x in order],
                    CommandOption("Evidence insufficient; defer reassessment", "defer"),
                ],
            )
            record = {
                "actor": self.s.ids["lin"], "case_id": case_id,
                "initial_hypothesis": first_stage["hypothesis"],
                "reconsider_choice": candidate, "done": False,
            }
            self.records["lin"] = record
            self._checkpoint()
        if record.get("done"):
            return False
        hypothesis = record["reconsider_choice"]
        if hypothesis == "defer":
            record["done"] = True
            self._checkpoint()
            return True
        if hypothesis not in CAUSES:
            raise PermissionError("Invalid recovered bridge hypothesis")
        await self.s.ensure_station("lin", "Bridge")
        result = await self._ledger(record).run(
            "reassessment", "lin", "anomaly_reassess", "ship",
            DurableEvenniaPort(self.s.clients["lin"]),
            arguments={"case_id": case_id, "hypothesis": hypothesis},
        )
        if not result.source_event_id:
            raise RuntimeError("World withheld bridge reassessment proof")
        own = await self.s.read_inbox("lin")
        if not any(
            e["event_id"] == result.source_event_id
            for e in _own(own, kind="anomaly_reassessment_recorded", case_id=case_id)
        ):
            raise RuntimeError("Bridge reassessment did not reach the bridge")
        self.s.epistemics["lin"].believe(
            "anomaly." + case_id + ".cause", hypothesis,
            confidence=0.5, basis="Independent follow-up " + result.source_event_id,
        )
        record["done"] = True
        self._checkpoint()
        return True

    async def advance(self) -> bool:
        """One person's bounded independent work, or a bridge reassessment."""
        for role in SPECIALISTS:
            if await self._specialist(role):
                return True
        return await self._bridge()
