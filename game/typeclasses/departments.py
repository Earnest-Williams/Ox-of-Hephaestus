"""Small, persistent cargo and environmental departments for the Ox freighter.

These fixtures deliberately model distinct jobs without inventing a skill score
or allowing the agent handler to set physical outcomes. Existing coolant
actions and character identities are untouched.
"""
from __future__ import annotations

from evennia.utils import gametime
from django.db import transaction
import re
from typeclasses.ship import FixedFixture


class DepartmentFixture(FixedFixture):
    """Stateful installed equipment with actor-local inspection provenance."""

    INITIAL_STATE = "unknown"
    EVENT_PREFIX = "dept"

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.db.operating_state = self.INITIAL_STATE
        self.db.event_seq = 0
        self.db.event_history = []
        self.db.inspections = {}

    @property
    def state(self) -> str:
        return self.db.operating_state or self.INITIAL_STATE

    def note_inspection(self, actor) -> None:
        """Inspection is evidence of a character's real physical presence."""
        if actor is None or actor.location != self.location:
            return
        records = dict(self.db.inspections or {})
        records[actor.dbref] = int(self.db.event_seq or 0)
        self.db.inspections = records

    def _fresh_inspection(self, actor) -> bool:
        return (
            actor is not None
            and dict(self.db.inspections or {}).get(actor.dbref)
            == int(self.db.event_seq or 0)
        )

    def _authorized(self, actor, role: str) -> bool:
        return bool(
            actor is not None
            and actor.location == self.location
            and actor.db.crew_role == role
        )

    def _record(self, operation: str, new_state: str, *, actor=None) -> None:
        before = self.state
        self.db.operating_state = new_state
        seq = int(self.db.event_seq or 0) + 1
        self.db.event_seq = seq
        history = list(self.db.event_history or [])
        history.append({
            "event_id": f"{self.EVENT_PREFIX}-{seq:04d}",
            "operation": operation,
            "before": before,
            "after": new_state,
            "actor_dbref": actor.dbref if actor else None,
            "game_time": float(gametime.gametime(absolute=True)),
        })
        self.db.event_history = history
        if self.location:
            self.location.msg_contents(
                f"{self.key}: {before} -> {new_state}.", exclude=actor,
            )

    def _alert(self, kind: str, assigned_role: str, message: str) -> None:
        """World-addressed alarms; the handler sees only legitimate inboxes.

        The authoritative world journal is indexed by recipient and supports
        replay independently of the physical equipment raising the alarm.
        """
        from world.bootstrap import build_ship
        from world.live_crew import emit
        ship = build_ship()
        for person in (ship["officer"], ship[assigned_role]):
            emit(
                ship["pump"], person, kind,
                data={"equipment": self.key, "state": self.state},
                text=message,
            )

    # Requests are actor-bound and persist with this *physical fixture*.
    # A refused transition is also durable: the same ID cannot later
    # change a previously rejected attempt into a successful operation.
    DURABLE_OPERATIONS: frozenset[str] = frozenset()

    def durable_action(self, request_id: str, operation: str, actor) -> dict:
        """Apply an authorized equipment command once, with a durable receipt."""
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("Invalid request ID")
        if operation not in self.DURABLE_OPERATIONS:
            raise ValueError("Unsupported physical operation for this fixture")
        if actor is None:
            raise PermissionError("An authenticated world character is required")
        with transaction.atomic():
            ledger = dict(self.db.ox_action_receipts or {})
            previous = ledger.get(request_id)
            if previous is not None:
                if (previous["actor_dbref"], previous["operation"]) != (
                    actor.dbref, operation
                ):
                    raise PermissionError("A different actor or operation owns this ID")
                return dict(previous)
            succeeded, _message = getattr(self, operation)(actor)
            events = list(self.db.event_history or [])
            receipt = {
                "request_id": request_id,
                "actor_dbref": actor.dbref,
                "operation": operation,
                "status": "succeeded" if succeeded else "failed",
                "reason": "transition_applied" if succeeded else "world_refused",
                "source_event_id": events[-1]["event_id"] if succeeded else None,
                "state": self.state if succeeded else None,
                "game_time": float(gametime.gametime(absolute=True)),
            }
            ledger[request_id] = receipt
            self.db.ox_action_receipts = ledger
            return dict(receipt)

    def durable_receipt(self, request_id: str, actor) -> dict:
        """Reveal only this character's receipt; never another actor's work."""
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("Invalid request ID")
        if actor is None:
            raise PermissionError("A world character is required")
        stored = dict(self.db.ox_action_receipts or {}).get(request_id)
        if stored is None or stored["actor_dbref"] != actor.dbref:
            return {
                "request_id": request_id, "actor_dbref": actor.dbref,
                "status": "unknown", "reason": "no_authorised_receipt",
                "source_event_id": None,
            }
        return dict(stored)

    def get_display_desc(self, looker, **kwargs) -> str:
        return f"{self.db.desc or ''}\n{self.readout()}"


class CargoCradle(DepartmentFixture):
    """C-01 restraints: survey -> restow -> fresh inspection -> certify."""

    INITIAL_STATE = "secured"
    EVENT_PREFIX = "c01"
    DURABLE_OPERATIONS = frozenset({"restow", "certify"})
    # Future skill-by-use tags, not current proficiency checks.
    SKILL_TAGS = {"restow": "cargo_rigging", "certify": "cargo_inspection"}

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.db.loaded_containers = 8
        self.db.capacity_containers = 12
        self.db.loose_restraints = 0

    def readout(self) -> str:
        return (
            f"CARGO RESTRAINT GRID C-01: {self.state.upper()}\n"
            f"Manifest: {self.db.loaded_containers} sealed containers / "
            f"{self.db.capacity_containers} positions.\n"
            f"Unsecured restraints: {int(self.db.loose_restraints or 0)}."
        )

    def inject_fault(self, actor=None) -> tuple[bool, str]:
        if actor is not None and not actor.check_permstring("Developer"):
            return False, "Only developers may inject a cargo shift."
        if self.state != "secured":
            return False, "C-01 is not in a secured state."
        self.db.loose_restraints = 2
        self._record("shift", "unsecured", actor=actor)
        self._alert(
            "cargo_shift", "cargo",
            "The cargo securing monitor reports two slack restraints.",
        )
        return True, "C-01 cargo shift recorded; securing inspection required."

    def restow(self, actor) -> tuple[bool, str]:
        if not self._authorized(actor, "cargo_officer"):
            return False, "A cargo officer must be physically present at C-01."
        if self.state != "unsecured" or not self._fresh_inspection(actor):
            return False, "Inspect the unsecured cargo restraints before restowing."
        self.db.loose_restraints = 0
        self._record("restow", "restowed", actor=actor)
        return True, "C-01 cargo restowed; fresh inspection required."

    def certify(self, actor) -> tuple[bool, str]:
        if not self._authorized(actor, "cargo_officer"):
            return False, "A cargo officer must be physically present at C-01."
        if self.state != "restowed" or not self._fresh_inspection(actor):
            return False, "Inspect the restowed load before certification."
        self._record("certify", "secured", actor=actor)
        return True, "C-01 cargo load certified secured."


class AtmosphereScrubber(DepartmentFixture):
    """A-01 cartridge work: inspect, isolate, replace, reinspect, restart."""

    INITIAL_STATE = "nominal"
    EVENT_PREFIX = "a01"
    DURABLE_OPERATIONS = frozenset({"isolate", "replace", "restart"})
    SKILL_TAGS = {
        "isolate": "atmosphere_diagnostics",
        "replace": "environmental_maintenance",
        "restart": "systems_validation",
    }

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.db.spare_cartridges = 2

    def readout(self) -> str:
        readings = {
            "nominal": "CO2 removal operating within designated limits",
            "saturated": "CO2 cartridge saturated; service required",
            "isolated": "Scrubber isolated for cartridge service",
            "serviced": "Cartridge replaced; restart check required",
        }
        return (
            f"ATMOSPHERE SCRUBBER A-01: {self.state.upper()}\n"
            f"{readings[self.state]}.\n"
            f"Local spare cartridges: {int(self.db.spare_cartridges or 0)}."
        )

    def inject_fault(self, actor=None) -> tuple[bool, str]:
        if actor is not None and not actor.check_permstring("Developer"):
            return False, "Only developers may inject a scrubber fault."
        if self.state != "nominal":
            return False, "A-01 cannot saturate outside nominal operation."
        self._record("saturate", "saturated", actor=actor)
        self._alert(
            "atmosphere_alarm", "environment",
            "The atmospheric scrubber reports a saturated cartridge.",
        )
        return True, "A-01 cartridge saturated; environmental service required."

    def isolate(self, actor) -> tuple[bool, str]:
        if not self._authorized(actor, "environment_tech"):
            return False, "The environmental technician must attend A-01."
        if self.state != "saturated" or not self._fresh_inspection(actor):
            return False, "Inspect the saturated scrubber before isolating."
        self._record("isolate", "isolated", actor=actor)
        return True, "A-01 safely isolated for service."

    def replace(self, actor) -> tuple[bool, str]:
        if not self._authorized(actor, "environment_tech"):
            return False, "The environmental technician must attend A-01."
        if self.state != "isolated":
            return False, "Isolate A-01 before replacing its cartridge."
        if int(self.db.spare_cartridges or 0) < 1:
            return False, "No replacement cartridge remains in local stores."
        self.db.spare_cartridges = int(self.db.spare_cartridges) - 1
        self._record("replace", "serviced", actor=actor)
        return True, "A-01 cartridge replaced; verify before restart."

    def restart(self, actor) -> tuple[bool, str]:
        if not self._authorized(actor, "environment_tech"):
            return False, "The environmental technician must attend A-01."
        if self.state != "serviced" or not self._fresh_inspection(actor):
            return False, "Inspect the serviced scrubber before restart."
        self._record("restart", "nominal", actor=actor)
        return True, "A-01 atmospheric scrubbing returned to nominal operation."


class OperationsConsole(FixedFixture):
    """Bridge telemetry explicitly published for operations, not device control."""

    def readout(self) -> str:
        from world.bootstrap import find_fixture
        cradle = find_fixture("cargo-cradle")
        scrubber = find_fixture("atmosphere-scrubber")
        return (
            "FREIGHTER OPERATIONS TELEMETRY\n"
            + (f"C-01 cargo restraints: {cradle.state.upper()}\n"
               if cradle else "C-01: NO READING\n")
            + (f"A-01 atmosphere scrubber: {scrubber.state.upper()}"
               if scrubber else "A-01: NO READING")
        )

    def get_display_desc(self, looker, **kwargs) -> str:
        return self.readout()


class DutyBoard(FixedFixture):
    """Posted standard duties; equipment condition is *not* a private memory."""

    def readout(self) -> str:
        return (
            "SHIPBOARD DEPARTMENT DUTIES\n"
            "Bridge: Lin Sato -- monitor instruments and coordinate alerts.\n"
            "Engineering: Ari Sen / Iona Vek -- cooling and safe commissioning.\n"
            "Cargo: Mara Voss -- inspect restraints, restow and certify loads.\n"
            "Environmental: Teo Hale -- inspect, isolate and service A-01.\n"
            "Machine shop: reserved for later fabrication and engineering work."
        )

    def get_display_desc(self, looker, **kwargs) -> str:
        return self.readout()
