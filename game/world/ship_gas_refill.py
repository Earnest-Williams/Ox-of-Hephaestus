"""G19 casualty repressurisation from the two fitted compressed-air banks.

The v0.5 ship carries two 2.75 t dry breathable-air reserves (`INV-GAS-REFILL-A`
at `WATER-SHIELD-FWD`, `INV-GAS-REFILL-B` at `STORE-FLUID-AFT`). Each feeds one
pressure-qualified regulator (`GAS-REFILL-REG-A` at `ENV-FWD`, `-B` at
`ENV-AFT`) rated at 100 kg/h, then the authored `repressurization_gas` network
of headers, rotary unions, HAB manifolds and pressure-cell taps.

This library is pure. It owns only the metering jobs and their audit history.
The Evennia world owns the bank inventories, valve and equipment state, crew
position and authority, cell gas and the conservation balance. Nothing here
creates gas: every kilogram delivered is debited from a finite bank by the
caller, and a job never meters past its setpoint or the bank's remaining stock.
"""

from __future__ import annotations

import copy
import math
from collections import deque
from collections.abc import Iterable, Mapping
from typing import Final, TypedDict, cast


class GasRefillError(ValueError):
    """Bad, inconsistent or nonphysical refill state or request."""


class RegulatorSpec(TypedDict):
    bank_equipment: str
    regulator_equipment: str
    inventory: str
    station: str
    bank_node: str


class RefillJob(TypedDict):
    cell: str
    setpoint_pa: float
    actor: str
    request_id: str
    started_s: float
    delivered_kg: float


class RefillRecord(TypedDict):
    bank: str
    cell: str
    setpoint_pa: float
    actor: str
    request_id: str
    started_s: float
    ended_s: float
    delivered_kg: float
    reason: str


class RefillLedger(TypedDict):
    commissioned_kg: dict[str, float]
    delivered_kg: dict[str, float]
    jobs: dict[str, RefillJob]
    history: list[RefillRecord]


class RouteEdge(TypedDict):
    a: str
    b: str
    conducts: bool


REGULATORS: Final[dict[str, RegulatorSpec]] = {
    "A": {
        "bank_equipment": "GAS-REFILL-BANK-A",
        "regulator_equipment": "GAS-REFILL-REG-A",
        "inventory": "INV-GAS-REFILL-A",
        "station": "ENV-FWD",
        "bank_node": "NODE-GAS-BANK-A",
    },
    "B": {
        "bank_equipment": "GAS-REFILL-BANK-B",
        "regulator_equipment": "GAS-REFILL-REG-B",
        "inventory": "INV-GAS-REFILL-B",
        "station": "ENV-AFT",
        "bank_node": "NODE-GAS-BANK-B",
    },
}
NETWORK: Final[str] = "repressurization_gas"
RATED_KG_S: Final[float] = 100.0 / 3600.0
OXYGEN_MASS_FRACTION: Final[float] = 0.232
SUPPLY_TEMPERATURE_K: Final[float] = 293.15
R_SPECIFIC_AIR: Final[float] = 287.05
MIN_SETPOINT_PA: Final[float] = 50_000.0
MAX_SETPOINT_PA: Final[float] = 103_000.0
MAX_BANK_KG: Final[float] = 2_750.0
MAX_HISTORY: Final[int] = 32
EPS_KG: Final[float] = 1e-7
STOP_REASONS: Final[frozenset[str]] = frozenset(
    {
        "operator_stop",
        "setpoint_reached",
        "bank_exhausted",
        "downstream_leak",
        "route_lost",
        "regulator_unserviceable",
        "bank_unserviceable",
        "cell_unverified",
    }
)
_LEDGER_KEYS: Final[frozenset[str]] = frozenset(
    {"commissioned_kg", "delivered_kg", "jobs", "history"}
)
_JOB_KEYS: Final[frozenset[str]] = frozenset(RefillJob.__annotations__)
_RECORD_KEYS: Final[frozenset[str]] = frozenset(RefillRecord.__annotations__)


def _number(
    value: object, *, positive: bool = False, maximum: float | None = None
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
        or (positive and value == 0)
        or (maximum is not None and value > maximum)
    ):
        raise GasRefillError("Nonphysical refill quantity")
    return float(value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise GasRefillError("Refill record lacks a required identity")
    return value


def initial_refill(bank_kg: Mapping[str, float]) -> RefillLedger:
    """Commission metering against the banks' current finite inventory."""
    if set(bank_kg) != set(REGULATORS):
        raise GasRefillError("Both fitted refill banks must be accounted for")
    commissioned: dict[str, float] = {
        bank: _number(kg, maximum=MAX_BANK_KG) for bank, kg in bank_kg.items()
    }
    ledger: RefillLedger = {
        "commissioned_kg": commissioned,
        "delivered_kg": {bank: 0.0 for bank in REGULATORS},
        "jobs": {},
        "history": [],
    }
    return validate_refill(ledger)


def validate_refill(raw: object) -> RefillLedger:
    """Check a persisted ledger and return it typed; never repair it."""
    if not isinstance(raw, dict) or set(raw) != _LEDGER_KEYS:
        raise GasRefillError("Invalid G19 refill ledger")
    commissioned: object = raw["commissioned_kg"]
    delivered: object = raw["delivered_kg"]
    jobs: object = raw["jobs"]
    history: object = raw["history"]
    if (
        not isinstance(commissioned, dict)
        or not isinstance(delivered, dict)
        or set(commissioned) != set(REGULATORS)
        or set(delivered) != set(REGULATORS)
    ):
        raise GasRefillError("Refill ledger must account for both banks")
    bank: str
    for bank in REGULATORS:
        start_kg: float = _number(commissioned[bank], maximum=MAX_BANK_KG)
        used_kg: float = _number(delivered[bank])
        if used_kg > start_kg + EPS_KG:
            raise GasRefillError("Refill delivered more gas than the bank held")
    if not isinstance(jobs, dict) or not set(jobs) <= set(REGULATORS):
        raise GasRefillError("Refill job is not bound to a fitted regulator")
    job: object
    for job in jobs.values():
        if not isinstance(job, dict) or set(job) != _JOB_KEYS:
            raise GasRefillError("Invalid refill metering job")
        if not _text(job["cell"]).startswith("PZ-"):
            raise GasRefillError("Refill job is not bound to a pressure cell")
        _number(job["setpoint_pa"], positive=True, maximum=MAX_SETPOINT_PA)
        _text(job["actor"])
        _text(job["request_id"])
        _number(job["started_s"])
        _number(job["delivered_kg"])
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise GasRefillError("Unbounded refill history")
    record: object
    for record in history:
        if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
            raise GasRefillError("Invalid refill history record")
        if record["bank"] not in REGULATORS or record["reason"] not in STOP_REASONS:
            raise GasRefillError("Refill history has an unknown bank or reason")
        if _number(record["ended_s"]) < _number(record["started_s"]):
            raise GasRefillError("Refill record ends before it starts")
        _number(record["delivered_kg"])
    return cast(RefillLedger, raw)


def bank_remaining_kg(ledger: RefillLedger, bank: str) -> float:
    """Remaining stock implied by the ledger; the world checks it against inventory."""
    if bank not in REGULATORS:
        raise GasRefillError("No such fitted refill bank")
    remaining: float = ledger["commissioned_kg"][bank] - ledger["delivered_kg"][bank]
    return max(0.0, remaining)


def reconciles_with_inventory(
    ledger: RefillLedger, bank: str, inventory_kg: float
) -> bool:
    """The bank inventory must equal commissioned stock minus metered delivery."""
    expected: float = bank_remaining_kg(ledger, bank)
    return math.isclose(expected, _number(inventory_kg), rel_tol=0, abs_tol=1e-6)


def mass_at_pressure(
    *, pressure_pa: float, volume_m3: float, temperature_k: float
) -> float:
    """Ideal-gas air mass for a cell at a given pressure."""
    p: float = _number(pressure_pa)
    v: float = _number(volume_m3, positive=True)
    t: float = _number(temperature_k, positive=True)
    return p * v / (R_SPECIFIC_AIR * t)


def deliverable_kg(
    *,
    mass_kg: float,
    volume_m3: float,
    temperature_k: float,
    setpoint_pa: float,
    bank_kg: float,
    seconds: float,
) -> float:
    """Mass one regulator may meter this substep: rate, stock and setpoint bound."""
    target_kg: float = mass_at_pressure(
        pressure_pa=setpoint_pa, volume_m3=volume_m3, temperature_k=temperature_k
    )
    shortfall_kg: float = target_kg - _number(mass_kg)
    if shortfall_kg <= EPS_KG:
        return 0.0
    rate_kg: float = RATED_KG_S * _number(seconds)
    return max(0.0, min(rate_kg, _number(bank_kg), shortfall_kg))


def start_refill(
    ledger: RefillLedger,
    *,
    bank: str,
    cell: str,
    setpoint_pa: float,
    actor: str,
    request_id: str,
    now_s: float,
) -> RefillLedger:
    """Open a metering job; the caller has already proved route, seal and authority."""
    validate_refill(ledger)
    if bank not in REGULATORS:
        raise GasRefillError("No such fitted refill regulator")
    if bank in ledger["jobs"]:
        raise GasRefillError("Regulator is already metering into a cell")
    if not cell.startswith("PZ-"):
        raise GasRefillError("Refill target must be a pressure cell")
    if not MIN_SETPOINT_PA <= _number(setpoint_pa) <= MAX_SETPOINT_PA:
        raise GasRefillError("Refill setpoint outside the regulator's rated range")
    if bank_remaining_kg(ledger, bank) <= EPS_KG:
        raise GasRefillError("Refill bank is exhausted")
    result: RefillLedger = copy.deepcopy(ledger)
    result["jobs"][bank] = {
        "cell": cell,
        "setpoint_pa": float(setpoint_pa),
        "actor": _text(actor),
        "request_id": _text(request_id),
        "started_s": _number(now_s),
        "delivered_kg": 0.0,
    }
    return validate_refill(result)


def record_delivery(ledger: RefillLedger, *, bank: str, kg: float) -> RefillLedger:
    """Account for gas the world has moved from a bank into the job's cell."""
    validate_refill(ledger)
    job: RefillJob | None = ledger["jobs"].get(bank)
    if job is None:
        raise GasRefillError("No active metering job for that regulator")
    mass: float = _number(kg)
    if mass > bank_remaining_kg(ledger, bank) + EPS_KG:
        raise GasRefillError("Delivery exceeds the bank's remaining stock")
    result: RefillLedger = copy.deepcopy(ledger)
    result["jobs"][bank]["delivered_kg"] += mass
    result["delivered_kg"][bank] += mass
    return validate_refill(result)


def stop_refill(
    ledger: RefillLedger, *, bank: str, reason: str, now_s: float
) -> RefillLedger:
    """Close a job and keep a bounded record of what it actually delivered."""
    validate_refill(ledger)
    if reason not in STOP_REASONS:
        raise GasRefillError("Unknown refill stop reason")
    job: RefillJob | None = ledger["jobs"].get(bank)
    if job is None:
        raise GasRefillError("No active metering job for that regulator")
    ended_s: float = max(_number(now_s), job["started_s"])
    result: RefillLedger = copy.deepcopy(ledger)
    del result["jobs"][bank]
    record: RefillRecord = {
        "bank": bank,
        "cell": job["cell"],
        "setpoint_pa": job["setpoint_pa"],
        "actor": job["actor"],
        "request_id": job["request_id"],
        "started_s": job["started_s"],
        "ended_s": ended_s,
        "delivered_kg": job["delivered_kg"],
        "reason": reason,
    }
    result["history"] = (result["history"] + [record])[-MAX_HISTORY:]
    return validate_refill(result)


def reachable_cells(
    *,
    start_node: str,
    edges: Iterable[RouteEdge],
    blocked_nodes: frozenset[str],
    node_cells: Mapping[str, str],
) -> frozenset[str]:
    """Cells a bank can feed through conducting pipework.

    Gas lines pass flow either way, so conducting edges are undirected. A node
    owned by unserviceable equipment blocks all flow through it. The start node
    must itself be serviceable.
    """
    if start_node in blocked_nodes:
        return frozenset()
    adjacency: dict[str, list[str]] = {}
    edge: RouteEdge
    for edge in edges:
        if not edge["conducts"]:
            continue
        if edge["a"] in blocked_nodes or edge["b"] in blocked_nodes:
            continue
        adjacency.setdefault(edge["a"], []).append(edge["b"])
        adjacency.setdefault(edge["b"], []).append(edge["a"])
    seen: set[str] = {start_node}
    pending: deque[str] = deque([start_node])
    while pending:
        node: str = pending.popleft()
        neighbour: str
        for neighbour in adjacency.get(node, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                pending.append(neighbour)
    return frozenset(node_cells[n] for n in seen if n in node_cells)
