"""Authenticated local terminal-incident sensor; no operator-state access."""
from evennia.commands.command import Command


class CmdOxTerminal(Command):
    """Read local ship atmospheric telemetry with proper actor provenance."""

    key = "oxterminal"
    locks = "cmd:all()"

    def func(self):
        from world.terminal_failure import observe_terminal
        if self.args.strip():
            self.caller.msg("Usage: oxterminal")
            return
        try:
            evidence = observe_terminal(self.caller)
        except (PermissionError, RuntimeError):
            self.caller.msg("Terminal sensors unavailable to this character.")
            return
        self.caller.msg(ox_terminal=([evidence], {}))
