"""In-world commands for Ox's first playable engineering compartment.

A model-controlled character will eventually use these same commands through
an ordinary Evennia client. No command trusts a claimed model outcome.
"""

from __future__ import annotations

from evennia.commands.command import Command

from typeclasses.ship import CoolingPump
from typeclasses.departments import CargoCradle, AtmosphereScrubber


class CmdInspect(Command):
    """Inspect local ship machinery or a nearby bridge console.

    Usage:
        inspect <equipment>
    """

    key = "inspect"
    aliases = ["readout"]
    locks = "cmd:all()"

    def func(self) -> None:
        """Read a fixture visible in the caller's current compartment."""
        if not self.args.strip():
            self.caller.msg("Inspect what? Try 'inspect pump' or 'inspect console'.")
            return
        target = self.caller.search(self.args.strip(), location=self.caller.location)
        if target is None:
            return
        if not callable(getattr(target, "readout", None)):
            self.caller.msg("That object has no shipboard readout.")
            return
        self.caller.msg(target.readout())
        if isinstance(target, CoolingPump):
            from world.live_crew import note_inspection
            note_inspection(self.caller, target)
        elif isinstance(target, (CargoCradle, AtmosphereScrubber)):
            target.note_inspection(self.caller)


class _CmdPumpOperation(Command):
    """Find a local pump and request a validated game-side transition."""

    operation = ""

    def func(self) -> None:
        """Execute the game command against local authoritative equipment."""
        if not self.args.strip():
            self.caller.msg(f"{self.key.capitalize()} what? Try '{self.key} pump'.")
            return
        target = self.caller.search(self.args.strip(), location=self.caller.location)
        if target is None:
            return
        if not isinstance(target, CoolingPump):
            if not (self.operation == "isolate"
                    and isinstance(target, AtmosphereScrubber)):
                self.caller.msg("This operation is not supported by that equipment.")
                return
        _success, message = getattr(target, self.operation)(self.caller)
        self.caller.msg(message)


class CmdIsolate(_CmdPumpOperation):
    """Isolate a faulted coolant pump.

    Usage:
        isolate pump
    """

    key = "isolate"
    operation = "isolate"
    locks = "cmd:all()"


class CmdRepair(_CmdPumpOperation):
    """Repair an isolated coolant pump.

    Usage:
        repair pump
    """

    key = "repair"
    operation = "repair"
    locks = "cmd:all()"


class CmdCommission(_CmdPumpOperation):
    """Return a repaired coolant pump to service.

    Usage:
        commission pump
    """

    key = "commission"
    operation = "commission"
    locks = "cmd:all()"


class CmdShipFault(Command):
    """Introduce a synthetic equipment fault (developers only).

    Usage:
        shipfault <pump|cargo|scrubber>
    """

    key = "shipfault"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        """Allow only authorised operators to inject a physical-world fault."""
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may inject test faults.")
            return
        lookup = {
            "pump": "pump", "p-01": "pump", "p01": "pump",
            "cargo": "cargo", "c-01": "cargo",
            "scrubber": "scrubber", "a-01": "scrubber",
        }
        name = lookup.get(self.args.strip().lower())
        if name is None:
            self.caller.msg("Usage: shipfault <pump|cargo|scrubber>")
            return
        target = self.caller.search(name, location=self.caller.location)
        if not isinstance(target, (CoolingPump, CargoCradle, AtmosphereScrubber)):
            self.caller.msg("That equipment is not within reach.")
            return
        _success, message = target.inject_fault(self.caller)
        self.caller.msg(message)


class CmdShipEngineer(Command):
    """Assume a test engineering role for the current character (developer).

    Usage:
        shipengineer

    This changes game-side authorisation for testing; it is not an AI power.
    """

    key = "shipengineer"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        """Give a developer-controlled body the prototype watch role."""
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may assume the prototype watch.")
            return
        self.caller.db.crew_role = "watch_engineer"
        self.caller.db.duty_title = "Engineering watch (developer test)"
        self.caller.msg("You are authorised for the prototype engineering watch.")


class CmdShipRole(Command):
    """Assume a specialist test duty in a disposable development world.

    Usage: shiprole <cargo|environment>

    Not an in-world promotion system. No production player can change
    their own specialist qualifications or engineering authority this way.
    """

    key = "shiprole"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may assume a test department role.")
            return
        assignments = {
            "cargo": ("cargo_officer", "Cargo test duty"),
            "environment": ("environment_tech", "Environmental test duty"),
        }
        role = assignments.get(self.args.strip().lower())
        if role is None:
            self.caller.msg("Usage: shiprole <cargo|environment>")
            return
        self.caller.db.crew_role, self.caller.db.duty_title = role
        self.caller.msg("Developer specialist duty set; physical access still required.")



class CmdOxIdentity(Command):
    """Report the caller's own character dbref in response to a fresh nonce.

    This is a normal, non-privileged, character-scoped command. It exposes
    nothing beyond the identity of the character issuing the command.
    """

    key = "oxidentity"
    locks = "cmd:all()"

    def func(self) -> None:
        import re
        nonce = self.args.strip()
        if not re.fullmatch(r"[0-9a-f]{32}", nonce):
            self.caller.msg("Usage: oxidentity <32 hex digit challenge>")
            return
        self.caller.msg(f"OX_IDENTITY {nonce} {self.caller.dbref}")

class CmdOxAction(Command):
    """Durable, role-checked action on P-01, C-01 or A-01.

    The original two-argument P-01 contract remains supported; extended
    fixtures explicitly name their target to prevent aliasing commands.
    """

    key = "oxaction"
    locks = "cmd:all()"

    def func(self) -> None:
        import re
        from world.bootstrap import find_fixture

        parts = self.args.strip().split()
        usage = ("Usage: oxaction <request-id> <isolate|repair|commission> "
                 "[pump]; or <request-id> <operation> <cargo|scrubber>")
        if (len(parts) not in (2, 3)
                or re.fullmatch(r"[0-9a-f]{32}", parts[0]) is None):
            self.caller.msg(usage)
            return
        request_id, operation = parts[:2]
        fixture_name = parts[2] if len(parts) == 3 else "pump"
        targets = {
            "pump": ("pump-p01", CoolingPump, ("isolate", "repair", "commission")),
            "cargo": ("cargo-cradle", CargoCradle, ("restow", "certify")),
            "scrubber": ("atmosphere-scrubber", AtmosphereScrubber,
                        ("isolate", "replace", "restart")),
        }
        spec = targets.get(fixture_name)
        if spec is None or operation not in spec[2]:
            self.caller.msg(usage)
            return
        equipment = find_fixture(spec[0])
        if not isinstance(equipment, spec[1]):
            self.caller.msg("Equipment is unavailable.")
            return
        try:
            result = equipment.durable_action(request_id, operation, self.caller)
        except PermissionError:
            result = {
                "request_id": request_id, "actor_dbref": self.caller.dbref,
                "operation": operation, "status": "failed",
                "reason": "request_collision", "source_event_id": None,
            }
        self.caller.msg(ox_receipt=([result], {}))


class CmdOxReceipt(Command):
    """Look up this actor's own durable operation, by equipment namespace."""

    key = "oxreceipt"
    locks = "cmd:all()"

    def func(self) -> None:
        import re
        from world.bootstrap import find_fixture

        parts = self.args.strip().split()
        if (len(parts) not in (1, 2)
                or re.fullmatch(r"[0-9a-f]{32}", parts[0]) is None):
            self.caller.msg("Usage: oxreceipt <request-id> [pump|cargo|scrubber]")
            return
        request_id = parts[0]
        fixture_name = parts[1] if len(parts) == 2 else "pump"
        targets = {
            "pump": ("pump-p01", CoolingPump),
            "cargo": ("cargo-cradle", CargoCradle),
            "scrubber": ("atmosphere-scrubber", AtmosphereScrubber),
        }
        spec = targets.get(fixture_name)
        if spec is None:
            self.caller.msg("Usage: oxreceipt <request-id> [pump|cargo|scrubber]")
            return
        equipment = find_fixture(spec[0])
        if not isinstance(equipment, spec[1]):
            self.caller.msg("Equipment is unavailable.")
            return
        self.caller.msg(ox_receipt=([
            equipment.durable_receipt(request_id, self.caller)
        ], {}))
