"""Persistent, mechanically authoritative objects in the tiny Ox ship.

Concordia must eventually issue normal character commands against these
objects. It cannot alter pump Attributes directly or claim repair via prose.
"""

from __future__ import annotations

from evennia.objects.objects import DefaultCharacter, DefaultObject, DefaultRoom
from evennia.utils import gametime


class ShipRoom(DefaultRoom):
    """A navigable physical compartment with stock Evennia exits."""


class CrewCharacter(DefaultCharacter):
    """A crew body in the world, whether or not it has an account or AI."""


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
            self.location.msg_contents(
                f"P-01 changes state: {before} -> {new_state}.",
                exclude=actor,
            )
        return True, f"P-01: {before.replace('_', ' ')} -> {new_state.replace('_', ' ')}."

    def inject_fault(self, actor=None) -> tuple[bool, str]:
        """Simulate a fault; only the system or a developer can introduce it."""
        return self._transition("fault", actor=actor)

    def isolate(self, actor) -> tuple[bool, str]:
        """Isolate a low-pressure pump in person."""
        return self._transition("isolate", actor=actor)

    def repair(self, actor) -> tuple[bool, str]:
        """Repair only an isolated pump in person."""
        return self._transition("repair", actor=actor)

    def commission(self, actor) -> tuple[bool, str]:
        """Return an already repaired loop to normal service."""
        return self._transition("commission", actor=actor)


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
        return "\n".join(rows)

    def get_display_desc(self, looker, **kwargs) -> str:
        """Show assignments when looking at the board."""
        return self.readout()
