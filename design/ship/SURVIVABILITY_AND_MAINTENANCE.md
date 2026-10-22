# Ox of Hephaestus — Survivability and Maintenance Layer v0.4

## Purpose

This layer makes the Ox behave like an old commercial ship that can be fought, isolated, repaired and recovered rather than a map that simply changes from `healthy` to `failed`.

It adds four linked systems:

1. damage control and firefighting;
2. exterior maintenance and EVA access;
3. local machinery-control stations;
4. layered backup life support.

The design goal remains verisimilitude for play. The data identifies useful physical boundaries, routes, equipment and consequences without modelling individual detector heads, hose couplings or fasteners unless a specific incident needs that resolution.

## 1. Damage control

### 1.1 Damage-control sectors

Every traversable space now has a `damage_control_sector`. The principal sectors are forward ship, forward cargo, forward flywheel, central Engineering, work rotor, aft flywheel, aft cargo, aft plant, each habitation arc, the habitation ring and exterior work.

Sector identity is operational. It can be used for casualty reports, smoke/fire isolation, local muster, route availability and damage-control assignments.

### 1.2 Fire main

The fixed spine has two separately sectionalised high-pressure water/mist mains, A and B. A forward fire pump and an aft fire pump can each feed both mains. Normally closed cross-ties at forward, central and aft positions preserve segregation while allowing a damaged run to be bypassed.

Two independent rotary fire-main interfaces feed a sectionalised habitation fire ring. Each habitation arc has a local mist manifold and hose point. Losing one bridge section does not by itself deprive the other arcs of fire-main access.

Water mist is the ordinary distribution medium; local automatic suppression uses the agent appropriate to the hazard. Generator, electrical, flywheel, work-rotor and fabrication spaces therefore do not all blindly discharge the same extinguishing agent.

The firefighting allocation is within the existing mission-fluid mass account. The model does not add a new unaccounted reservoir to ship mass.

### 1.3 Distributed equipment

There are twelve major fixed-ship damage-control lockers and eight habitation-arc lockers. Their normal contents include breathing sets, thermal imaging, portable extinguishers, patch/plug material, temporary hose and cable, portable lighting and basic casualty rigging.

Four portable damage-control pumps and six portable smoke-control fans are distributed around the ship. Portable equipment is finite: if a pump is installed as a temporary bypass in HAB-05, it is no longer sitting available in its locker.

Fixed pressure sectors have zoned fire/smoke detection loops at simulation granularity; individual detector heads can be expanded into objects only when a particular sensor fault matters.

### 1.4 Smoke

Smoke control prioritises pressure-sector isolation and recirculating cleanup. Venting a compartment to vacuum is a deliberate last-resort action with pressure, access and inventory consequences, not an automatic fire command.

## 2. Exterior maintenance

### 2.1 Fixed-spine route

The ship has a continuous exterior maintenance rail/handhold/tether route running from the forward EVA station to the aft EVA station. Through the cargo-drum regions this route lies in the vacuum annulus around the fixed spine and inside the drums' central bores; it is exterior to the pressurised spine even when it is not on the outside diameter of the ship.

Two powered rail crawlers carry two people plus tools/light equipment. A larger maintenance/rescue platform carries four people and up to roughly two tonnes of work payload.

### 2.2 Rotating drums

The fixed-spine route reaches bearing and hub work without requiring a person to walk on a rotating cargo drum. Human transfer to a drum's exterior skin/portal work zone requires the drum to be stopped, aligned and hard-locked.

Two remote inspection crawlers can perform visual and screening inspection on selected drum exterior surfaces without putting a person there. They do not replace heavy structural repair.

### 2.3 Radiators and propulsion

Each radiator wing has an exterior service zone. Close EVA requires the affected wing to be isolated and put into a maintenance attitude; Engineering must first ensure that the remaining heat-rejection system can carry the current load.

Aft propulsion exterior access requires propulsion inhibition, residual-energy and thermal checks, and positive confirmation of plume keep-out.

## 3. Local machinery control

Thirty-three major local-control stations are explicitly installed.

They cover:

- six cargo drums;
- all twelve cargo-drum bearing stations;
- both flywheel banks;
- all three generators;
- aft electrical distribution;
- low- and high-temperature thermal plant;
- both ECLSS trains;
- the adjustable-gravity workshop rotor;
- FTL machinery;
- sublight propulsion;
- forward and aft fire-main pumps.

A local station retains the indications and safe controls needed to inspect, trip, isolate and where appropriate start/run its plant when the ordinary shipwide control network is unavailable. Major stations have at least one hour of protected control-power ride-through.

Local control is not an authority loophole. It does not bypass mechanical interlocks, lockout/tagout, pressure boundaries or work permits. A local takeover is an action with attribution and a record.

## 4. Backup life support

Backup life support is layered. There is deliberately no invisible third full-capacity ECLSS train.

### Layer 1 — normal ECLSS

ECLSS-A and ECLSS-B remain the two full habitation processing trains. Either can support forty people at protected duty when distribution is intact.

### Layer 2 — fixed-spine plants

The forward and aft fixed-spine atmosphere plants remain independently useful for occupied fixed-spine work spaces. They provide local circulation/scrubbing and reduce dependence on the habitation ECLSS for people working in the spine.

### Layer 3 — isolated habitation arc

Each of the eight habitation arcs carries a local cartridge scrubber, local circulation and a protected 4.45 kg oxygen bank. At the reference oxygen rate this is nominally enough for ten people for approximately twelve hours.

Its purpose is to buy time during an isolated-arc or distribution casualty: diagnose, restore a route or move the occupants. It is not comfortable long-duration habitation and it does not repair a pressure leak.

### Layer 4 — refuge mode

HAB-04 and HAB-08 each have an independent forty-person, 72-hour refuge air-treatment package, their existing 0.75 MWh refuge battery, and a 106.8 kg protected oxygen bank.

The nominal refuge population occupies the adjoining spaces made available for refuge mode; forty people are not assumed to fit inside the 40 m² equipment store.

### Layer 5 — survival craft

The forward and aft survival craft each retain the already accepted independent forty-person, thirty-day life-support capability. They are the deepest local survival layer, not interstellar escape ships.

### Portable layer

Four portable scrubber/fan units and the breathing sets in damage-control lockers support rescue and temporary sealed-space work. Portable scrubbers remove CO2/trace contaminants and circulate air; they do not create pressure or oxygen.

### Oxygen accounting

The protected shipboard respiratory oxygen account is unchanged:

- HAB-04 refuge: 106.8 kg;
- HAB-08 refuge: 106.8 kg;
- eight arc-local banks: 8 × 4.45 kg = 35.6 kg;
- total: **249.2 kg**.

No duplicate protected oxygen stock was invented in v0.4.

## 5. Play-facing consequence

These systems are intended to create recoverable, legible work. A casualty can now produce states such as:

- one fire-main section isolated while the opposite main back-feeds the area;
- smoke contained but a personnel route temporarily unavailable;
- an external inspection requiring the aft crawler because the forward crawler is already deployed;
- a drum operable locally while its remote control channel is unavailable;
- an isolated residential arc living on twelve-hour local scrubber capacity while Engineering works the distribution fault;
- a refuge activated for seventy-two-hour protection without declaring the entire vessel abandoned.

The ship therefore has meaningful intermediate states between **normal** and **evacuate ship**.