# Drum 3 fit-out survey

**Date:** 2 November 2026. **Purpose:** step 1 of the
[lead-mind first slice](ship-mind.md#first-playable-slice): record what the
installed ship actually has around cargo drum 3, what the runtime does with it
today, and what the slice would have to add.

**Sources:** `design/ship/ox_full_ship.json` (the installed design data),
`game/world/continuous_ship_physics.py`, `game/world/ship_cargo_environment.py`
and `game/world/ship_auxiliary_electrical.py`, and the
[cargo environment](../ship/G19_CARGO_ENVIRONMENT.md) and
[instrumentation](../ship/G19_INSTRUMENTATION_AND_RECOVERY.md) notes. This is a
read-only survey; nothing was changed.

## Summary

- Everything the incident needs is fitted: skid, circulation pack, LT
  interface and valve, gallery board, sector valves and a local machinery
  control station.
- **Today, nothing about drum 3 reaches the bridge or engineering.** The skid
  is read and set only by someone standing in the drum 3 gallery.
- **"Running but not cooling" is real physics.** The skid can be powered and
  operating while delivering no cooling, because cooling also needs the LT
  interface connected and a share of a budget that the drive takes first.
- **The design data already describes a remote layer the runtime doesn't
  model:** an "original plant-control network", a gateway fitted when
  generator B was replaced, 559 isolators flagged as remotely operable, and 33
  local control stations built to keep working when the network is down. This
  is the lead mind's natural reach.
- There is no navigation computer, data network or gateway equipment. Those
  are new.

## Installed fittings

| ID | What it is | Room (frame) | Generation | Runtime role today |
|---|---|---|---|---|
| `DR-03-CARGO-HX` | Cargo refrigeration heat exchanger and pump skid | `DR-03-GALLERY` (rotating) | original | Local proportional controller; read and set only in the gallery |
| `DR-03-CARGO-GAS` | Controlled-atmosphere service pack | `DR-03-GALLERY` (rotating) | original | Must be operating for the skid to cool |
| `DR-03-SVC-DB` | Rotating cargo service board | `DR-03-GALLERY` (rotating) | original | Feeds both cargo devices |
| `DR-03-LT-IF` | Cargo thermal rotary interface | `DR-03-SERVICE-LOCK` (fixed) | original | Connects the skid to the LT plant |
| `DR-03-ROT-PWR` | Rotary power interface | `DR-03-SERVICE-LOCK` (fixed) | life-extension refit | Power into the drum |
| `DB-A-DR-03`, `DB-B-DR-03` | Zone distribution boards A and B | `TRUNK-A-DR-03`, `TRUNK-B-DR-03` | original | Trunk power |
| `LP-DR-03-SERVICE-LOCK` | Local panel | `DR-03-SERVICE-LOCK` (fixed) | original | Reads that room's pressure cell, equipment and isolators |
| `LCS-DR-03` | Local rotor and cargo machinery control station | `BE-05-SVC` (fixed) | mixed | **None for cargo.** Fitted with local takeover, a hardwired emergency trip and network-independent safe functions |
| `LT-PLANT`, `LCS-LT` | LT cooling plant and its local control | `ROTARY-UTIL-A` | — | Source of all low-temperature heat rejection |

The gallery has no local panel. Its air is the measured pressure cell
`PZ-DR-03-SVC`.

## Paths

**Power:** `DB-A/B-DR-03` → `DR-03-ROT-PWR` → breaker `ISO-DR-03-SVC-DB`
(gallery) → `DR-03-SVC-DB` → skid and pack, each individually fused, and the
eight sector feeds `ISO-PWR-DR-03-SEC-01` to `-08`.

**Cooling:** `LT-PLANT` → `EDGE-DR-03-LT-IF` through valve `ISO-DR-03-LT-IF`
(in the **service lock**, on the fixed side) → `DR-03-LT-IF` → skid → eight
sector cooling feeds through valves `ISO-COOL-DR-03-SEC-01` to `-08`
(gallery). The cargo atmosphere has a matching set, `ISO-CARGOAIR-DR-03-SEC-xx`.

## How the skid behaves

Every 10-second physics step, the skid cools only if **all** of these hold:
the skid is operating, the circulation pack is operating, `DR-03-LT-IF` is
connected to the LT plant and not broken, and there is budget left.

- It rejects heat in proportion to how far the cargo is above target, up to
  **20 kW**.
- All six drums share **min(120 kW, 10 % of the LT capacity left for the
  environment)**. LT capacity is 937.5 kW per working radiator (up to four),
  and **the drive's heat is cooled first**. Losing radiators or running the
  drive hard can push the cargo share well below 120 kW.
- Cargo out of its profile's band accumulates permanent quality loss.
- The drum's thermal state exists only after an operator survey of the drum
  and its sensitive lots.

So a skid can be operating, powered and healthy yet deliver nothing: valve
shut, LT interface broken, pack stopped, or no budget during a burn. **That is
the physical basis for the `RUN` ambiguity** in the lead-mind design: a
translated "running" is not delivered cooling.

## What can be seen and done today

| | Today |
|---|---|
| Read cargo temperature, target, cooling kW and lot condition | Only in `DR-03-GALLERY`, at the skid ("read the actual cargo heat-exchanger panel locally"). |
| Change the target | Only in the gallery: skid not broken, gallery air safe, cargo environment commissioned; 265–315 K. |
| Operate an isolator | Only in the isolator's own room, by hand. The runtime honours the remote flag in exactly two hard-wired cases: `ISO-GAS-BANK-A` from `WATER-FWD`, and `ISO-RAD-HT-1/2` from `ENG-CONTROL`. |
| Bridge or engineering view of drum 3 | None. The only ship-wide relay is the protected HAB fire and pressure relay. |
| `LCS-DR-03` | Fitted equipment only; it has no runtime behaviour for cargo. |

## The remote layer on paper

The installed design data describes more than the runtime models:

- **559 of 1,092 isolators** are flagged `remote_operable`, including
  `ISO-DR-03-LT-IF`, `ISO-DR-03-SVC-DB`, `ISO-DR-03-ROT-PWR` and all 24 drum 3
  sector valves and breakers. Only `ISO-LP-DR-03-SERVICE-LOCK` is local-only.
- **`MOD-GEN-B`** (life-extension era): the replacement generator "is more
  reliable but uses a gateway to the original plant-control network".
- **`MOD-BR06-SLEEVE`** (repair era): "remote indication exists but remote
  actuation was not restored for every service".
- The **local control contract** requires machinery to stay controllable "if
  shipwide remote control or a central console is unavailable", and 33 local
  control stations are fitted to that rule.
- Equipment carries its **generation** (original, life-extension, gen 2 and
  gen 3 replacements, repair era, mixed), so the patchwork of protocols has a
  basis in the data.

Nothing in the runtime implements this network. That gap is the lead mind's
starting position: the paper says the ship once had a plant-control network;
the game decides how much of it still works.

## Travel to drum 3

| From | Links | Nominal time | Note |
|---|---|---|---|
| `ENG-CONTROL` | 10 | about 6 minutes | Trunk A pressure doors, then the service lock |
| `CMD-PRIMARY` | 9 | about 5.5 minutes | Trunk A forward |

Three of those minutes are the **indexed rotary transfer** from the service
lock to the drum hub, which needs capture confirmed and relative speed in
limits. The LT valve is in the service lock, on the fixed side, so an engineer
can check it **without** the transfer. Setting the target needs the transfer.

## What the slice must add

1. **The plant-control network and one gateway.** Model the original network
   as world-owned links. Put the gateway at `LCS-DR-03`, the drum's
   mixed-generation local control station, translating its skid status into
   the network's terms. This replaces the earlier idea of a gateway at
   `LP-CARGO-CTRL-FWD`.
2. **One remote action.** `ISO-DR-03-LT-IF` is already flagged remotely
   operable, so it is the honest first actuator: honour the flag only through
   a working network path and gateway, under the existing interlocks.
3. **Telemetry through the gateway:** skid operating state, cooling kW, cargo
   temperature and target, each with source time and mapping revision, and a
   deliberate mapping flaw where "operating" is translated as "cooling".
4. **The navigation computer** as new fitted equipment near `LP-NAV-PLANNING`,
   if it stays the first specialist.
5. **Commissioning:** an operator survey of drum 3 and one cold-chain lot
   before the incident.

## Questions for the design

- Should the plant-control network be one network with damage, or several
  segments of different generations joined by gateways? The data suggests the
  second.
- Which of the 559 remote-flagged isolators should actually be reachable at
  the start? A small set keeps the "nearly blind" opening.
- Does `LCS-DR-03` get its own controller behaviour (local takeover, trip), or
  stay a passive gateway host in the first slice?
