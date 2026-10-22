# Evennia integration of the full Ox ship

**Stage 1: canonical spatial topology**  
**Source model:** `ox_full_ship.json`, model v0.4

The full current-installation ship model is now being introduced into the runnable Evennia world incrementally. This stage deliberately materialises spatial truth before operational semantics.

## Authority boundary

`ox_full_ship.json` is source data. It is not the live simulation database.

The loader validates the prepared model and uses it to create persistent Evennia objects. Once created, those objects own live state. Rerunning the loader does not reset a room's current condition, delete runtime objects because the JSON changed, or silently reroute an existing access object.

This preserves the existing project rule: **Evennia owns physical state and consequences; the external AI handler owns private cognition.**

## Stage 1 implementation

`world.ship_model` validates and indexes the canonical model. It currently consumes the source identity, 421 spaces and 517 authored access links while structurally validating the other required model sections for later slices.

`world.ship_world` materialises:

- one persistent `CanonicalShipRoom` per canonical space, tagged by source-model ID;
- persistent access objects for the authored physical links;
- source identity and static spatial metadata on those objects;
- a non-spatial root object recording which model version and topology counts are deployed;
- a Developer-only `board ox` / `disembark ox` entry path from Limbo when Limbo exists.

The builder is idempotent. An interrupted first deployment leaves the root marked incomplete, so the next startup resumes the graph rather than trusting a partial materialisation.

## Conservative traversal boundary

Canonical access links are **Developer-only in Stage 1**.

This is intentional. The source model contains pressure boundaries, exterior work zones, rotating cargo drums, indexed transfers, hard-lock requirements and machinery-access conditions. Treating every graph edge as an ordinary open doorway would make the integrated ship less correct than the prepared model.

The topology can therefore be inspected and exercised immediately by developers without granting crew impossible movement. Later slices will replace the temporary traversal lock with world-owned checks appropriate to each access class.

## Temporary coexistence with the proving ground

The seven-compartment prototype ship remains available during migration because existing coolant, cargo, atmosphere, watch and cognition tests are coupled to its fixtures and crew markers.

Initial setup now builds the canonical topology first and the proving-ground fixture second. Server startup verifies that the canonical topology exists, but skips the expensive walk when the same complete source version is already deployed.

The prototype is not the target world. It is compatibility scaffolding and should be retired only after its operational fixtures, crew locations and scenario assumptions have been migrated onto canonical spaces/equipment.

## Next integration slices

1. Classify canonical access links and implement pressure, EVA, rotary/indexing, hard-lock and permission/interlock traversal rules.
2. Materialise selected high-value equipment from the 692 equipment records, starting with equipment already represented by prototype gameplay.
3. Connect service nodes, service edges and isolation points to world-owned utility state and casualty consequences.
4. Move operational crew and existing incident scenarios onto canonical spaces and equipment while preserving durable identities and histories.
5. Retire the seven-compartment proving ground after regression parity is demonstrated.

## Verification

Stage 1 has lightweight source-model tests for the v0.4 topology counts and malformed references, plus database-backed tests using a tiny synthetic topology to verify idempotence, persistent current condition and directional access materialisation without constructing all 421 canonical rooms in every test case.
