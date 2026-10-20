"""Safety ceiling for disposable six-character trials, not a game mechanic.

Turn reservations are synchronous (there is no await inside claim) and
therefore atomic in the runner's single asyncio event loop. A cap is a
test-harness stop, never evidence of an in-world death.
"""


class TurnCapReached(RuntimeError):
    """An experimental decision ceiling was reached, not a character event."""


class TurnBudget:
    def __init__(self, roles, *, max_per_character: int, max_total: int):
        if type(max_per_character) is not int or max_per_character < 1:
            raise ValueError("Per-character turn ceiling must be positive")
        if type(max_total) is not int or max_total < 1:
            raise ValueError("Total turn ceiling must be positive")
        identities = tuple(roles)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("Each distinct actor must have one budget identity")
        self.counts = {role: 0 for role in identities}
        self.total = 0
        self.max_per_character = max_per_character
        self.max_total = max_total

    def claim(self, role: str) -> int:
        """Reserve one decision slot or report an explicit experiment stop."""
        if role not in self.counts:
            raise PermissionError("Unknown actor cannot claim a turn")
        if self.total >= self.max_total:
            raise TurnCapReached("total_turn_limit")
        if self.counts[role] >= self.max_per_character:
            raise TurnCapReached("character_turn_limit:" + role)
        self.counts[role] += 1
        self.total += 1
        return self.counts[role]
