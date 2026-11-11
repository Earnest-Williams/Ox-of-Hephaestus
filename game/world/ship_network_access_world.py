"""Evennia-owned enrolled principal and event-time network access deliveries.

An account is authenticated by Evennia's account command path, not a supplied
principal ID, character puppet, client-supplied reader list, or handler token.
Live electrical, thermal and A/B fibre evidence decides which observed events
cross to the account's durable, replayable inbox.
"""

from __future__ import annotations

import copy
import secrets

from django.db import transaction
from evennia.accounts.models import AccountDB

from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_access_contact import (
    CABLE, GATEWAY, LINK, SENSOR, certificate_valid, contact_specifications,
)
from world.ship_network_access import (
    DELIVERED, MAX_PAGE, PRINCIPAL, SCHEMA, NetworkAccessError,
    capture, present_delivery, require, seal, unseal, valid_limit,
)


def _account_id(account):
    """Accept an actual stored Evennia account, not a claimed ID or puppet."""
    pk = getattr(account, "pk", None)
    require(
        isinstance(account, AccountDB)
        and type(pk) is int and pk > 0
        and AccountDB.objects.filter(pk=pk).exists(),
        "Authenticated Evennia account required",
    )
    return pk


def _principal(account, *, lock=False):
    pk = _account_id(account)
    query = CanonicalShipState.objects
    if lock:
        query = query.select_for_update()
    row = query.filter(pk=PRINCIPAL).first()
    require(row is not None and row.category == "principal"
            and row.source_model == SCHEMA
            and row.source_id == "OX-LEAD-MIND"
            and row.space_id is None
            and row.setting == "bound" and row.condition == "serviceable"
            and isinstance(row.reference, dict)
            and row.reference.get("account_pk") == pk
            and row.reference.get("gateway") == GATEWAY
            and row.reference.get("reader") == SENSOR
            and row.reference.get("role") == "bodiless_ship_mind"
            and isinstance(row.reference.get("epoch"), str)
            and isinstance(row.details, dict)
            and set(row.details) == {
                "hmac_secret", "acked_sequence", "issued_sequence",
                "issued_has_more",
            }
            and type(row.details["issued_has_more"]) is bool
            and type(row.details["acked_sequence"]) is int
            and type(row.details["issued_sequence"]) is int
            and 0 <= row.details["acked_sequence"] <= row.details["issued_sequence"],
            "Account has no verified ship-mind enrollment")
    return row


@transaction.atomic
def enroll_access_account(account, *, operator_approved=False):
    """Bind one genuine OOC account once; existing bindings never get replaced."""
    if not operator_approved:
        raise PermissionError("Only a world operator may enroll a ship principal")
    pk = _account_id(account)
    from world.continuous_ship_physics import _clock
    clock = _clock(lock=True)
    require(clock.details.get("mind_gateway") is not None
            and clock.details.get("mind_cooling") is not None,
            "Network hardware must be installed before principal enrollment")
    candidate = {
        "key": PRINCIPAL, "category": "principal",
        "source_id": "OX-LEAD-MIND", "source_model": SCHEMA,
        "space_id": None, "condition": "serviceable",
        "setting": "bound",
        "reference": {
            "account_pk": pk, "gateway": GATEWAY, "reader": SENSOR,
            "role": "bodiless_ship_mind", "epoch": secrets.token_hex(16),
        },
        "details": {
            "hmac_secret": secrets.token_hex(32),
            "acked_sequence": 0, "issued_sequence": 0,
            "issued_has_more": False,
        },
    }
    row, created = CanonicalShipState.objects.get_or_create(
        pk=PRINCIPAL, defaults=candidate)
    if not created:
        _principal(account, lock=True)  # Reject reassignment / altered binding.
        return {"enrolled": False, "idempotent": True}
    CanonicalShipEvent.objects.create(
        component_key=PRINCIPAL, operation="g19_access_principal_enrolled",
        before={}, after={"role": "bodiless_ship_mind", "account_pk": pk,
                          "gateway": GATEWAY, "reader": SENSOR},
        game_time=float(clock.details["last_game_time"]),
    )
    return {"enrolled": True, "idempotent": False}


def network_reachable(clock):
    """A conservative *current* network proof, not last tick's connected bit.

    Both the local gateway's live power and a core machine's current selected
    feed are checked. The canonical electrical and finite mind-power routines
    run over current world rows without committing a simulated timestep.
    The last thermal proof and every surveyed fibre path also must survive.
    """
    details = clock.details
    gateway = details.get("mind_gateway")
    service = details.get("mind_support_last")
    mind = details.get("mind_power")
    if (not isinstance(gateway, dict)
            or not isinstance(service, dict)
            or not isinstance(mind, dict)
            or not isinstance(details.get("mind_cooling"), dict)
            or gateway.get("last", {}).get("connected") is not True
            or service.get("observed_s") != details.get("last_game_time")
            or not service.get("compute_ready")):
        return False
    from world.ship_access_contact_world import _gateway_power_live
    if not _gateway_power_live(clock)[0]:
        return False

    from world.continuous_ship_physics import _power, PhysicsError
    from world.full_ship_operations import load_candidate
    from world.ship_port_operations import contacts_active
    from world.ship_mind_power import (
        MindPowerError, load_design as load_power_design,
    )
    from world.ship_mind_runtime import tick_mind_power
    from world.ship_mind_support import (
        connected_machines, load_support,
    )
    from world.ship_mind_support_world import installed_support_rows

    all_rows = {row.key: row for row in CanonicalShipState.objects.all()}
    equipment = {row.source_id: row for row in all_rows.values()
                 if row.category == "equipment"}
    edges = [row for row in all_rows.values() if row.category == "edge"]
    switches = {row.source_id: row for row in all_rows.values()
                if row.category == "isolator"}
    try:
        grid = _power(
            equipment, edges, switches, details["load_profile"],
            ledger=details["electrical"],
            moored=contacts_active(details.get("cargo", {})),
        )
        design = load_power_design()
        supported = load_support()
        ship = load_candidate()
        # This one-second dry run *checks* live supply and reserve; it never
        # advances meters, transfers contacts or grants free power.
        forecast, _ = tick_mind_power(
            design, mind, rows=all_rows, g19_power=grid,
            seconds=1, loads_enabled=True,
        )
        available = set(forecast["last"]["powered"]) & set(
            service["compute_ready"])
        if not available:
            return False
        physical = installed_support_rows(
            CanonicalShipState, supported, design, ship)
        # One failed rejector does not eliminate a still-finite cold store.
        # Nor does one broken cold plate remove its healthy sibling.
        from world.ship_network_access import thermally_ready
        available = thermally_ready(
            supported, details["mind_cooling"], physical,
            service.get("thermal_receipts", {}),
            available, forecast["last"]["delivered_heat_kj"],
        )
        if not available:
            return False
        connected = connected_machines(
            supported, available_machines=available,
            physical_rows=physical, gateway_id=GATEWAY)
        return bool(connected)
    except (MindPowerError, PhysicsError, KeyError, ValueError, TypeError):
        return False


def observe_network_delivery(sender, instance, created, **kwargs):
    """Issue a world event *during* a local observation only when the path lives.

    No polling of old local observations, no buffered resend of missed events.
    Local contact observations continue even while this network is dark.
    """
    if not created or instance.operation != "g19_access_contact_observed":
        return
    principal = CanonicalShipState.objects.select_for_update().filter(
        pk=PRINCIPAL).first()
    if principal is None:
        return
    try:
        require(principal.source_model == SCHEMA
                and principal.setting == "bound"
                and principal.condition == "serviceable",
                "Network principal not fitted")
        packet = capture(instance)
        old = CanonicalShipEvent.objects.filter(
            pk=int(packet["physical_hatch_event_id"]),
            operation="crew_hatch", component_key="access:" + LINK,
        ).first()
        require(old is not None
                and old.before.get("setting") == packet["setting_before"]
                and old.after.get("setting") == packet["setting_after"],
                "Contact does not cite its original door change")
        clock = CanonicalShipState.objects.filter(
            pk="meta:continuous-physics").first()
        if clock is None or not network_reachable(clock):
            return
        from world.ship_access_contact_world import (
            _gateway_power_live, _rows,
        )
        from world.ship_model import load_ship_model
        proof_rows = _rows(contact_specifications(load_ship_model()))
        live, revisions = _gateway_power_live(clock)
        if not live or not certificate_valid(proof_rows, revisions):
            return
        if (proof_rows["equipment:" + SENSOR].revision !=
                packet["sensor_revision"]
                or proof_rows["edge:" + CABLE].revision !=
                packet["cable_revision"]):
            return
        epoch = principal.reference.get("epoch")
        require(isinstance(epoch, str) and len(epoch) == 32,
                "Missing enrollment epoch")
        if CanonicalShipEvent.objects.filter(
            component_key=PRINCIPAL, operation=DELIVERED,
            source_event_id=str(instance.sequence),
        ).exists():
            return
        CanonicalShipEvent.objects.create(
            component_key=PRINCIPAL, operation=DELIVERED,
            before={}, after={**packet, "epoch": epoch},
            source_event_id=str(instance.sequence),
            actor_dbref=None, request_id=None,
            game_time=float(instance.game_time),
        )
    except NetworkAccessError:
        return  # Invalid instrument evidence never cancels a physical hatch.


@transaction.atomic
def access_page(account, *, limit=16):
    """Read only capsules previously *delivered* while a real path was live.

    Pages are replayable until acknowledged. No client-controlled sequence,
    reader IDs, access scope, or capability can address the raw world journal.
    """
    valid_limit(limit)  # Before any ORM or network scan.
    principal = _principal(account, lock=True)
    clock = CanonicalShipState.objects.filter(
        pk="meta:continuous-physics").first()
    require(clock is not None and network_reachable(clock),
            "Ship network is not currently reachable")
    after = principal.details["acked_sequence"]
    issued = principal.details["issued_sequence"]
    query = CanonicalShipEvent.objects.filter(
        component_key=PRINCIPAL, operation=DELIVERED, sequence__gt=after,
    )
    if issued > after:
        # Freeze the exact issued prefix until it has been acknowledged.
        # New network deliveries cannot enlarge a page or change its token,
        # even across restarts or if a different internal limit is requested.
        page = list(query.filter(sequence__lte=issued).order_by(
            "sequence")[:MAX_PAGE + 1])
        require(bool(page) and len(page) <= MAX_PAGE
                and page[-1].sequence == issued,
                "Unacknowledged page has lost committed delivery evidence")
        has_more = principal.details["issued_has_more"]
    else:
        rows = list(query.order_by("sequence")[:limit + 1])
        page = rows[:limit]
        has_more = len(rows) > limit
        if page:
            principal.details = {
                **principal.details,
                "issued_sequence": page[-1].sequence,
                "issued_has_more": has_more,
            }
            principal.revision += 1
            principal.save(update_fields=["details", "revision"])
    entries = [
        present_delivery(row, epoch=principal.reference["epoch"]) for row in page
    ]
    ack = (
        seal(principal.details["hmac_secret"],
             principal.reference["account_pk"],
             principal.reference["epoch"], page[-1].sequence)
        if page else None
    )
    return {
        "version": 1, "principal": "ship_lead",
        "events": entries, "has_more": has_more,
        "ack_token": ack,
    }


@transaction.atomic
def acknowledge_page(account, token):
    """Persist an account-bound delivery prefix; safe across process restart."""
    principal = _principal(account, lock=True)
    sequence = unseal(
        token, principal.details["hmac_secret"],
        principal.reference["account_pk"], principal.reference["epoch"])
    details = principal.details
    require(sequence <= details["issued_sequence"],
            "Cannot acknowledge an unissued page")
    receipt = CanonicalShipEvent.objects.filter(
        pk=sequence, component_key=PRINCIPAL,
        operation=DELIVERED).first()
    require(receipt is not None,
            "Acknowledgement does not belong to this principal")
    # This is a receiver acknowledgement of an earlier delivered event,
    # not permission to read newly isolated machinery or lost observations.
    if sequence <= details["acked_sequence"]:
        return {"acknowledged": False, "idempotent": True}
    principal.details = {**details, "acked_sequence": sequence}
    principal.revision += 1
    principal.save(update_fields=["details", "revision"])
    return {"acknowledged": True, "idempotent": False}
