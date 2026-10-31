# Preparatory world read model — ox.world.read/1

**Status (31 October 2026): typed contract only; not an endpoint.**
Shared Pydantic v2 models: `ox_contracts.world_read_model`. Nothing in this
contract authorizes a database read, bypasses Evennia command permissions,
enables developer access or integrates private Concordia memory.

## Pressure topology and event projection

- **Pressure is cell-owned, not room-owned.** A developer projection has
  `pressure_cells` with measured pressure, oxygen partial pressure, temperature,
  gas mass, volume and the authored room membership. `spaces` reference their
  `pressure_cell_id` (or `null` for no verified commissioned cell).
  `pressure_boundaries` carry actual access-link identity, both endpoints'
  cell IDs, the **actual** `setting` (`open` or `closed`), the optional
  `authored_policy` (`open`, `closed` or `closed_or_auto`, design data, never
  a state) and condition. A closed hatch is not the same as a
  healthy seal; neither a renderer nor a crew client may infer flow from its
  displayed setting alone. Cell-wide measurements cannot be copied into each
  room's `measurements`. The published full ship contains 133 pressure cells.
  Room IDs inside a cell obey the identifier grammar. A cell's `pressure_kpa`
  must agree with the world's own coarse gas model, P = m·R·T/V with dry-air
  R = 287.05 J/(kg·K), to 0.5 % (or 0.01 kPa), so a projection cannot pair a
  plausible pressure with an impossible gas charge.
- **Authenticated addressed events include what was said.** Each actor event
  carries `text` and `datum_fields`: a bounded flat map preserving original
  `datum_*` OOB keys and scalar values. `null` is allowed and means the world
  reported the value as unknown (for example, a panel with no good sample
  yet), which is different from an absent key. No nested dictionaries, invented alarm
  payloads or events addressed to another character. `datum_fields` is
  read-only once validated and serialises as a plain JSON object. If an
  observation cites `Evidence.source=addressed_event`, the cited event may be on
  another page of the same cursor series (as with developer pages); when it is
  on the same page it must predate the observation. The service must still
  authenticate the original addressed journal delivery.
- **Panel readings keep their sample time.** `Evidence.source=local_panel`
  is timed at the panel's own sample, and may cite the journal event that
  delivered the reading to this actor (`event_id`). That delivery happens at
  or after the sample, so when co-paged the event must not predate the
  observation. Only `addressed_event` and `local_panel` evidence may cite an
  event.
- **Freshness is objective, not a caller label.** At snapshot game time,
  `available` means a usable observation sampled **at most 60 game-seconds
  ago**; `stale` means a retained last-known observation **older than 60
  game-seconds**; `unavailable` means a failed sample with no condition or
  readings, **at any age**: its evidence time is when the failure was last
  confirmed and is never rewritten to look recent. A 1,000-second-old reading
  cannot be `available`, and a 10-second-old one cannot be `stale`. These are
  evidence freshness states, *not* declarations that machinery is functional.
  The exact 60-second policy is part of schema v1 and requires versioning if
  changed. Future producers must derive, not accept, these labels.
- **Measurements are unique per metric name.** Units are restricted to the
  enumerated physical units. Known metrics have a canonical unit, and any other
  name ending in a unit suffix (`_kpa`, `_pa`, `_k`, `_kg`, `_kg_s`, `_m3`,
  `_m_s`, `_kw`, `_mw`, `_kwh`, `_rpm`, `_rad`, `_s`, `_h`, `_pct`, `_fraction`)
  must use that unit. Thus two `pressure_kpa` readings, `unit=furlongs` or a
  `tank_volume_m3` in kelvin cannot validate.
- **Mass units and custody:** source **Evennia inventory quantities are in
  tonnes (t)**; the world-read wire contract publishes `quantity_kg` in
  **kilograms (kg)**. The producer must explicitly multiply an inventory
  `quantity_t` by 1,000, while already-kg motion-ledger balances must
  *not* be converted twice. Retain distinct source identifiers and custody:
  `INV-REACTION`/`INV-FTL-FUEL` are legacy reference rows and the
  corresponding motion-ledger balances are spendable. Do not sum or claim
  equality before the planned receipt-backed migration.

## Rules

- `developer_actual` is an explicitly privileged projection of Evennia-owned
  world truth. It may contain spatial and equipment states, measured numeric
  readings, source-specific stocks and developer-only audit events.
- `actor_observed` is built from the authenticated character's *already
  legitimately obtained* observations, local capability advertisements and
  addressed `ox_event`-style world events. It contains neither another
  character's events nor the global machine, route or fault graph. An unavailable
  panel has no fresh measurements; stale readings retain their observation time.
- Both scopes carry `schema_version`, `world_id`, independent
  `topology_version` and `engineering_version`, a committed publication
  sequence, finite game time and a bounded (128 records per collection) page.
  Cursors are opaque; the future service must bind them to actor, scope,
  installation, revision, and query and expire/reject stale cursors.
  A contract validator alone cannot enforce that.
- Model version equality is required for **both** topology and engineering
  fit-out before a renderer overlays values. Existing v0.4 wire drawing must
  not be silently matched to installed `0.5-candidate` engineering.
- World audit entries are *not* addressed alarms. Generating an actual crew
  warning requires an Evennia-owned emission and authenticated journal delivery,
  not converting developer diagnostics to beliefs in the interface.
- `INV-REACTION` and `INV-FTL-FUEL` inventory references are explicitly
  `legacy_reference` custodians, **not spendable remaining balance**. Only
  `motion.propellant_kg` and `motion.ftl_fuel_kg` are currently designated
  operational fuel balances. No equality or migration is invented.

## Remaining integration requirements

1. Install a role-checked server-side projection from the *persisted* v0.5
   state, not source design JSON, with transactionally coherent snapshot
   publication and independent revision identity.
2. Extend G19 actor-local observations/capabilities and receipt-backed
   delivery before using this for autonomous full-ship traversal or work.
3. Add explicit world-emitted crew-visible alarms (with recipient and event
   provenance). Keep existing private event filtering and reconnect/replay.
4. Design a separately authenticated handler cognition read API and joining
   policy. This world schema must **not** contain private handler beliefs.
5. Reconcile inventory fuel with motion-ledger debits through a **versioned,
   receipted migration** before claiming one unified stock balance.
6. Review the deployed v0.5 renderer and its engineering version registration.
7. Keep the F6 corruption hardening and the main fuzz record accurate.

## Amendments before any producer

`ox.world.read/1` has no producer or consumer yet, so these were amended in
place on 31 October 2026 rather than versioned: actual-vs-authored boundary
setting; `unavailable` at any age; cross-page event citations; identifier
grammar for cell room IDs; suffix-derived canonical units; P/m/V/T agreement;
immutable event datums. A second round on the same day, still before any
producer: `null` event datums, and `local_panel` evidence citing its delivery
event. Once any endpoint publishes this schema, a change to what validates
requires a new schema version.

Contract-only tests: `python -m unittest discover -s contracts/tests -p 'test_*.py' -v`
after installing `python -m pip install -e ./contracts`. Schema tests do not
prove service authorization, physics, migrations, or installed-world behavior.
