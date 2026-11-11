"""Internal access-evidence projection for the future ship-wide mind.

Only world-emitted, committed CanonicalShipEvent rows are inputs. A permitted
network reader and its identity reader are separate facts: this module cannot
invent a fitted reader, grant a principal, or authorize remote machinery.
No player/handler endpoint calls this module until a world-owned, authenticated
network scope and delivery ledger exist.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from world.ship_model import ShipWorldModel


PLAN_SCHEMA = "ox.ship-access-monitoring/1"
PLAN_STATUS = "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY"
EVENT_SOURCES = frozenset({
    "crew_traverse", "crew_hatch", "crew_indexed_transfer_complete",
})


class AccessEvidenceError(ValueError):
    """An access design, reader scope or cursor is invalid."""


@dataclass(frozen=True)
class AccessMonitoringPlan:
    topology_version: str
    controlled_spaces: frozenset[str]
    rack_reader_candidates: tuple[tuple[str, str], ...]
    candidate_link_options: dict[str, tuple[bool, bool]]

    def controlled_links(self, model: ShipWorldModel) -> frozenset[str]:
        """Return candidates, not evidence of installed working readers."""
        return frozenset(
            link.id for link in model.access_links
            if link.from_id in self.controlled_spaces
            or link.to_id in self.controlled_spaces
        )


def access_plan_path() -> Path:
    return (Path(__file__).resolve().parents[2] / "design" / "ship"
            / "access_monitoring_v01.json")


def _id_list(value: Any, label: str) -> list[str]:
    if (not isinstance(value, list)
            or any(not isinstance(item, str) or not item.strip()
                   for item in value)
            or len(value) != len(set(value))):
        raise AccessEvidenceError(f"Invalid or duplicate {label}")
    return value


def load_access_plan(model: ShipWorldModel, path: str | Path | None = None
                     ) -> AccessMonitoringPlan:
    """Validate a proposed retrofit against actual canonical geometry.

    This does not commission readers, doors or motors. The MIND-03 rack is
    explicitly separate from the public cross-trunk passage at gap 23.
    """
    try:
        data = json.loads(
            Path(path or access_plan_path()).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AccessEvidenceError("Unreadable access monitoring plan") from exc
    if (not isinstance(data, dict)
            or set(data) != {
                "schema_version", "status", "topology_version",
                "controlled_spaces", "rack_reader_candidates",
                "candidate_access_links",
            }
            or data["schema_version"] != PLAN_SCHEMA
            or data["status"] != PLAN_STATUS
            or data["topology_version"] != model.model_version):
        raise AccessEvidenceError("Wrong access-plan schema or topology")
    controlled = _id_list(data["controlled_spaces"], "controlled spaces")
    if any(space not in model.spaces_by_id for space in controlled):
        raise AccessEvidenceError("Controlled space is absent from the ship")
    if not isinstance(data["rack_reader_candidates"], list):
        raise AccessEvidenceError("Malformed rack reader candidates")
    racks: list[tuple[str, str]] = []
    for item in data["rack_reader_candidates"]:
        if (not isinstance(item, dict)
                or set(item) != {"rack_id", "space_id"}
                or not all(isinstance(v, str) and v.strip()
                           for v in item.values())
                or item["space_id"] not in model.spaces_by_id):
            raise AccessEvidenceError("Invalid rack reader candidate")
        racks.append((item["rack_id"], item["space_id"]))
    if len(set(racks)) != len(racks):
        raise AccessEvidenceError("Duplicate rack reader candidate")
    # A monitored rack inside a public corridor must not turn the corridor
    # itself into a controlled-access room or obstruct either passage.
    if any(room in controlled for _, room in racks):
        raise AccessEvidenceError("Rack-only reader cannot gate a public room")
    if not isinstance(data["candidate_access_links"], list):
        raise AccessEvidenceError("Malformed candidate door capabilities")
    links = {link.id: link for link in model.access_links}
    options: dict[str, tuple[bool, bool]] = {}
    for row in data["candidate_access_links"]:
        if (not isinstance(row, dict)
                or set(row) != {"id", "motorised", "vacuum_seal"}
                or not isinstance(row["id"], str)
                or row["id"] not in links or row["id"] in options
                or type(row["motorised"]) is not bool
                or type(row["vacuum_seal"]) is not bool):
            raise AccessEvidenceError("Invalid candidate link flags")
        if (row["vacuum_seal"]
                and links[row["id"]].metadata.get("pressure_boundary") is not True):
            raise AccessEvidenceError("Vacuum seal needs a rated boundary")
        options[row["id"]] = (row["motorised"], row["vacuum_seal"])
    return AccessMonitoringPlan(
        topology_version=model.model_version,
        controlled_spaces=frozenset(controlled),
        rack_reader_candidates=tuple(racks),
        candidate_link_options=options,
    )


def _field(row: Any, key: str) -> Any:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _link_ids(ids: Iterable[str], known: Mapping[str, Any], name: str
              ) -> frozenset[str]:
    if isinstance(ids, (str, bytes)):
        raise AccessEvidenceError(f"{name} must be a collection")
    try:
        result = frozenset(ids)
    except (TypeError, ValueError) as exc:
        raise AccessEvidenceError(f"Invalid {name}") from exc
    if any(not isinstance(link_id, str) or link_id not in known
           for link_id in result):
        raise AccessEvidenceError(f"{name} contains an unknown link")
    return result


def project_access_page(
    records: Iterable[Any],
    model: ShipWorldModel,
    plan: AccessMonitoringPlan,
    *,
    observed_links: Iterable[str],
    identity_links: Iterable[str] = (),
    after_sequence: int = 0,
    max_scan: int = 128,
) -> dict:
    """Project a bounded *internal* page from committed world events.

    observed_links must originate from world-verified delivery, not client
    query parameters. identity_links additionally requires fitted identification
    instruments. Public principal access, scope binding and opaque cursors are
    separate later work; do not expose the numeric scan cursor to a player.
    The cursor advances over unseen events too, avoiding replay gaps and
    duplicate effects when a page is mostly filtered.
    """
    if (type(after_sequence) is not int or after_sequence < 0
            or type(max_scan) is not int or not 1 <= max_scan <= 128):
        raise AccessEvidenceError("Invalid access cursor or page limit")
    if plan.topology_version != model.model_version:
        raise AccessEvidenceError("Monitoring plan is for another ship topology")
    links = {link.id: link for link in model.access_links}
    allowed = _link_ids(observed_links, links, "Observed links")
    identity = _link_ids(identity_links, links, "Identity reader links")
    if not identity <= allowed or not identity <= plan.controlled_links(model):
        raise AccessEvidenceError("Identity source is not verified and controlled")

    rows = sorted(
        (row for row in records
         if type(_field(row, "sequence")) is int
         and _field(row, "sequence") > after_sequence),
        key=lambda row: _field(row, "sequence"),
    )
    has_more = len(rows) > max_scan
    page = rows[:max_scan]
    next_sequence = page[-1].sequence if (page and not isinstance(page[-1], Mapping)) else (
        page[-1]["sequence"] if page else after_sequence)
    output: list[dict] = []
    seen: set[int] = set()
    for row in page:
        seq = _field(row, "sequence")
        if seq in seen:
            continue
        seen.add(seq)
        source = _field(row, "operation")
        component = _field(row, "component_key")
        time = _field(row, "game_time")
        before = _field(row, "before")
        after = _field(row, "after")
        if (source not in EVENT_SOURCES or not isinstance(component, str)
                or not component.startswith("access:")
                or type(time) not in (int, float) or not math.isfinite(time)
                or not isinstance(before, Mapping)
                or not isinstance(after, Mapping)):
            continue
        link_id = component.removeprefix("access:")
        if link_id not in allowed:
            continue
        link = links[link_id]
        item = {
            "source_event_id": str(seq),
            "source_type": source,
            "access_link_id": link_id,
            "game_time": float(time),
        }
        if source == "crew_hatch":
            old = before.get("setting")
            new = after.get("setting")
            if old not in {"open", "closed"} or new not in {"open", "closed"} or old == new:
                continue  # A receipted no-op is not a door transition.
            if after.get("requested_value") != new:
                continue
            item.update({"kind": "hatch_change", "setting_before": old,
                         "setting_after": new})
        else:
            origin = before.get("space_id")
            destination = after.get("space_id")
            if (origin, destination) == (link.from_id, link.to_id):
                direction = "forward"
            elif (origin, destination) == (link.to_id, link.from_id):
                direction = "reverse"
            else:
                continue  # Do not infer an arrival from the wrong link.
            item.update({
                "kind": "arrival" if source == "crew_indexed_transfer_complete"
                        else "passage",
                "from_space": origin,
                "to_space": destination,
                "direction": direction,
            })
        actor = _field(row, "actor_dbref")
        if link_id in identity and isinstance(actor, str) and actor:
            item["actor_dbref"] = actor
        output.append(item)
    return {
        "events": output,
        "next_after_sequence": next_sequence,
        "has_more": has_more,
    }


def internal_access_page(
    model: ShipWorldModel,
    plan: AccessMonitoringPlan,
    *,
    observed_links: Iterable[str],
    identity_links: Iterable[str] = (),
    after_sequence: int = 0,
    max_scan: int = 128,
) -> dict:
    """Read committed Evennia events for an already world-verified scope.

    Internal engineering integration only. A future authenticated principal
    must bind scope and cursor to its identity and persist event delivery.
    """
    from world.models import CanonicalShipEvent

    if type(after_sequence) is not int or after_sequence < 0:
        raise AccessEvidenceError("Invalid access cursor")
    rows = list(CanonicalShipEvent.objects.filter(
        operation__in=EVENT_SOURCES, sequence__gt=after_sequence
    ).order_by("sequence")[:max_scan + 1])
    return project_access_page(
        rows, model, plan, observed_links=observed_links,
        identity_links=identity_links, after_sequence=after_sequence,
        max_scan=max_scan,
    )
