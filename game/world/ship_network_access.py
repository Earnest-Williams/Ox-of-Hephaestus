"""Trust boundary for network-delivered hatch observations (no Django dependency).

A physical observation is not automatically a network event. Each delivered
record is independently sealed to an enrolled account principal and committed
when a surveyed local gateway can reach operating compute.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re

from world.ship_access_contact import GATEWAY, LINK, OBSERVED, SENSOR


SCHEMA = "ox.network-access/1"
PRINCIPAL = "principal:ox-lead-mind"
DELIVERED = "g19_access_network_delivered"
MAX_PAGE = 32
_TOKEN = re.compile(r"^v1\.([0-9a-f]{1,16})\.([0-9a-f]{64})$")
_ID = re.compile(r"^[0-9]+$")


class NetworkAccessError(ValueError):
    """Unverified network evidence, invalid principal, or unsafe replay."""


def require(ok, message):
    if not ok:
        raise NetworkAccessError(message)


def valid_limit(limit):
    require(type(limit) is int and 1 <= limit <= MAX_PAGE,
            "Invalid network page size")
    return limit


def _get(event, name):
    return (event.get(name) if isinstance(event, dict)
            else getattr(event, name, None))


def capture(event):
    """Encode only *actual passive-contact evidence*, never hidden crew data."""
    require(_get(event, "operation") == OBSERVED
            and _get(event, "component_key") == "equipment:" + SENSOR,
            "Not an installed local access observation")
    sequence = _get(event, "sequence")
    source_id = _get(event, "source_event_id")
    before = _get(event, "before")
    after = _get(event, "after")
    seconds = _get(event, "game_time")
    require(type(sequence) is int and sequence > 0
            and isinstance(source_id, str) and _ID.fullmatch(source_id)
            and isinstance(before, dict) and isinstance(after, dict)
            and type(seconds) in (int, float) and math.isfinite(seconds)
            and seconds >= 0,
            "Invalid source evidence identity or time")
    previous = before.get("setting")
    current = after.get("setting")
    require(previous in {"open", "closed"}
            and current in {"open", "closed"} and previous != current
            and after.get("link_id") == LINK
            and type(after.get("sensor_revision")) is int
            and after["sensor_revision"] > 0
            and type(after.get("cable_revision")) is int
            and after["cable_revision"] >= 0
            and _get(event, "actor_dbref") is None
            and _get(event, "request_id") is None,
            "No verified change from an anonymous local contact")
    return {
        "sensor_event_id": str(sequence),
        "physical_hatch_event_id": source_id,
        "reader_id": SENSOR,
        "gateway_id": GATEWAY,
        "access_link_id": LINK,
        "kind": "hatch_change",
        "setting_before": previous,
        "setting_after": current,
        "sensor_revision": after["sensor_revision"],
        "cable_revision": after["cable_revision"],
        "source_time": float(seconds),
    }


def seal(secret, account_pk, epoch, sequence):
    """Opaque, account-and-enrolment-bound ack proof, not an untrusted cursor."""
    require(isinstance(secret, str) and re.fullmatch(r"[0-9a-f]{64}", secret)
            and type(account_pk) is int and account_pk > 0
            and isinstance(epoch, str) and re.fullmatch(r"[0-9a-f]{32}", epoch)
            and type(sequence) is int and sequence > 0,
            "Invalid private acknowledgement context")
    text = f"{SCHEMA}:{account_pk}:{epoch}:{sequence}".encode()
    digest = hmac.new(bytes.fromhex(secret), text, hashlib.sha256).hexdigest()
    return f"v1.{sequence:x}.{digest}"


def unseal(token, secret, account_pk, epoch):
    require(isinstance(token, str) and len(token) <= 90,
            "Invalid acknowledgement")
    match = _TOKEN.fullmatch(token)
    require(match is not None, "Invalid acknowledgement")
    number = int(match.group(1), 16)
    require(hmac.compare_digest(token, seal(secret, account_pk, epoch, number)),
            "Wrong principal acknowledgement")
    return number


def present_delivery(event, *, epoch):
    """Return the stored network capsule, never the raw underlying event."""
    sequence = _get(event, "sequence")
    packet = _get(event, "after")
    source = _get(event, "source_event_id")
    require(type(sequence) is int and sequence > 0
            and _get(event, "operation") == DELIVERED
            and _get(event, "component_key") == PRINCIPAL
            and isinstance(packet, dict)
            and packet.get("epoch") == epoch
            and str(packet.get("sensor_event_id")) == source
            and _get(event, "actor_dbref") is None
            and _get(event, "request_id") is None,
            "Untrusted or foreign network capsule")
    safe = {
        "sensor_event_id", "physical_hatch_event_id", "reader_id",
        "gateway_id", "access_link_id", "kind", "setting_before",
        "setting_after", "sensor_revision", "cable_revision", "source_time",
    }
    require(set(packet) == safe | {"epoch"}, "Network capsule has unknown data")
    require(packet["reader_id"] == SENSOR
            and packet["gateway_id"] == GATEWAY
            and packet["access_link_id"] == LINK
            and packet["kind"] == "hatch_change"
            and packet["setting_before"] in {"open", "closed"}
            and packet["setting_after"] in {"open", "closed"}
            and packet["setting_before"] != packet["setting_after"]
            and type(packet["source_time"]) in (int, float)
            and math.isfinite(packet["source_time"]),
            "Network capsule is not a verified hatch change")
    return {"delivery_event_id": "ox-net-" + str(sequence),
            **{key: packet[key] for key in sorted(safe)}}
