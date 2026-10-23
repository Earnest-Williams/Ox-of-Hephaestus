#!/usr/bin/env python3
"""Deterministic, design-reference coupled atmosphere/damage-control simulator.

This is NOT a live Evennia system. Nominal gas volumes, rates, samples,
crew placements and hardware conditions are explicit test assumptions.
No operation changes the authored ship, handler knowledge or actual world.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import isfinite, isclose, sqrt
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
P_REF_KPA = 101.325
T_REF_K = 293.15
AIR_CP_KJ_KG_K = 1.005
REF_O2_MOLAR = 0.21
O2_MOLAR_KG = 0.031998
# Other dry air is an effective mixture, not pure nitrogen.
OTHER_MOLAR_KG = (0.0289652 - REF_O2_MOLAR * O2_MOLAR_KG) / (1 - REF_O2_MOLAR)
MAX_SAMPLE_AGE_S = 10.0
MAX_SAMPLE_MASS_CHANGE_FRACTION = 0.002
MAX_CREW = 40


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def positive(value: float, what: str, *, allow_zero: bool = False) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and isfinite(value) and (value >= 0 if allow_zero else value > 0),
            "invalid " + what)
    return float(value)


def load_model() -> tuple[dict, dict, dict]:
    def read(name):
        return json.loads((HERE / name).read_text(encoding="utf-8"))
    return (read("pressure_zone_topology_v0.5.json"),
            read("pressure_gas_recovery_v0.5.json"),
            read("environmental_access_boundaries_v0.5.json"))


@dataclass
class GasCell:
    id: str
    free_volume_m3: float
    gas_kg: float
    oxygen_kg: float
    trace_kg: float = 0.0
    temperature_K: float = T_REF_K
    sampled_temperature_K: float | None = None
    sampled_oxygen_kg: float | None = None
    sampled_at_s: float | None = None
    sampled_gas_kg: float | None = None
    sampled_trace_kg: float | None = None
    unknown_exposure: bool = False
    crew: int = 0
    crew_unsafe_seconds: float = 0.0

    @property
    def pressure_kpa(self) -> float:
        # Lumped ideal-gas reference; thermal/fuel model updates temperature.
        return (P_REF_KPA * self.gas_kg / (1.204118 * self.free_volume_m3)
                * self.temperature_K / T_REF_K)

    @property
    def oxygen_partial_kpa(self) -> float:
        if self.gas_kg <= 0:
            return 0.0
        o2_moles = self.oxygen_kg / O2_MOLAR_KG
        other_moles = max(0.0, self.gas_kg - self.oxygen_kg) / OTHER_MOLAR_KG
        return self.pressure_kpa * o2_moles / (o2_moles + other_moles)

    def modeled_unsuited_air_safe(self) -> bool:
        return (not self.unknown_exposure
                and 80.0 <= self.pressure_kpa <= 120.0
                and 16.0 <= self.oxygen_partial_kpa <= 26.0
                and 278.15 <= self.temperature_K <= 313.15
                and self.trace_kg <= 1e-5 * max(self.gas_kg, 0.0))

    def fresh_observation(self, now_s: float) -> bool:
        if self.sampled_at_s is None or self.unknown_exposure:
            return False
        return (0 <= now_s - self.sampled_at_s <= MAX_SAMPLE_AGE_S
                and self.sampled_gas_kg is not None
                and abs(self.gas_kg - self.sampled_gas_kg)
                <= MAX_SAMPLE_MASS_CHANGE_FRACTION * max(self.sampled_gas_kg, 1.0)
                and self.sampled_trace_kg is not None
                and abs(self.trace_kg - self.sampled_trace_kg) <= 1e-9
                and self.sampled_temperature_K is not None
                and abs(self.temperature_K - self.sampled_temperature_K) <= 1.0
                and self.sampled_oxygen_kg is not None
                and abs(self.oxygen_kg - self.sampled_oxygen_kg)
                    <= 0.002 * max(self.sampled_oxygen_kg, 1.0))


@dataclass
class Gate:
    id: str
    a: str | None
    b: str | None
    kind: str
    state: str = "closed"   # closed / open / jammed_open / jammed_closed
    open_flow_kg_s: float = 35.0
    diffusion_exchange_kg_s: float = 0.25

    def is_open(self) -> bool:
        return self.state in ("open", "jammed_open")


@dataclass
class Breach:
    id: str
    cell_id: str
    full_pressure_loss_kg_s: float
    active: bool = True


class PressureDamageTrial:
    """A diagnostic trial, not an actuator command, permission oracle or world DB."""

    def __init__(self, topology: dict, gas: dict, environmental: dict,
                 volume_basis: str = "midpoint"):
        require(volume_basis in ("lower", "midpoint", "upper"),
                "unrecognized reference free-volume basis")
        require(len(topology["pressure_cells"]) == 133
                and len(topology["pressure_boundary_doors"]) == 339
                and len(gas["sized_and_unsized_pressure_cells"]) == 133
                and len(environmental["doors"]) == 131,
                "wrong or incomplete registered ship geometry")
        cells = {r["id"]: r for r in topology["pressure_cells"]}
        estimates = {r["pressure_zone_id"]: r
                     for r in gas["sized_and_unsized_pressure_cells"]}
        require(len(cells) == len(estimates) == 133
                and set(cells) == set(estimates),
                "duplicate or differently identified gas cells")
        density = gas["reference_gas"]["density_kg_m3"]
        require(isclose(density, 1.204118, abs_tol=1e-6)
                and isclose(gas["reference_gas"]["oxygen_mass_fraction_approx"],
                            0.232, abs_tol=1e-6), "unexpected reference air mix")
        self.volume_basis = volume_basis
        self.cells: dict[str, GasCell] = {}
        for key, row in estimates.items():
            require(row["verified_as_installed_free_gas_m3"] is None
                    and cells[key]["actual_usable_free_air_m3"] is None,
                    "design-reference trial given invented as-installed survey")
            lo = positive(row["design_free_gas_lower_m3"], key + " lower volume")
            hi = positive(row["design_free_gas_upper_m3"], key + " upper volume")
            require(lo <= hi and row["source_gross_envelope_m3"]
                    == cells[key]["gross_reference_envelope_m3"],
                    "mismatched compartment volume " + key)
            vol = {"lower": lo, "midpoint": (lo + hi) / 2, "upper": hi}[volume_basis]
            mass = vol * density
            self.cells[key] = GasCell(key, vol, mass, mass * 0.232)

        schedule = {x["access_link_id"] for x in environmental["doors"]}
        require(len(schedule) == 131, "duplicate unclassified receiver schedule")
        self.gates: dict[str, Gate] = {}
        self.unknown_gate_ids: set[str] = set()
        for row in topology["pressure_boundary_doors"]:
            key = row["id"]
            require(key not in self.gates, "duplicate physical pressure gate")
            a, b = row["from_pressure_zone_id"], row["to_pressure_zone_id"]
            require(a != b and a in (set(self.cells) | {None, "VACUUM"})
                    and b in (set(self.cells) | {None, "VACUUM"}),
                    "nonphysical pressure-boundary endpoints " + key)
            require(a in self.cells or b in self.cells,
                    "pressure-boundary has no simulated crew-side gas cell")
            if a is None or b is None:
                require((a is None) != (b is None) and key in schedule,
                        "unregistered unknown-environment threshold " + key)
                self.unknown_gate_ids.add(key)
            else:
                require(key not in schedule,
                        "unknown-environment access schedule incorrectly assigned")
            # Cold-isolated initial condition is explicit. Authoring 'open' and
            # 'closed_or_auto' are NOT evidence of the present installed state.
            self.gates[key] = Gate(key, a, b, row.get("kind", "unclassified"))
        require(len(self.gates) == 339 and self.unknown_gate_ids == schedule,
                "registered 131 hazardous thresholds or 339 gates lost")
        require(len(topology["unassigned_pressure_zone_space_ids"]) == 83,
                "unclassified cargo spaces may not become gas reservoirs")

        banks = gas["reserve_gas"]["banks"]
        self.bank_kg = {b["inventory_id"]: b["mass_t"] * 1000 for b in banks}
        require(set(self.bank_kg) == {"INV-GAS-REFILL-A", "INV-GAS-REFILL-B"}
                and len(banks) == 2
                and all(isclose(x, 2750.0) for x in self.bank_kg.values()),
                "two independent reserve-gas banks missing")
        self.bank_outlet_open = {x: False for x in self.bank_kg}
        self.refill_rate_kg_h = positive(
            gas["reserve_gas"]["maximum_simultaneous_controlled_flow_kg_h_from_two_banks"],
            "refill delivery rate")
        self.time_s = 0.0
        self.breaches: dict[str, Breach] = {}
        self.lost_to_vacuum_kg = 0.0
        self.lost_oxygen_kg = 0.0
        self.events: list[dict] = []
        self.initial_system_gas_kg = self.accounted_mass_kg()

    def event(self, kind: str, **values) -> None:
        self.events.append({"at_s": round(self.time_s, 3), "kind": kind, **values})

    def sample_local(self, cell_id: str, *, qualified_local_probe: bool) -> None:
        require(qualified_local_probe is True, "local sensor proof missing")
        c = self.cells[cell_id]
        require(not c.unknown_exposure,
                "unknown medium requires an external measurement/reinitialisation")
        c.sampled_at_s = self.time_s
        c.sampled_gas_kg = c.gas_kg
        c.sampled_trace_kg = c.trace_kg
        c.sampled_temperature_K = c.temperature_K
        c.sampled_oxygen_kg = c.oxygen_kg
        self.event("sample_local", cell=cell_id)

    def may_enter_unsuited(self, cell_id: str) -> bool:
        c = self.cells[cell_id]
        return c.modeled_unsuited_air_safe() and c.fresh_observation(self.time_s)

    def can_open(self, gate_id: str, *, local_authority: bool,
                 transfer_interlocks_proven: bool = False,
                 freight_permit_proven: bool = False) -> tuple[bool, str]:
        g = self.gates[gate_id]
        if local_authority is not True:
            return False, "local_authority_not_proven"
        if g.state in ("jammed_closed", "jammed_open"):
            return False, "gate_mechanically_failed"
        if g.a not in self.cells or g.b not in self.cells:
            return False, "unknown_or_vacuum_requires_separate_transfer"
        # Pressure equality does not index a rotating drum or hard-lock an
        # engineering freight collar. The witness is separate from air.
        rotating = {"indexed_rotary_transfer", "indexed_freight_transfer",
                    "indexer_hatch", "heavy_rotor_freight_lock"}
        freight = {"indexed_freight_transfer", "heavy_rotor_freight_lock",
                   "freight_pressure_shutter", "freight_branch_tunnel"}
        if g.kind in rotating and transfer_interlocks_proven is not True:
            return False, "rotor_capture_and_drive_inhibit_unproven"
        if g.kind in freight and freight_permit_proven is not True:
            return False, "heavy_freight_transfer_permit_unproven"
        a, b = self.cells[g.a], self.cells[g.b]
        if not a.fresh_observation(self.time_s) or not b.fresh_observation(self.time_s):
            return False, "local_samples_unverified_or_stale"
        if abs(a.pressure_kpa - b.pressure_kpa) > 2.0:
            return False, "differential_pressure_over_2kpa"
        if not a.modeled_unsuited_air_safe() or not b.modeled_unsuited_air_safe():
            return False, "atmosphere_not_compatible_for_unsuited_access"
        return True, "nominal_reference_permission_only"

    def open_gate(self, gate_id: str, *, local_authority: bool,
                  transfer_interlocks_proven: bool = False,
                  freight_permit_proven: bool = False) -> bool:
        g = self.gates[gate_id]
        allowed, reason = self.can_open(
            gate_id, local_authority=local_authority,
            transfer_interlocks_proven=transfer_interlocks_proven,
            freight_permit_proven=freight_permit_proven)
        self.event("open_gate_requested", gate=gate_id, allowed=allowed, reason=reason)
        if allowed and g.state == "closed":
            g.state = "open"
        return allowed

    def fail_gate_open(self, gate_id: str) -> None:
        g = self.gates[gate_id]
        g.state = "jammed_open"
        self.event("mechanical_gate_failure", gate=gate_id, state=g.state)
        self._propagate_unknown_exposure()

    def fail_gate_closed(self, gate_id: str) -> None:
        g = self.gates[gate_id]
        require(not g.is_open(), "jammed-closed fault cannot shut an open moving hatch")
        g.state = "jammed_closed"
        self.event("mechanical_gate_failure", gate=gate_id, state=g.state)

    def close_gate(self, gate_id: str) -> bool:
        g = self.gates[gate_id]
        if g.state == "jammed_open":
            self.event("closure_failed", gate=gate_id)
            return False
        if g.state != "jammed_closed":
            g.state = "closed"
        self.event("closure_confirmed", gate=gate_id, state=g.state)
        return True

    def isolate_zone(self, cell_id: str) -> dict[str, list[str]]:
        require(cell_id in self.cells, "cannot isolate unmodelled atmosphere")
        closed, failed = [], []
        for gate in self.gates.values():
            if cell_id in (gate.a, gate.b):
                (closed if self.close_gate(gate.id) else failed).append(gate.id)
        self.event("zone_isolation", zone=cell_id, closed=len(closed), jammed=failed)
        return {"closed": closed, "failed": failed}

    def breach(self, breach_id: str, cell_id: str,
               full_pressure_loss_kg_s: float) -> None:
        require(breach_id not in self.breaches and cell_id in self.cells,
                "duplicate breach or nonexistent crew pressure cell")
        rate = positive(full_pressure_loss_kg_s, "hull breach loss rate")
        self.breaches[breach_id] = Breach(breach_id, cell_id, rate)
        self.event("hull_breach_to_vacuum", breach=breach_id,
                   zone=cell_id, design_loss_rate_kg_s=rate)

    def seal_breach(self, breach_id: str, *, repair_verified: bool) -> None:
        require(repair_verified is True, "unverified hull patch is not sealed")
        require(breach_id in self.breaches and self.breaches[breach_id].active,
                "no active repairable breach")
        self.breaches[breach_id].active = False
        self.event("leak_isolated_and_verified", breach=breach_id)

    def mark_contaminated(self, cell_id: str, trace_kg: float) -> None:
        c = self.cells[cell_id]
        amount = positive(trace_kg, "contamination-tracer mass")
        require(amount <= c.gas_kg - c.oxygen_kg - c.trace_kg,
                "cannot manufacture contaminant mass")
        # Convert existing carrier-gas fraction to contaminated material.
        c.trace_kg += amount
        self.event("carrier_gas_contamination", cell=cell_id, tracer_kg=amount)

    def set_crew(self, cell_id: str, count: int) -> None:
        require(type(count) is int and 0 <= count <= MAX_CREW
                and sum(c.crew for c in self.cells.values())
                - self.cells[cell_id].crew + count <= MAX_CREW,
                "invalid 40-person ship-crew placement")
        self.cells[cell_id].crew = count

    def traversable_zones(self, start: str) -> set[str]:
        if not self.may_enter_unsuited(start):
            return set()
        reached = {start}
        queue = deque([start])
        by_zone: dict[str, list[str]] = defaultdict(list)
        for gate in self.gates.values():
            if gate.is_open() and gate.a in self.cells and gate.b in self.cells:
                by_zone[gate.a].append(gate.b)
                by_zone[gate.b].append(gate.a)
        while queue:
            for dest in by_zone[queue.popleft()]:
                if dest not in reached and self.may_enter_unsuited(dest):
                    reached.add(dest)
                    queue.append(dest)
        return reached

    def _propagate_unknown_exposure(self) -> None:
        # A forced-open hatch to an unclassified cargo/process receiver is
        # NOT a vacuum sink: its pressure, volume and composition are unknown.
        affected = set()
        for g in self.gates.values():
            if g.is_open() and (g.a is None or g.b is None):
                known = g.b if g.a is None else g.a
                if known in self.cells:
                    affected.add(known)
        # Contamination/pressure uncertainty spreads through opened known
        # gates; it cannot be reclassified safe by inspecting a design JSON.
        affected |= {id for id, c in self.cells.items() if c.unknown_exposure}
        changed = True
        while changed:
            changed = False
            for g in self.gates.values():
                if g.is_open() and g.a in self.cells and g.b in self.cells:
                    if (g.a in affected) != (g.b in affected):
                        affected.update((g.a, g.b))
                        changed = True
        for id in affected:
            self.cells[id].unknown_exposure = True

    @staticmethod
    def _flow_kg(source_p: float, sink_p: float,
                 nominal_flow_kg_s: float, dt_s: float) -> float:
        if source_p <= sink_p or source_p <= 0:
            return 0.0
        # Deliberately lumped, isothermal reference orifice: approaches
        # choked flow at large pressure ratios and scales with upstream P.
        ratio = min(1.0, sqrt(2.0 * (source_p - sink_p) / source_p))
        return nominal_flow_kg_s * (source_p / P_REF_KPA) * ratio * dt_s

    def _move_mass(self, source: GasCell, receiver: GasCell | None,
                   wanted_kg: float) -> None:
        """Move an actual parcel of mass/species or vent it to known vacuum."""
        mass = min(max(wanted_kg, 0.0), source.gas_kg)
        if mass <= 0:
            return
        oxygen = mass * source.oxygen_kg / source.gas_kg
        trace = mass * source.trace_kg / source.gas_kg
        old_receiver_mass = receiver.gas_kg if receiver is not None else 0.0
        parcel_temperature = source.temperature_K
        source.gas_kg = max(0.0, source.gas_kg - mass)
        source.oxygen_kg = max(0.0, source.oxygen_kg - oxygen)
        source.trace_kg = max(0.0, source.trace_kg - trace)
        if receiver is None:
            self.lost_to_vacuum_kg += mass
            self.lost_oxygen_kg += oxygen
        else:
            receiver.temperature_K = ((old_receiver_mass * receiver.temperature_K
                + mass * parcel_temperature) / (old_receiver_mass + mass))
            receiver.gas_kg += mass
            receiver.oxygen_kg += oxygen
            receiver.trace_kg += trace

    @staticmethod
    def _exchange_constituents(a: GasCell, b: GasCell,
                               mass_equivalent: float) -> None:
        """Conservative equal-gross-mass bidirectional gas exchange."""
        if mass_equivalent <= 0 or a.gas_kg <= 0 or b.gas_kg <= 0:
            return
        x = min(mass_equivalent, 0.25 * a.gas_kg, 0.25 * b.gas_kg)
        oxygen_a, oxygen_b = a.oxygen_kg / a.gas_kg, b.oxygen_kg / b.gas_kg
        trace_a, trace_b = a.trace_kg / a.gas_kg, b.trace_kg / b.gas_kg
        old_a_K, old_b_K = a.temperature_K, b.temperature_K
        oxygen_difference = x * (oxygen_b - oxygen_a)
        trace_difference = x * (trace_b - trace_a)
        a.oxygen_kg += oxygen_difference
        b.oxygen_kg -= oxygen_difference
        a.trace_kg += trace_difference
        b.trace_kg -= trace_difference
        a.temperature_K += x / a.gas_kg * (old_b_K - old_a_K)
        b.temperature_K += x / b.gas_kg * (old_a_K - old_b_K)

    def _step(self, dt: float) -> None:
        self._propagate_unknown_exposure()
        # Evaluate pairs sequentially against their CURRENT masses.
        # For every connected pair, cap its transfer at their equal-pressure
        # mass. The previous simultaneous explicit Euler scheme allowed
        # an enormous 35 kg/s hatch to overshoot a tiny BR-03 bridge cell,
        # spuriously pushing HAB-04 above 1 atm during a leak-only casualty.
        # This pairwise limiter preserves the pressure maximum principle.
        for gate_id in sorted(self.gates):
            g = self.gates[gate_id]
            if not g.is_open() or g.a is None or g.b is None:
                continue  # null receiver never modeled as vacuum
            a, b = self.cells.get(g.a), self.cells.get(g.b)
            if a is not None and b is not None:
                pa, pb = a.pressure_kpa, b.pressure_kpa
                if pa > pb:
                    donor, receiver, p_high, p_low = a, b, pa, pb
                elif pb > pa:
                    donor, receiver, p_high, p_low = b, a, pb, pa
                else:
                    donor = receiver = None
                if donor is not None:
                    requested = self._flow_kg(
                        p_high, p_low, g.open_flow_kg_s, dt)
                    # Pressure equalisation must also respect the hot donor
                    # gas's enthalpy as the receiver warms during transfer.
                    equalising_mass = (
                        donor.gas_kg * donor.temperature_K * receiver.free_volume_m3
                        - receiver.gas_kg * receiver.temperature_K * donor.free_volume_m3
                    ) / (donor.temperature_K *
                         (donor.free_volume_m3 + receiver.free_volume_m3))
                    self._move_mass(donor, receiver,
                                    min(requested, max(equalising_mass, 0.0)))
                # Composition still mixes through a hatch at equal P.
                self._exchange_constituents(
                    a, b, g.diffusion_exchange_kg_s * dt)
            else:
                live = a if a is not None else b
                if live is not None and "VACUUM" in (g.a, g.b):
                    p = live.pressure_kpa
                    self._move_mass(live, None, self._flow_kg(
                        p, 0.0, g.open_flow_kg_s, dt))
        for breach_id in sorted(self.breaches):
            breach = self.breaches[breach_id]
            if breach.active:
                cell = self.cells[breach.cell_id]
                self._move_mass(cell, None,
                                breach.full_pressure_loss_kg_s
                                * (cell.pressure_kpa / P_REF_KPA) * dt)
        for c in self.cells.values():
            require(c.gas_kg >= -1e-8
                    and c.oxygen_kg >= -1e-8
                    and c.trace_kg >= -1e-8
                    and c.oxygen_kg + c.trace_kg <= c.gas_kg + 1e-7,
                    "species/material ledger underflow")
            if not c.modeled_unsuited_air_safe():
                c.crew_unsafe_seconds += c.crew * dt
        self.time_s += dt

    def advance(self, seconds: float, *, integration_step_s: float = 1.0) -> None:
        remaining = positive(seconds, "simulation elapsed time")
        step = positive(integration_step_s, "integration step")
        require(step <= 1.0, "reference casualty integration step exceeds 1 s")
        while remaining > 1e-9:
            dt = min(step, remaining)
            self._step(dt)
            remaining -= dt
        require(self.mass_balance_error_kg() < 1e-5,
                "pressure-breach simulator creates or destroys gas mass")

    def open_pressure_component(self, start: str) -> set[str]:
        """Pressure-coupled gas cells, independent of permission to walk."""
        require(start in self.cells, "unknown starting pressure cell")
        seen = {start}
        pending = deque([start])
        graph: dict[str, set[str]] = defaultdict(set)
        for g in self.gates.values():
            if g.is_open() and g.a in self.cells and g.b in self.cells:
                graph[g.a].add(g.b)
                graph[g.b].add(g.a)
        while pending:
            for adjacent in graph[pending.popleft()]:
                if adjacent not in seen:
                    seen.add(adjacent)
                    pending.append(adjacent)
        return seen

    def set_bank_outlet(self, inventory_id: str, open_state: bool,
                        *, local_authority: bool) -> None:
        require(inventory_id in self.bank_kg
                and type(open_state) is bool and local_authority is True,
                "bank valve cannot be operated without known equipment/authority")
        self.bank_outlet_open[inventory_id] = open_state
        self.event("bank_isolation_valve", bank=inventory_id, opened=open_state)

    def pump_replacement_air(self, inventory_id: str, zone: str, seconds: float,
                             *, path_locally_proven: bool,
                             receiving_chemistry_verified: bool) -> float:
        duration = positive(seconds, "replenishment duration")
        require(inventory_id in self.bank_kg and zone in self.cells,
                "invalid replenishment inventory or destination")
        cell = self.cells[zone]
        coupled = self.open_pressure_component(zone)
        require(self.bank_outlet_open[inventory_id]
                and path_locally_proven is True
                and receiving_chemistry_verified is True
                and cell.fresh_observation(self.time_s)
                and all(not self.cells[id].unknown_exposure for id in coupled)
                and cell.trace_kg <= 1e-5 * max(cell.gas_kg, 0),
                "replenishment lacks proven valve route, sample or known receiver")
        require(not any(b.active and b.cell_id in coupled
                        for b in self.breaches.values()),
                "refill path still connects to an active hull breach")
        require(not any(g.is_open() and (
                    (g.a in coupled and g.b not in self.cells) or
                    (g.b in coupled and g.a not in self.cells))
                    for g in self.gates.values()),
                "refill path still exposed to vacuum or unknown receiver")
        target = 1.204118 * cell.free_volume_m3
        needed = max(0.0, target - cell.gas_kg)
        quantity = min(needed, self.bank_kg[inventory_id],
                       duration * self.refill_rate_kg_h / 3600.0)
        require(quantity > 0, "empty bank or cell already at nominal pressure")
        # Ledger-averaged delivery over a declared duration, NOT an actuator
        # transient or an assertion of current pipe availability.
        self.bank_kg[inventory_id] -= quantity
        cell.gas_kg += quantity
        cell.oxygen_kg += quantity * 0.232
        self.time_s += duration
        self.event("replacement_air_metered", bank=inventory_id,
                   zone=zone, transferred_kg=round(quantity, 4),
                   nominal_elapsed_s=duration)
        require(self.mass_balance_error_kg() < 1e-5,
                "gas inventory manufactured during replenishment")
        return quantity

    def accounted_mass_kg(self) -> float:
        return (sum(c.gas_kg for c in self.cells.values())
                + sum(self.bank_kg.values()) + self.lost_to_vacuum_kg)

    def mass_balance_error_kg(self) -> float:
        return abs(self.accounted_mass_kg() - self.initial_system_gas_kg)

    def summary(self, ids: list[str]) -> dict:
        require(all(x in self.cells for x in ids), "summary requests unknown cell")
        return {
            "time_s": round(self.time_s, 3),
            "volume_assumption": self.volume_basis + "_design_free_air_not_surveyed",
            "vented_to_confirmed_vacuum_kg": round(self.lost_to_vacuum_kg, 3),
            "bank_remaining_kg": {k: round(v, 3) for k, v in self.bank_kg.items()},
            "gas_mass_balance_error_kg": round(self.mass_balance_error_kg(), 8),
            "cells": {id: {
                "temperature_reference_C": (None if self.cells[id].unknown_exposure
                    else round(self.cells[id].temperature_K - 273.15, 3)),
                "pressure_reference_kpa": (None if self.cells[id].unknown_exposure
                    else round(self.cells[id].pressure_kpa, 3)),
                "oxygen_partial_reference_kpa": (None if self.cells[id].unknown_exposure
                    else round(self.cells[id].oxygen_partial_kpa, 3)),
                "unsuited_access_allowed": self.may_enter_unsuited(id),
                "unclassified_receiver_exposure": self.cells[id].unknown_exposure,
                "crew_person_seconds_in_unsafe_reference_air":
                    round(self.cells[id].crew_unsafe_seconds, 2),
            } for id in ids},
        }
