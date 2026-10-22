# Ox of Hephaestus - fixed spine, transit and Engineering work-rotor layout v0.3

**22 October 2026 | Current-installation world model**

This is the play-facing physical arrangement used by `ox_full_ship.json`. It describes where people and equipment actually go. It is not fabrication CAD.

## 1. Fixed-spine cross-section

The 16 m outside-diameter fixed spine contains three independent longitudinal movement systems.

- **Trunk A** and **Trunk B** are separate 3.0 m-clear personnel/service trunks, centred roughly 4.6 m to either side of the ship axis. Four guided battery carts normally work in each trunk, but a manual passage remains if the carts fail.
- The **central logistics trunk** is a 5.5 m-clear, normally pressurised freight tube. Four guided sleds move stores, machinery and bounded cargo modules. It is sectionalised by pressure/fire shutters.
- Remaining annular wedges contain utility raceways and local fixed workspaces. The fixed spine is zero-g.

The two personnel trunks therefore move people and light service loads. The logistics trunk handles serious internal material movement. Neither is a substitute for the drum loading portals when handling commercial bulk freight.

## 2. Personnel and freight transit

Personnel carts carry six restrained people or roughly 500 kg of light service load. Nominal speed is 4 m/s; pure bow-to-stern movement is about 4.2 minutes, ordinarily 5-7 minutes including station handling.

The logistics sled envelope is approximately 4.2 x 4.2 x 8 m. Routine load is 50 t; restricted slow movement up to 100 t is permitted when the complete route and inertia limits allow it. Nominal sled speed is 3 m/s.

Each cargo drum has two different interfaces:

1. a small indexed service lock usable for people/tools while the drum rotates;
2. a large internal freight lock usable only with the drum stopped, aligned and mechanically hard-locked.

This permits machinery, tanks, pallets and bounded cargo modules to move drum-to-drum through the spine. It deliberately does **not** make the spine a 900,000-tonne bulk conveyor. Large loose-bulk redistribution normally waits for port/external handling.

## 3. Bow command complex, x = 0-90 m

The forward region is fully compartmentalised. It includes the debris-shield forepeak, docking vestibule, EVA station, sensor room, primary bridge, cargo operations room, navigation/traffic planning, communications, command office/briefing room, forward switchroom, water-service plant, sanitary compartment, local atmosphere plant and forward rescue-craft bay.

The **bridge** (`CMD-PRIMARY`) is therefore a real command room inside a larger command complex rather than a generic bow marker.

## 4. Central Engineering complex, x = 400-510 m

The fixed part of Main Engineering contains:

- `ENG-CONTROL` - Engineering Control;
- `SHOP-ELEC` - clean electrical/electronics shop;
- `NDT-BAY` - inspection/metrology/NDT;
- `ENG-LOCKER` and `HEAD-CENTRAL`;
- habitation indexer and rotary-utility machinery;
- `WR-ROTOR-MACHINERY` - bearings, drives, extension machinery and interfaces for the Engineering work rotor;
- `WR-FREIGHT-STAGING` - hard-lock heavy-freight staging from the central logistics trunk;
- `WR-FIXED-TRANSFER` - personnel transfer vestibule to the work rotor.

The original fixed zero-g heavy machine shop was replaced during a life-extension refit by the variable-gravity work rotor described below. The former machine-shop volume now contains rotor support machinery; the former heavy-fabrication volume is the work-rotor freight staging/hard-lock bay.

## 5. WR-01 adjustable-gravity Engineering work rotor

`WR-01` is a dedicated independent rotor centred near **x = 489 m**. It is not the habitation rotor and can be stopped for heavy freight transfer without stopping the crew accommodation.

Two pressurised telescoping passages extend in opposite radial directions from a central rotating hub.

### Shop carriage

The outward carriage contains:

- `SHOP-MECH` - machine/mechanical shop;
- `SHOP-WELD` - fabrication/welding bay;
- `PARTS-WASH` - dirty preparation/parts wash;
- `SHOP-IMMEDIATE-STOCK` - commonly used tools, cutters, fasteners and consumables.

Nominal moving mass is about **160 t**. At the normal 3.45 rpm work-rotor speed, the shop can move from **24 m to 75 m radius**:

| Shop radius | Approximate gravity |
|---:|---:|
| 24 m | 0.32 g |
| 38 m | 0.51 g |
| 56 m | 0.75 g |
| 60 m | 0.80 g |
| 75 m | 1.00 g |

The current general-machining deployment is **60 m / ~0.80 g**. Moving the carriage changes gravity without changing the normal rotor speed. Lower gravity than the 24 m position can be obtained by reducing rotor speed when a job genuinely benefits from it.

### Opposed stores carriage

The opposite carriage contains:

- `SPARES-CENTRAL` - high-use Engineering spares;
- `TOOL-CRIB` - controlled tool/test-equipment stock;
- `MATERIAL-STOCK` - fabrication material stock.

Its nominal moving mass is about **480 t**, approximately three times the shop carriage. Consequently it only needs to move one-third as far:

```text
m_shop * r_shop ~= m_stores * r_stores
r_stores ~= r_shop / 3
```

So the stores carriage ranges from **8 m to 25 m radius** while the shop ranges from 24 m to 75 m. In the normal 60 m shop deployment, the stores sit at **20 m**.

This is deliberately useful rather than dead counterweight. Frequently used stock lives in the shop itself; substantial spares, tools and material are only a passage-and-hub walk away. At the normal deployment the carriage-centre separation is about **80 m**, not a trip down half the ship.

### Fine balance and changing inventory

The 3:1 ratio is nominal. The exact stores mass changes as parts are consumed, repaired or replenished, so rack location is operationally significant. Segmented trim-water masses and smaller movable trim weights provide fine correction. Nobody has to relocate a three-tonne compressor merely to balance the rotor, but Engineering cannot treat stowage as weightless bookkeeping either.

### Personnel access

A small independent indexed transfer (`WR-IX-CAPSULE`) connects the fixed spine to `WR-HUB`. Ordinary personnel and hand tools can enter while the work rotor is operating. From the hub, the two telescoping passages lead directly to the shop and stores carriages.

### Heavy machinery transfer

The heavy logistics trunk connects to `WR-FREIGHT-STAGING`. To transfer a 50-100 t sled load onto the work rotor:

1. stop WR-01;
2. retract to the transfer configuration;
3. coordinate both carriages and trim;
4. index the rotor;
5. engage the structural hard lock;
6. equalise/open the freight boundary;
7. move the restrained load into the rotating hub/shop route.

This is a scheduled operation, not something done while the machine shop is spinning at one g.

## 6. Why the main shop is not fixed zero-g

Zero-g remains excellent for moving large assemblies and for some electronics/inspection work. It is poor as the default environment for machining, swarf collection, fluids, ordinary bench work and many fabrication jobs. The Ox therefore keeps clean electronics/NDT and freight handling fixed, but performs routine heavy workshop work under selectable centrifugal gravity.

This is a life-extension refit rather than an original-build feature, which suits the Ship-of-Theseus history of the vessel.

## 7. Aft power and propulsion complex, x = 820-950 m

The aft fixed ship contains separate switchgear, three generator rooms, high-temperature thermal plant, atmosphere plant, sanitary compartment, cartridge handling/magazine, propulsion control, emergency command, emergency communications, FTL service, FTL-fuel service, reaction-mass service, sublight propulsion service, aft EVA/rescue facilities, and long-voyage stores.

## 8. Space dust and debris protection

Protection remains layered:

1. navigation and avoidance for detectable macroscopic hazards;
2. replaceable multi-layer passive bow shielding for neutral hypervelocity particles/fragments;
3. an ionising/electrostatic/magnetic adjunct for charged or ionised fine dust;
4. approximately 120 t of already-carried water positioned in segmented forward shielding cells as secondary fragment/radiation mass;
5. an explicit FTL setting rule in which microscopic matter does not cross into the translated envelope as an ordinary superluminal impact, while macroscopic intersection remains prohibited.

The magnetic system is therefore useful but is not a magic neutral-rock shield, and the water is useful mission inventory rather than a sacrificial exposed iceberg.


## v0.4 survivability/maintenance integration

The fixed spine now carries two sectionalised fire mains alongside its separated personnel/service routes, with forward and aft pressure sources and controlled cross-ties. A continuous vacuum-side maintenance rail follows the fixed spine from the forward to aft EVA station; through cargo-drum regions it occupies the central bore around the fixed spine rather than the rotating outer drum skin.

Major machinery now has local-control capability independent of the ordinary central display path. The central Engineering complex remains the primary work-coordination point, but loss of Engineering Control or of a data route does not make a healthy local plant physically unmanageable.

Forward and aft spine atmosphere plants, local habitation emergency scrubbers, the two habitat refuges and the two survival craft form increasingly deep backup-life-support layers.
## v0.5 candidate pressure-zone refinement

The full-span `PZ-TRUNK-A` / `PZ-TRUNK-B` identities describe the old v0.4 source, not an indivisible installed atmosphere in the v0.5 ship design. Each of the 23 physical sections per personnel trunk is now a separate pressure cell named from its existing room ID, with all 44 original sectional pressure doors retained. These cells can exchange gas through actual open doors but remain independently isolatable on fault. F1/F2 flywheel machine bays are vacuum behind service locks; see `PRESSURE_CELL_CLOSURE_v0.5.md`. The v0.4 JSON and wire render have not been silently overwritten.
