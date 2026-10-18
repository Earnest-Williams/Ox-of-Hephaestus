# G3b — real cartridges, carriers and world-owned supply dependencies

This is the physical/world foundation for cooperative work. It builds on
G3a's actor-private epistemic ledgers: observations, guesses and
questions are *not* inventory.

## Inventory conservation

A new Django InventoryItem represents ONE serialised A-01 cartridge.
It is always either stored in an exact real compartment, physically
carried by one world character, or irreversibly consumed. Check
constraints reject impossible simultaneous locations. Consumed item
rows remain as world history, not magically replenished stock.

The prototype already had real local spare cartridges in A-01's
persistent Attribute. Those are **not duplicated or reset on upgrade**.
The scrubber readout and physical replace operation now count both
legacy local spares and separately serialised delivered supplies. When
the legacy rack has no remaining unit, a valid replacement consumes
exactly one installed serialised item, transactionally. Existing
cartridge procedures and work receipts remain valid.

No cargo inventory is fabricated by running build_ship(). The
operator-only disposable seed helper creates actual units for test
scenarios; later dock/production systems will seed items via their own
world-authoritative receipts.

## World-order lifecycle and actor limitations

The first bounded SupplyOrder requests one A-01 cartridge, naming
the actual requesting character (Teo), assigned cargo person (Mara),
required delivery compartment and status.

1. Teo may issue request_supply only at Environmental Plant, where
   A-01 is isolated and **real local spares are zero**. The world
   creates the order and addresses Mara. Merely anticipating a shortage
   does not mint an item.
2. Mara may accept_supply as that assigned role. This confirms only
   an accepted obligation, **not** that stock exists.
3. Mara must physically attend Cargo Hold and collect_supply. The
   world atomically moves exactly one available serialised item from
   cargo storage to her carrier identity. If none exists, the work
   receipt is a durable refusal; no imaginary cartridge is supplied.
4. Mara must traverse ordinary Evennia exits to Environmental Plant
   and deliver_supply the **same carried item**. The world changes its
   actual location and generates a supply_replenished event addressed
   to Teo. Prior "in transit" messages were not delivery proof.
5. Teo can see the newly present item in a local sensor reading. Only
   real role- and location-checked scrubber replacement consumes it.

All four supply verbs use existing global WorkReceipt IDs with
actor-bound reconciliation. The common world pump row lock, inventory
row locks and transaction ensure serialised competing requests on
PostgreSQL; denied requests remain denied on retry with their
original ID. A new legitimate attempt requires a **new world event
or changed evidence** and a distinct request ID. No model can submit
raw SQL or assign itself inventory.

## Local observation versus world truth

New ordinary oxinventory <nonce> reports only the authenticated
character's current compartment stock and physically carried items.
For compartments without relevant sensors/stock affordances,
local_cartridges is **null (not verified)**, not a fabricated zero.
No omniscient shipwide count or order list is exposed. Order messages
arrive only through the existing recipient-addressed journal. The
handler checks nonce, actor DBref, version, item IDs and integer
quantities before treating this as a local observation.

## Tests and boundaries

The database-backed tests verify real request/accept/collect/deliver/
replace effects, exactly-once serial conservation, unauthorized
roles, location refusal, collisions across global WorkReceipt IDs,
private event addressing, at-least-once replay, atomic rollback,
and two accepted orders competing for the last real unit.

This PR establishes the physical authority and command contracts.
The next handler increment uses private agendas and ordinary movement
to actually orchestrate Teo and Mara through that order lifecycle,
including a lost-ACK restart trial. It does not introduce general
cargo types, all possible work orders, nor player UI.
