**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 339 rated isolation boundaries (208 previous plus 131 cargo/industrial/unknown-environment thresholds), 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **802 maintained equipment objects, 13 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.

# Ox of Hephaestus — major-system operating and casualty doctrine v0.5

**Earlier 23 October 2026 checkpoint — indexed drum locks:** Six separately pressurised DR-01–DR-06 fixed service-lock cylinders have been moved off the personnel-trunk bores. There are now **107/133 sized pressure cells**, **26 held**, **208 rated boundaries**, **68,310.657 m³ nominal gross** and **54,101.591–62,502.553 m³ design free-air screen**. The short station connectors and moving indexed collars remain survey items; measured free air and actual safe access remain unknown. The two independent 2.75 t air reserves remain unchanged.


**Design-stage functional closure; not Evennia code.**
Each plant below has a physical state, an observation state and a recorded
maintenance/work state. They are distinct: an operator may see a stale gauge,
a repair may fail, and the world must not declare a plant functional solely
because a task was marked complete.

This document supplies believable operating doctrine at simulation
granularity. It does not mandate discrete-second physical solvers for every
switch, valve, litre or metal part.

## A. Electrical generation and distribution

The main generator GEN-M is 3.0 MW nameplate; GEN-A and GEN-B are
0.75 MW each. Continuous **combined** delivered generation is limited to
3.3 MW by the actual integrated plant/thermal/switching envelope.
Normal service load is 1.55 MW; demanding load 2.6 MW; protected
distribution budget 0.75 MW.

Each generator has states OFF/COLD, PREPARING, AVAILABLE,
ON_LOAD, UNAVAILABLE/TRIPPED and ISOLATED_FOR_WORK. Individual
measurements include cartridge feed, coolant flow, output power,
winding/bearing temperatures, breaker position and electrical protection.
Breakers, buses and local control must not automatically follow generator
availability. An apparently healthy generator can deliver nothing through
an isolated MSB or open outgoing breaker.

GEN-M trip causes actual load shedding/re-dispatch. A single auxiliary
supports at most the **0.65 MW selected essential schedule**. The 0.75 MW
full protected schedule therefore loses at least 0.10 MW of discretionary
loads in this operating mode; do not say both capacities are identical.
Only substantiated available batteries/flywheels may bridge changeover.
A failed bus tie may leave one district dark while adjacent panels stay on.

The original power architecture remains organised but the current panels
are mixed generation. A bridge screen can show breaker demand and remote
status; a local technician may find a welded contact or a relabelled cable.
Restoring power requires verified voltage and downstream load/temperature,
not merely setting a switch back to ON.

## B. Bearings, rotational drives and mechanical support

Six cargo drums, the habitation rotor, flywheel installations, and
independent WR-01 have separate torque, bearings, local controls,
lubrication and balance provisions. None is operated by a generic
shipwide ROTATE flag.

Common states: PARKED / BRAKED / RELEASING / ROTATING / SPINDOWN /
ISOLATED / UNBALANCED / BEARING_CAUTION / TRIPPED.
Motor-driven acceleration is not instantaneous. Emergency stopping a
massive rotating drum incurs a period of reduced controllability,
mechanical and thermal loads, and can strand work access in a safer
but less convenient configuration.

A damaged bearing can lose pressure, develop thermal/vibration drift,
or disagree with its local gauge without having already seized.
A crew member can take local control after permission and access checks;
remote telemetry cannot bypass actual mechanical stops.
After work, retest vibration, oil flow, temperature and rotor balance.

WR-01's shop remains 60 m from the axis at roughly 0.80 g during
normal machining. Opposite stores are at 20 m, with nominal 160 t/480 t
moving masses and trim water/weights. Workshop inventory placement
affects balance; heavy freight transfer requires rotor stop,
retraction, index, hard-lock and pressure preparation. Ordinary
indexing of people/tools is a different system.

## C. Cargo handling and transport

Personnel transit uses two separate 3 m clear trunks with roughly
six-person carts, ordinary 4 m/s cruising and station handling.
Guideway faults can strand carts without making the trunk impossible
to walk; carriage retrieval and manual bypass are explicit duties.

The heavy logistics tube is 5.5 m clear and has a 3.8 x 3.4 x 8.0 m
complete sled bounding envelope; typical 50 t, restricted 100 t.
Its stations, braking blocks and sectional fire/pressure shutters
are individual operational constraints. A sled cannot change
compartments if its load is oversize or a pressure shutter is locked.

The six cargo drums have three independent functions:
commercial external bulk portals, small indexed personnel/tool locks,
and full internal freight locks. The last demand the drum be stopped,
aligned and structurally hard-locked. A stopped freight drum may lose
its artificial-gravity handling regime and require cargo restraint
rechecks before restart.

Balance, temperature and cargo atmosphere are by drum/sector rather
than a single vessel-wide NORMAL. An inaccessible container or a
faulty thermal skid becomes a logistics and work problem, not
automatic loss of the entire 900,000 t reference cargo manifest.

## D. Atmosphere and pressure

Forty people require two physically distinct ECLSS trains whose
protected single-train duty is 40 persons. ECLSS-A and ECLSS-B can
be AVAILABLE, ON_LINE, STANDBY, LIMITED, ISOLATED, FAULTED, or
UNDER_LOCAL_CONTROL. The proposed normal gas-chemistry assemblies are ECLSS-A/B-O2-GEN
(each 40 kg/day oxygen from treated-water electrolysis) and
ECLSS-A/B-CO2-REGEN (each 45 kg/day carbon-dioxide removal).
Oxygen purity, hydrogen discharge/recovery and CO2 desorption/receivers
are physical conditions; see ENDURANCE_LEDGER_v0.5.md.

Process capacity and distribution path are
separate; a good train cannot clean air in an isolated zone that has
no open route to it.

Each hab arc is a distinct PZ-HAB zone. Each BR-nn is also a distinct
pressure volume with two independent end closures. Arc-local emergency
oxygen/cartridge scrubbers, the two 72-hour refuges and the two
30-day craft are real independent fallback levels. Pressure loss is
never corrected by a CO2 scrubber alone, and remaining oxygen mass
is not a proxy for cabin pressure integrity.

Breach response: detect/verify -> isolate smallest viable pressure
boundary -> account for affected occupants -> check leakage/recovery
path -> patch/repair/test -> deliberate repressurisation from actual
stock -> re-open only after objective conditions permit. A brief
bridge leak should not immediately decompress all eight arcs;
a failed closure or excessive isolation delay can enlarge the casualty.

Alarm indications may fail, an observation can lag, and knowledge
of hidden leak location belongs to the world until the crew obtains
enough measurements and physical evidence.

## E. Potable water, sanitation, cultivated food

Storage, potable processing, greywater, blackwater, dehumidifier
condensate and cultivation are different networks. Water does not
become potable by reassigning inventory to another tag.

Forty people: reference 1,000 L domestic use per day, 90%
domestic recovery, about 100 L/day unrecovered domestic use
before the additional growth-process and failure demands.
The 162 t normal voyage makeup includes about 73 t domestic
unrecovered use, 29.237 t gross water electrolysis feed,
35 t food/cultivation processing and the remaining technical
rejection allowance; the 70 t protected degradation reserve
remains separately counted. Any balance asserting
730 days endurance must explicitly include additional processes,
leaks, degradation and actual consumption rather than calling
the whole balance 73 t.

A processor fault can put the train in QUARANTINED even when a
pump runs. An operator can reroute compatible greywater or
activate local reserves only with valid valve boundaries and
water-quality checks. Do not drain protected emergency stock
automatically to satisfy normal crop irrigation.

The new INV-FOOD-LONG-LEG records 32 t of stored provisions,
including at least 24.82 t reference edible demand for
forty people over 730 days.

Three growth rooms supply additional fresh food, not long-voyage
calorie independence. Their pumps/lighting/nutrients are
load-sheddable before full-cabin survival loads except where
particular crop loss creates an explicitly tracked longer-term
supply concern.

## F. Heat rejection

Generation, ECLSS, refrigeration, fabrication and inhabited spaces
impose heat loads with real rejection paths. Radiators, coolant
circulation, pumps and rotary fluid interfaces have independent
states. The same battery that runs a fan cannot indefinitely
dump the compartment's accumulated heat.

A radiator wing under EVA repair is isolated, cooled and placed in
safe attitude, with demonstrated remaining thermal headroom for
current power/heat duty. If the remaining system cannot carry the
heat, stop nonessential generation or industrial loads first.
Failure to restore coolant circulation can force controlled
generator derating without immediately requiring every person
to abandon ship.

## G. Fire and damage control

Two segregated A/B fire mains, front and aft pressure sources,
sectionalised isolation, normally shut cross-ties and two
independent habitation inlets are explicit equipment and service
edges. Water mist is the common distribution medium, but actual
suppression agent depends on the local hazard.

Fire response: alarm -> verify from safe access or readings ->
prioritise persons and fire boundary -> isolate threatened
utilities/ventilation -> select the permitted local suppressor ->
deploy finite breathing/portable hardware -> clear and test
before restoring routes. An EVA work platform or a portable
damage-control pump has a current location; if assigned to a
different casualty, it is not simultaneously in its locker.

Smoke is preferentially contained and scrubbed/recirculated
within intact pressure zones. Venting to vacuum is a hazardous,
deliberate last-resort action with pressure and crew consequences.
Losing one fire-main section can be recoverable by correctly
configured opposite-main backfeed, but a closed cross-tie does
not magically supply the isolated line.

## H. External maintenance and propulsion

The external handhold/tether/rail system runs from bow EVA to
aft EVA even through the cargo-drum *central bores*. Being
outside the pressurised spine does not always mean being at
the ship's maximum outside radius.

Powered crawlers and larger work platforms have occupancy,
load and battery limits. Crossing onto a cargo drum's actual
external moving skin requires a stopped/aligned/hard-locked
drum; remote inspection bots can inspect selected rotating
surfaces but cannot perform arbitrary heavy repair.

External radiator work demands thermal isolation; aft
propulsion work demands positive drive inhibit, verified
residual energy and plume keep-out. Losing remote actuator
control does not transfer authority to an AI character or
the UI. Actual maintenance is local, permissioned and logged.

FTL and sublight drive performance remains fictional by
design, with defined bunker/reaction-mass, navigation and
thermal requirements. A drive fault can cause delay, fuel
cost, bad arrival geometry or inability to dispatch, without
pretending the 3.3 MW electrical plant is a 1.2 Mt propulsion
power source.

## I. Document-versus-installation truth

Every system with retrofits can hold:
(1) original intended layout, (2) the present actual
condition/configuration, (3) documents whose reliability
may vary, and (4) private crew interpretations. A successful
work receipt, obsolete drawing and reliable local sensor
are not interchangeable evidence.

Preserve specific current quirks: HAB-03 cabin control rewiring,
ECLSS-B mixed-generation gateway, BR-06 manual wet service,
BE-08 narrower filter extraction access, uneven bow shielding,
and the non-interchangeable HAB-03 scrubber fan controller.
Give such details maintenance consequences but do not
simulate random catastrophe solely to add drama.

## Priority acceptance scenarios after geometric completion

| Scenario | Required physical result |
| --- | --- |
| GEN-M trips at 1.55 MW demand | Alternate generation and staged shedding, no invented 0.75 MW load on 0.65 MW aux |
| BR-06 greywater sleeve leaks | Local pressure boundary and wet-service isolation remain distinct; worker can inspect locally |
| HAB-03 end hatch pressure seal degrades | Adjacent bridge can be isolated, crew routes change, seal test required before restoration |
| WR-01 machine tool requires 50 t replacement | Hard-lock freight route requires rotor stop without stopping habitation |
| Forward radiator panel hit | Isolation and rerouting only if surviving thermal capacity permits present load |
| HAB-07 atmosphere distribution isolated | Local ten-person/12h support available, subject to sealed volume and actual consumables |
| Aft EVA crawler already deployed | A second job cannot reuse it until recovered, moved or explicitly reassigned |

These are **future world acceptance** scenarios. They do not
assert that the unmerged Evennia prototype already simulates
the full physical ship.

## J. B′ physical habitation authority

The selected design has eight keyed centre saddles, sixteen sliding outer saddles and three physically distinct frame branches at each outer station. A seized outer slide and a failed centre key produce different faults; neither may be represented as a generic bearing off/on switch. Eight flexible pressure bridges allow about 125 mm normal relative service travel but should isolate and potentially block passage at the 450 mm exceptional excursion. Their pressure-spool IDs and independently isolatable wet/electrical sleeves are separate equipment objects. The habitation main drive/bearing/brake assemblies are also separate from the two phase-indexing **30 t** passenger carriers and their four capture collars. See `BPRIME_HAB38_MECHANICAL_CLOSURE.md`; this is a design-only contract, not gameplay implementation.

## K. Sectional pressure safety in actual ship topology

Trunk A and trunk B are each 23 separately pressure-sealable segments, with 22 inter-section automatic/pressure doors per trunk. Doors may be open in ordinary service, but each section retains its own gas identity so closing a door partitions pressure and flow instead of merely blocking walking. HAB-04 medical isolation and the A/B indexer final lifts have separate pressure boundaries. F1/F2 flywheel machine bays are vacuum by design behind service airlocks. The 72-hour, 40-person refuge modes protect the *entire* intact HAB-04/HAB-08 pressure arcs via cupboards holding consumables and machinery; occupants are not placed in those stores. See `PRESSURE_CELL_CLOSURE_v0.5.md` for the authored 133 cells and now 339 rated pressure boundaries, including 131 unclassified-environment thresholds. Net breathing volumes and real sensor/control behaviours are not yet simulated.
