"""Idempotently construct the first persistent Ox ship in Evennia's database.

The builder is not a simulator. Evennia remains authoritative; rerunning this
function does not reset equipment state, crew position, or recorded outcomes.
"""

from __future__ import annotations

from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object

FIXTURE_CATEGORY = "ox_ship_prototype"

CREW_MARKERS = ("crew-chief", "crew-watch", "crew-bridge")


def find_fixture(marker: str):
    """Resolve one Ox-owned entity by durable Evennia tag, not by display name."""
    matches = list(ObjectDB.objects.get_by_tag(key=marker, category=FIXTURE_CATEGORY))
    if len(matches) > 1:
        raise RuntimeError(f"Duplicate Ox fixture tag {marker!r}; refusing to guess")
    return matches[0] if matches else None


def _ensure(marker: str, typeclass: str, key: str, **kwargs):
    """Create one tagged object, leaving existing world state untouched."""
    existing = find_fixture(marker)
    if existing is not None:
        return existing
    return create_object(
        typeclass,
        key=key,
        tags=[(marker, FIXTURE_CATEGORY)],
        **kwargs,
    )


def _room(marker: str, name: str, desc: str):
    """Make one named navigable compartment without changing live descriptions."""
    room = _ensure(marker, "typeclasses.ship.ShipRoom", name, nohome=True)
    if not room.db.desc:
        room.db.desc = desc
    return room


def _exit(marker: str, name: str, origin, destination, aliases=()):
    """Add one directional passage; never silently reroute an existing exit."""
    return _ensure(
        marker,
        "evennia.objects.objects.DefaultExit",
        name,
        location=origin,
        destination=destination,
        aliases=list(aliases),
    )


def build_ship() -> dict[str, object]:
    """Install three linked rooms, equipment and three initially idle crew.

    This can be run repeatedly, from the one-time startup hook or via shell.
    It does not create accounts, sessions, autonomous cognition or a timed AI
    process. Return objects for tests and local operator tooling.
    """
    bridge = _room(
        "room-bridge",
        "Bridge",
        "The small freighter's command deck has a forward navigation display, "
        "a bolted watch roster, and a cooling-system telemetry console. "
        "The passage leads aft toward engineering.",
    )
    passage = _room(
        "room-passage",
        "Connecting Passage",
        "A narrow, worn companionway runs between bridge and engineering. "
        "Conduit trunks and inspection hatches line its bulkheads.",
    )
    engineering = _room(
        "room-engineering",
        "Engineering",
        "Heat exchangers and service manifolds crowd this compartment. "
        "Cooling Pump P-01 is secured beside the pressure gauge and isolation "
        "valves. The connecting passage leads forward.",
    )

    _exit("exit-bridge-passage", "aft", bridge, passage, aliases=("passage",))
    _exit("exit-passage-bridge", "fore", passage, bridge, aliases=("bridge",))
    _exit(
        "exit-passage-engineering",
        "engineering",
        passage,
        engineering,
        aliases=("engine room",),
    )
    _exit("exit-engineering-passage", "out", engineering, passage, aliases=("fore",))

    # Limbo is Evennia's first-run entry room (#2); it may not exist in tests
    # or before initial_setup. Do not create a fake Limbo in that situation.
    limbo = ObjectDB.objects.filter(id=2).first()
    if limbo is not None and limbo.key.lower() == "limbo":
        _exit("exit-limbo-board", "board", limbo, bridge, aliases=("ship",))
        _exit("exit-bridge-disembark", "disembark", bridge, limbo)

    pump = _ensure(
        "pump-p01",
        "typeclasses.ship.CoolingPump",
        "Cooling Pump P-01",
        location=engineering,
        aliases=["pump", "p-01", "p01"],
    )
    if not pump.db.desc:
        pump.db.desc = "A heavy-duty circulation pump bolted into coolant loop A."

    console = _ensure(
        "panel-bridge",
        "typeclasses.ship.StatusConsole",
        "Cooling Status Console",
        location=bridge,
        aliases=["console", "panel"],
    )
    if not console.db.desc:
        console.db.desc = "The bridge's read-only cooling loop instrumentation."

    roster = _ensure(
        "roster-board",
        "typeclasses.ship.RosterBoard",
        "Watch Roster",
        location=bridge,
        aliases=["roster", "duty roster"],
    )

    crew_spec = (
        (
            "crew-chief",
            "Chief Engineer Iona Vek",
            engineering,
            "chief_engineer",
            "Chief engineer; on-call escalation",
            "on call",
        ),
        (
            "crew-watch",
            "Engineer Ari Sen",
            engineering,
            "watch_engineer",
            "Watch engineer; cooling-system rounds",
            "00:00–08:00",
        ),
        (
            "crew-bridge",
            "Officer Lin Sato",
            bridge,
            "bridge_officer",
            "Bridge watch; navigation and ship systems",
            "00:00–08:00",
        ),
    )
    members = {}
    for marker, key, room, role, duty, watch in crew_spec:
        existing = find_fixture(marker)
        member = _ensure(
            marker,
            "typeclasses.ship.CrewCharacter",
            key,
            location=room,
            home=room,
        )
        if existing is None:
            member.db.crew_role = role
            member.db.duty_title = duty
            member.db.watch_window = watch
            member.db.desc = "A crew member standing their posted shipboard watch."
        members[marker] = member

    return {
        "bridge": bridge,
        "passage": passage,
        "engineering": engineering,
        "pump": pump,
        "console": console,
        "roster": roster,
        "chief": members["crew-chief"],
        "watch": members["crew-watch"],
        "officer": members["crew-bridge"],
    }
