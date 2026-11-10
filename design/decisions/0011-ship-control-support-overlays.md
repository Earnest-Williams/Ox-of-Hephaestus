# ADR 0011: ship-control support overlays and independent fault domains

**Status:** proposed and under implementation in [PR #151](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/151), 10 November 2026. These records do not declare the equipment operational in a deployed ship.

## Context

The accepted operations design needs a patched-together, segment-based plant
network and nine distributed compute machines, but the fitted v0.5 ship has no
general-purpose plant-control backbone. Its existing fire/pressure relays and
116 local instrumentation panels do not grant network control. The v0.5 ship
also has a single common LT rejection plant; calling nine machine cold plates
"independent" does not remove that shared plant failure domain.

One proposed machine is in `XCON-GAP-23`, a through passage between both
trunks. Turning the entire passage into a secure room would make crew
movement and maintenance worse.

## Decisions

1. **Separate, versioned infrastructure overlays.** Preserve the original
   `ox_full_ship_v0.5_candidate.json` and its fitted 438/450/466 electrical
   register as independent source truth. Validate new power and ship-control
   support overlays against those rows and the 421 spaces and 517 access links.
   The overlay is proposal until an explicit, audited, operator-only
   commissioning operation creates separate world-owned equipment, node and
   edge identities. No existing switch or broken component is reset.

2. **One plant-control backbone, two independent physical rails.** The A
   and B fibre rails trace the two distinct 23-compartment personnel trunks.
   Every compute endpoint has a separately faultable A and B branch. A single
   rail or splice cut cannot silently become a ship-wide network outage.
   The backbone is passive medium; locally powered endpoints are downstream
   of actual fitted electricity. No fictional central router is inserted as
   a new common-mode failure point. Gateways and authority are separate
   mechanisms, not implied by a fitted cable.

3. **Two genuinely new continuous-duty rotating data couplers.** The
   rotating HAB needs a separate A interface at `HUB-FIXED-A` to
   `HAB-04-COR` and B at `HUB-FIXED-B` to `HAB-08-COR`.
   An indexed personnel capsule is not a continuously conducting cable.
   Each coupler is a separate faultable piece of equipment; A and B have
   distinct machine drops. Their electrical/mechanical ratings and
   pressure-rated cable penetrations require commissioning evidence.
   No remote device gains authority from these new cables.

4. **Keep the forward cross-connection open.** `MIND-03` lives in a
   monitored, lockable *equipment rack* in `XCON-GAP-23`, not behind a
   whole-room lock. Both `ACC-XCON-GAP-23-A` and `-B` remain usable
   movement routes. Access to the rack is a distinct future monitored action.

5. **Five independent finite thermal domains.** No group exceeds two
   machines. Each has its own buffer, rejector, and separately monitored
   cold plates. At their 2 kW/machine rated draw, a local 720 kJ heat
   buffer exceeds the 120 s, 480 kJ worst-case interval for a two-machine
   island. Headroom starts **unmeasured**, not full. The common LT plant
   may support steady-state rejection, but its failure is *not* evidence
   of unlimited local cooling. Before measured rejection exists, heat goes
   into measured local headroom; any remainder enters the actual room
   atmosphere and causes an equipment thermal-protection trip.

6. **Fit the first gateway as disabled hardware.** The gateway
   `GW-LCS-DR-03` belongs to the existing `LCS-DR-03` station
   at `BE-05-SVC`. An A branch from `TRUNK-A-DR-03` runs through the
   actual logistics stop and `TRUNK-B-DR-03`; the B branch enters from
   that same B trunk compartment. A casualty at this shared local corridor
   can remove *the drum-3 gateway*, even though the two principal backbone
   rails remain independently routed. A single segment-local gateway fault
   is acceptable because the drum keeps its physical local controller.
   Commissioning adds only physical records. Protocol mapping revision
   starts at zero, power unverified and remote commands disabled.

7. **Preserve separations of responsibility.** Installed fibre proves
   physical connectivity only, not a correct device protocol, sensor
   freshness, permission to command, successful actuation, or a live
   computational principal. A future network-scoped read model and remote
   command arbitration require their own acceptance and access controls.
   Local control, hardwired trips, and ordinary door travel survive network
   loss.

## Verification

The support candidate is `design/ship/lead_mind_support_topology.json`.
The validation and finite-cooling model is `game/world/ship_mind_support.py`.
No candidate-only fault sweep is labelled an installed-world acceptance test.
The draft PR adds separate commissioning, persistence and source-provenance
checks, plus an installed electrical and ship-clock integration gate.

## Deliberately unresolved

- The remaining mixed-generation gateway vocabulary beyond three read-only
  drum-3 controller registers and segment-local fallback acceptance.
- Which local roles may take control of each segment and exact remote
  authority grants.
- Supervised cooldown/restart after a latched computer thermal trip.
- Access-reader fitting to the rack and other controlled machinery rooms.
- Parity, rebuild timing, cognition, and the lead-mind player interface.

These are subsequent operational work packages, not evidence that today's
prototype has a functioning ship-wide AI.

## Commissioning implementation

- Exact cable pressure-penetration surveys and continuous rotary-joint
  ratings now gate installed network connectivity. Revisions invalidate
  certificates after apparatus changes, including failure and repair.
- Fifteen separately fitted LT connection rows provide real feed/return
  routes and manual isolation without modifying the original network.
  Rejection consumes the original plant/motor/radiator allowance; shared
  LT failure leaves only measured local buffer capacity. Optional air
  transfer deposits all rejected heat in its real receiving cell.
- Cooling custody version 2 checks current headroom against cumulative
  absorption and recovery. Its migration preserves version-1 inventory.
- Three separate local gateway supply rows support measured 50 W operation.
  A bounded read-only vocabulary preserves raw terms and timestamps and
  requires operator comparison before a mapping revision is accepted.
  Network loss withholds remote readings; it does not change local machinery.
- The focused infrastructure workflow runs on drafts so physical acceptance
  can be completed before marking the construction PR ready. Other expensive
  draft suites retain their existing deferral policy.
