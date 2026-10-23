# Ox of Hephaestus — installed transfer machinery and finite industrial disposal, v0.5

**23 October 2026 · 40-person / 730-day reference · selected physical design, not Evennia or fabrication qualification.**

## Equipment genuinely installed

The ship has **808 individually maintainable equipment objects** across its original **421 spaces**, **517 access links**, **1,186 service nodes**, **1,181 service links**, **1,256 isolation points**, **15 inventory accounts** and **42 grouped maintenance procedures**. The sixteen cargo/industrial pieces introduced in this machinery increment, followed by six physically distinct inert-gas makeup pieces in the later B′ endurance reconciliation, are not extra life-support trains. They are **six independent cargo-drum passenger-indexer carriers**, **six independent fixed full-sled freight pressure-capture collars**, **two sealed 4-tonne compatible industrial scrap cassettes**, and **two segregated sealed 1-tonne hazardous solid cassettes**. All remain in the existing dry-mass planning allowance; no extra departure mass is minted.

Each rotating cargo drum already has one fixed **12 × 4.6 × 4.6 m** full-sled freight chamber with two metres nominal clearance around an eight-metre captive cargo box. The six existing `DR-xx-SERVICE-LOCK` pressure chambers are **two-person/tool indexed transfer cabins**, not duplicate freight locks. The corresponding `DR-xx-PERSONNEL-INDEXER` equipment physically drives/locks the moving carriage. The separate `DR-xx-FREIGHT-COLLAR` equipment docks and mechanically hard-locks the full freight portal.

The passenger station is 18 m axially removed from the freight station, permitting 9.5 m nominal clear separation between the ends of their rated cabin/cargo reference envelopes. A passenger shuttle can operate with an independently rotating drum **only after both extended collars are withdrawn and mechanical phase/capture is proved**. Heavy freight is restricted to a **stopped, aligned, structurally hard-locked drum** with restrained/sized cargo, actual pressure equality and verified individual hatch seats. The six drum stations never share one magical cargo/interlock flag. A failed passenger carriage, jammed fixed capture or cargo lock has local operational consequences; other drum interfaces can remain usable.

## Actual local control evidence, not dashboard truth

Every selected critical system has a separate hidden physical condition, sensor/indicator claims and a verifiable local recovery path. Eight seeded *casualty design cases* in the model cover:

1. Main generator breaker indicating closed while its bus is dead.
2. Habitation bearing lubricant/heating anomaly with misleading normal-speed telemetry.
3. Drum-02 personnel-indexer false capture.
4. Industrial scrap bin full while its level gauge reads empty.
5. HAB-06 CO₂ exterior outlet obstructed by a scaffold despite a healthy indoor indicator.
6. Waste processor B operating while its waste rotary union is unsealed.
7. A portable damage-control pump marked available though physically held in F2 vacuum service.
8. WR-01 indexer/swinging carriage passage leaking through sliding seals.

A crew's repair receipt, remote reset, old label or a locally plausible explanation does not restore machinery without the stated access, physical isolation, positive test and world-owned observation. Independent emergency resources cannot be moved to two simultaneous casualties. Faults are not forced across the whole ship when a local boundary can contain them.

## External habitation hydrogen and CO₂ ports

ECLSS-A occupies HAB-06 and ECLSS-B HAB-08. Their four segregated byproduct pipes and double source/hull isolation **remain separate from oxygen delivery, breathing-gas makeup and from each other**. The current design selects radial-outward rotating-hull outlet datums:

| Vent | Arc | Angle | Axial station | Outer radius |
| --- | --- | ---: | ---: | ---: |
| ECLSS-A-H₂ | HAB-06 | 231° | 453 m | 79.5 m |
| ECLSS-A-CO₂ | HAB-06 | 219° | 457 m | 79.5 m |
| ECLSS-B-H₂ | HAB-08 | 321° | 453 m | 79.5 m |
| ECLSS-B-CO₂ | HAB-08 | 309° | 457 m | 79.5 m |

Each 0.6 m-class nozzle is at least 6° from its arc's keyed central and nearby sliding saddle datums, 13° from an end-pressure head, and 1.58 m radially outside the existing conservative r77.92 m shell guard. The vent x-stations lie **between**, rather than within, the two indexed passenger carrier axial station intervals. The rotating external ECLSS discharge nozzles and their plumes require an observed **3 m local EVA exclusion**, positive exterior site/camera clearance, attitude-reaction correction and twin-valve shutoff. This is a credible **selected nominal swept-reference separation, not a claim that the welds/collars/actual service rails have been surveyed**.

If either H₂ exterior outlet obstructs, the affected electrolysis train reaches its finite **0.25 kg** temporary buffer and must throttle or stop; protected breathing oxygen is separately limited. A CO₂ regeneration receiver has **50 kg** finite acceptance, not an inexhaustible solution. Sensors can lie. A plume-blocked area prevents dumping even when pressure is suitable; no process may discharge into occupied atmosphere.

## Material cannot disappear

The two existing sanitation processors continue to collect/transform reference **7.3 t** of dried sanitary residue across 730 days into **two separate 8 t** bins, 16 t nominal capacity. There are also **two 4 t industrial scrap receivers** (8 t total) and **two 1 t hazardous solid containment cassettes** (2 t total). The two new corresponding inventory accounts begin with **0 t departure waste**. Reference industrial generation is **1.5 kg/day** (1.095 t across 730 days) and reference segregated hazardous generation **0.7 kg/day** (0.511 t). These are scenario baselines, not an unbounded guarantee: major repairs, casualty debris, infected waste, incompatible cargo, or burnt equipment can exceed them.

Generated matter is **transferred out of identified existing supplies, spare equipment, cartridges, maintenance/cargo materials and food flows**. It must debit the source before increasing a receiver, preserving total mass and avoiding double counting the original 1,187,500 t departure budget. Hazardous waste may not be relabelled general sanitary residue, washed down, burnt inside an unqualified plant, vented to vacuum, or hidden within the 8 t dry scrap inventory. Contents requiring chemical identification are quarantined at their generation site pending a compatible vessel and verified physical handling route.

All ordinary receipts rely on actual available cassette free capacity, serial/seal condition, relevant pressure doors and transfer vehicle/handcar status. Material in rotating WR-01 requires the correct current carriage and passage configuration; inaccessible stores are not global shared storage. A full compatible receiver **stops or constrains the generating operation** until independently approved containment or port-side offload exists. The 10 t combined industrial/hazardous capacity is not ten tonnes *on top of* the 16 t sanitary stream; all three categories remain chemically and physically distinct.

## Mechanical validation

`check_physical_operations.py` verifies six interlocked rotating cargo interfaces (twelve separate machines), freight-sled fit/rating and local control ownership, four finite segregated industrial bins and two generated-mass inventories, four physical byproduct nozzle positions against the selected B′ 38° arc/head/saddle and IX station guards, and eight distinct locally observable machinery casualties. Sixteen deliberate invalid mutations must fail. It is executed with the ship's six previously existing stdlib checkers in `.github/workflows/ox-ship-design.yml`.

**Selected candidate scope:** physically coherent geometry, material destinations, maintenance ownership and consequences at simulation fidelity. Real as-installed material condition, pressure integrity, moving-gasket contact/FEA, measured volume, inspection and certified nozzle/hatch pressure vessels are not asserted. The v0.4 published ship, standalone wire display and Evennia/AI source remain unchanged.

**Selected revised indexer moving guard:** r8.55–11.55 m, preserving 0.55 m to the stationary 8 m fixed spine and 0.30 m to the rotating r11.85 m receiver. Former r8.05–11.65 m was an intermediate trial. Both collars must retract before moving.

## Known-air to unknown-environment physical closures

A supplementary pressure-access audit has added **131 existing physical doors and shutters** to the independently rated boundary register, bringing total rated interfaces to **339**. They remain covered by the original **517 access links** and **42 existing maintenance groups**; the access-to-maintenance assignment is recorded in `environmental_access_boundaries_v0.5.json`. No extra atmosphere volume, equipment objects or departure mass is invented.

The industrial/bearing service rooms, cargo service and freight sector gates, external cargo portals and shield service hatches are sealed against their source protected cells. Crews must prove local pressure, chemistry, seal and isolation; hazardous process or moving gear additionally requires energy/rotation lockout. See [UNKNOWN_ENVIRONMENT_ACCESS_CLOSURE_v0.5.md](UNKNOWN_ENVIRONMENT_ACCESS_CLOSURE_v0.5.md).
