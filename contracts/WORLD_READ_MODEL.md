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
  cell IDs, access setting and condition. A closed hatch is not the same as a
  healthy seal; neither a renderer nor a crew client may infer flow from its
  displayed setting alone. Cell-wide measurements cannot be copied into each
  room's `measurements`. The published full ship contains 133 pressure cells.
- **Authenticated addressed events include what was said.** Each actor event
  carries `text` and `datum_fields`: a bounded flat map preserving original
  `datum_*` OOB keys and scalar values. No nested dictionaries, invented alarm
  payloads or events addressed to another character. If an observation cites
  `Evidence.source=addressed_event`, the cited `event_id` must be included
  in `addressed_events` on the same page and must predate its observation.
  The service must still authenticate the original addressed journal delivery.
- **Freshness is objective, not a caller label.** At snapshot game time,
  `available` means a usable observation sampled **at most 60 game-seconds
  ago**; `stale` means a retained last-known observation **older than 60
  game-seconds**; `unavailable` means a recent failed sample with no condition
  or readings. A 1,000-second-old sample cannot be `available`. These are
  evidence freshness states, *not* declarations that machinery is functional.
  The exact 60-second policy is part of schema v1 and requires versioning if
  changed. Future producers must derive, not accept, these labels.
- **Measurements are unique per metric name.** Units are restricted to the
  enumerated physical units, with canonical units for known metrics. Thus
  two `pressure_kpa` readings or `unit=furlongs` cannot validate.
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
7. Keep remaining F6 corruption hardening and the main fuzz record accurate.

Contract-only tests: `python -m unittest discover -s contracts/tests -p 'test_*.py' -v`
after installing `python -m pip install -e ./contracts`. Schema tests do not
prove service authorization, physics, migrations, or installed-world behavior.
