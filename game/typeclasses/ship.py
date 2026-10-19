"""Persistent, mechanically authoritative objects in the tiny Ox ship.

Concordia must eventually issue normal character commands against these
objects. It cannot alter pump Attributes directly or claim repair via prose.
"""

from __future__ import annotations

from django.db import transaction

from evennia.objects.objects import DefaultCharacter, DefaultObject, DefaultRoom
from evennia.utils import gametime


class ShipRoom(DefaultRoom):
    """A navigable physical compartment with stock Evennia exits."""


class CrewCharacter(DefaultCharacter):
    """A persistent physical shipboard person, not a session-scoped avatar."""

    def at_post_unpuppet(self, account=None, session=None, **kwargs) -> None:
        """Remain in the ship's world when an AI or player session disconnects.

        Stock DefaultCharacter stows an unpuppeted body in location=None.
        That would effectively make a ship's crew vanish whenever an external
        Concordia handler restarts. Shipboard people instead persist at
        their last actual world location; normal per-account puppet locks,
        authenticated commands and world checks still govern control.
        """
        if self.location is not None:
            self.db.prelogout_location = self.location


class FixedFixture(DefaultObject):
    """Equipment attached to a compartment and not collectable as an item."""

    def at_object_creation(self) -> None:
        """Prevent normal pickup of installed fixtures."""
        super().at_object_creation()
        self.locks.add("get:false();drop:false()")

    def at_pre_get(self, getter, **kwargs) -> bool:
        """Reject pickup even when invoked outside the ordinary get command."""
        getter.msg("That fixture is secured to the ship.")
        return False


class CoolingPump(FixedFixture):
    """A deliberately small deterministic coolant-loop state machine."""

    TRANSITIONS = {
        "fault": ("normal", "low_pressure"),
        "isolate": ("low_pressure", "isolated"),
        "repair": ("isolated", "repaired"),
        "commission": ("repaired", "normal"),
    }
    PRESSURE = {
        "normal": "nominal",
        "low_pressure": "below safe operating limits",
        "isolated": "zero; loop isolated",
        "repaired": "zero; awaiting commissioning",
    }

    def at_object_creation(self) -> None:
        """Create authoritative persistent state exactly once."""
        super().at_object_creation()
        self.db.operating_state = "normal"
        self.db.event_seq = 0
        self.db.event_history = []

    @property
    def state(self) -> str:
        """Return the actual game-state machine position."""
        return self.db.operating_state or "normal"

    def readout(self) -> str:
        """Display observations that an observer next to the pump can obtain."""
        return (
            f"Cooling Pump P-01: {self.state.replace('_', ' ').upper()}\n"
            f"Loop pressure: {self.PRESSURE[self.state]}."
        )

    def get_display_desc(self, looker, **kwargs) -> str:
        """Provide a live inspection when someone looks at the pump."""
        return f"{self.db.desc or ''}\n{self.readout()}"

    def _is_engineer_here(self, actor) -> bool:
        """Require physical access and a game-authorised engineering role."""
        from world.bootstrap import find_fixture
        roster = find_fixture("roster-board")
        active = getattr(roster.db, "ox_active_engineer", None) if roster else None
        if (active is not None and actor and actor.dbref != active
                and not actor.check_permstring("Developer")):
            return False
        return bool(
            actor
            and actor.location == self.location
            and (
                actor.db.crew_role in ("watch_engineer", "chief_engineer")
                or actor.check_permstring("Developer")
            )
        )

    def _transition(self, operation: str, actor=None) -> tuple[bool, str]:
        """Apply a validated change, recording its factual outcome once."""
        expected, new_state = self.TRANSITIONS[operation]
        before = self.state
        if before != expected:
            return False, (
                f"Cannot {operation} P-01 while it is {before.replace('_', ' ')}."
            )

        if operation == "commission" and self.db.ox_chief_gate and not self.db.ox_chief_released:
            return False, "Chief safety release required before commissioning."

        # An unattended fault is a world event, not an NPC command; the other
        # operations must be performed by a local authorised character.
        if operation == "fault":
            if actor is not None and not actor.check_permstring("Developer"):
                return False, "Only an operator can inject a test fault."
        elif not self._is_engineer_here(actor):
            return False, "Engineering access and presence at P-01 are required."

        self.db.operating_state = new_state
        serial = int(self.db.event_seq or 0) + 1
        self.db.event_seq = serial
        history = list(self.db.event_history or [])
        history.append(
            {
                "event_id": f"p01-{serial:04d}",
                "operation": operation,
                "before": before,
                "after": new_state,
                "actor_dbref": actor.dbref if actor else None,
                "game_time": float(gametime.gametime(absolute=True)),
            }
        )
        self.db.event_history = history
        if self.location:
            # An aborted database transition must not announce a physical
            # change that never committed to world truth.
            room = self.location
            notice = f"P-01 changes state: {before} -> {new_state}."
            transaction.on_commit(
                lambda: room.msg_contents(notice, exclude=actor)
            )
        return True, f"P-01: {before.replace('_', ' ')} -> {new_state.replace('_', ' ')}."

    @transaction.atomic
    def inject_fault(self, actor=None) -> tuple[bool, str]:
        """Simulate a fault; only the system or a developer can introduce it."""
        # Evennia's cached Attribute models outlive a rolled-back Django
        # transaction. Preserve the pre-fault values in memory too if the
        # alarm writer fails AFTER this local physical transition.
        prior_state = self.db.operating_state
        prior_sequence = int(self.db.event_seq or 0)
        prior_history = list(self.db.event_history or [])
        succeeded, message = self._transition("fault", actor=actor)
        if succeeded and self.db.ox_chief_gate:
            from world.live_crew import fault_alarm
            try:
                fault_alarm(self)
            except BaseException:
                self.db.operating_state = prior_state
                self.db.event_seq = prior_sequence
                self.db.event_history = prior_history
                raise
        return succeeded, message

    def isolate(self, actor) -> tuple[bool, str]:
        """Isolate a low-pressure pump in person."""
        return self._transition("isolate", actor=actor)

    def repair(self, actor) -> tuple[bool, str]:
        """Repair only an isolated pump in person."""
        return self._transition("repair", actor=actor)

    def commission(self, actor) -> tuple[bool, str]:
        """Return an already repaired loop to normal service."""
        return self._transition("commission", actor=actor)


    def durable_action(self, request_id: str, operation: str, actor) -> dict:
        """Commit an actor-bound physical operation and its receipt atomically."""
        import re
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("Action ID must be 32 lowercase hex digits")
        if operation not in ("isolate", "repair", "commission"):
            raise ValueError("Invalid physical operation")
        if actor is None:
            raise PermissionError("Physical commands require a character")
        with transaction.atomic():
            ledger = dict(self.db.ox_action_receipts or {})
            previous = ledger.get(request_id)
            if previous is not None:
                if (previous["actor_dbref"], previous["operation"]) != (actor.dbref, operation):
                    raise PermissionError("Request ID already bound to different work")
                return dict(previous)
            succeeded, _message = self._transition(operation, actor=actor)
            history = list(self.db.event_history or [])
            receipt = {
                "request_id": request_id, "actor_dbref": actor.dbref,
                "operation": operation,
                "status": "succeeded" if succeeded else "failed",
                "reason": "transition_applied" if succeeded else "world_refused",
                "source_event_id": history[-1]["event_id"] if succeeded else None,
                "state": self.state if succeeded else None,
                "game_time": float(gametime.gametime(absolute=True)),
            }
            ledger[request_id] = receipt
            self.db.ox_action_receipts = ledger
            return dict(receipt)

    def durable_receipt(self, request_id: str, actor) -> dict:
        """Read only the caller's own recorded action, with no remote state leak."""
        import re
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("Action ID must be 32 lowercase hex digits")
        if actor is None:
            raise PermissionError("A character identity is required")
        stored = dict(self.db.ox_action_receipts or {}).get(request_id)
        if stored is None or stored["actor_dbref"] != actor.dbref:
            return {"request_id": request_id, "actor_dbref": actor.dbref,
                    "status": "unknown", "reason": "no_authorised_receipt",
                    "source_event_id": None}
        return dict(stored)


class StatusConsole(FixedFixture):
    """Bridge-mounted telemetry sourced from the authoritative pump object."""

    def readout(self) -> str:
        """Show only information deliberately exposed by bridge telemetry."""
        from world.bootstrap import find_fixture

        pump = find_fixture("pump-p01")
        if pump is None:
            return "No telemetry from cooling loop P-01."
        return f"BRIDGE COOLING TELEMETRY\n{pump.readout()}"

    def get_display_desc(self, looker, **kwargs) -> str:
        """Present current measurements rather than a static description."""
        return f"{self.db.desc or ''}\n{self.readout()}"


class RosterBoard(FixedFixture):
    """Posted work assignments; this is not a running duty scheduler."""

    def readout(self) -> str:
        """Show assigned watches without revealing crew-private memories."""
        from world.bootstrap import CREW_MARKERS, find_fixture

        rows = ["SHIPBOARD WATCH ROSTER (assignment metadata, not live clock)"]
        for marker in CREW_MARKERS:
            member = find_fixture(marker)
            if member:
                rows.append(
                    f"{member.key}: {member.db.duty_title} "
                    f"[{member.db.watch_window}]"
                )
                if self.db.ox_active_engineer == member.dbref:
                    rows.append(f"Active engineering watch: {member.key}")
        return "\n".join(rows)

    def get_display_desc(self, looker, **kwargs) -> str:
        """Show assignments when looking at the board."""
        return self.readout()
