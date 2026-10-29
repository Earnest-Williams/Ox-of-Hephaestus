# G19 — original EVA crawlers and drum-inspection robots

**Branch:** \`g19-complete-ship-systems\` · **PR #138** (single integration PR).

Four original machines, in their exact fitted rooms:

| Original identity | Family | As-built home |
| --- | --- | --- |
| \`EVA-CRAWLER-1\` | EVA rail crawler | \`EVA-FWD\` |
| \`EVA-CRAWLER-2\` | EVA rail crawler | \`EVA-AFT\` |
| \`DRUM-INSPECT-ROBOT-1\` | inspection robot | \`EVA-FWD\` |
| \`DRUM-INSPECT-ROBOT-2\` | inspection robot | \`EVA-AFT\` |

The model owns no added exterior room, depot, rail, hatch, battery supply
or structural repair tool. The reference \`eva_rail\` links and the installed
421-space geometry are used unchanged.

## Real vehicle operation

Operator commissioning with
\`commission_g19_exterior_mobile(operator_approved=True)\` validates
the original four equipment IDs, families, rooms and rated original rail.
A one-time \`survey_g19_exterior_mobile\` attests each existing,
independent, finite battery's **remaining charge** (kWh).
A later survey cannot mint a replacement battery.

An authorised, alive crew member must physically attend the original
\`EVA-FWD\` or \`EVA-AFT\` local station. The respective
\`LP-EVA-FWD/AFT\` control, electrical breaker and EVA record must be
sound. If the airlock is evacuated, the operator must actually be wearing
a live issued EVA suit. Local commands use durable, exactly-once receipts:

\`\`\`
oxplant <32hex> exterior_mobile DRUM-INSPECT-ROBOT-1 launch
oxplant <32hex> exterior_mobile DRUM-INSPECT-ROBOT-1 move:EXT-DR01
oxplant <32hex> exterior_mobile DRUM-INSPECT-ROBOT-1 scan
oxplant <32hex> exterior_mobile DRUM-INSPECT-ROBOT-1 move:EXT-BOW
oxplant <32hex> exterior_mobile DRUM-INSPECT-ROBOT-1 dock
oxplantread exterior_mobile:DRUM-INSPECT-ROBOT-1
\`\`\`

\`launch\` and \`dock\` are **45-second** timed operations using the
*original* forward/aft outer hatch. A real EVA pumpdown is required:
the original recovered-gas airlock must be in vacuum mode, its inner
hatch positively closed, the named pressure cell actually depressurised,
and the outer hatch physically open. The as-fitted electrical panel
and breaker must be live/sound. Commands may never fabricate an airlock
cycle or use the opposite dock.

\`move:EXT-...\` is a **30-second** *single-hop* move along an as-authored
\`eva_rail\` link. Only original vacuum-to-vacuum \`EXT-\` vertices and
existing live/rated rail links qualify. The engine refuses distant
teleports, damaged rail, occupied rail sections, conflicting exterior
berths, propulsive acceleration and unsafe ship attitude. Drum rotation
requires stopping before **close inspection**; movement along the fixed
rail remains possible beside rotating drums. A robot does not silently
cross the separately fitted, normally closed 180-second skin-platform link. It conserves the original independent battery:
simulated draw is 12 kW while crawling and 4 kW for a smaller robot,
times the *actual active seconds*. These are coarse game rates, not
engineering certification figures or new power circuits.

## Inspection evidence

The installed inspection robot can order a **20-second** \`scan\` only
while stationary at an original fixed-rail \`EXT-DR01..06\` station
adjacent to its separately rated \`EXT-DR01..06-SKIN\` work platform with
the corresponding original rotor stationary, braked and hardlocked.
The sample is taken **at job completion** from authoritative rotor
state and retains the actual rail station, observed but **unentered**
skin platform, rotor RPM, condition, brakes, hardlock and sample time. It is remote *observational evidence*,
not arbitrary hull-health revelation, a hidden leak sensor, or a
powered structural repair. Each exposure consumes separately metered
2 kW inspection power.

The full ship clock records cumulative energy expended, completed
rail sections, successful scans, each machine's position, current
in-progress travel and its last sampled evidence.

## Failure and recovery

A faulted, seized or destroyed original machine stops and **latches**.
A broken link, loss of airlock readiness, spinning drum, ship manoeuvre
or missing battery blocks travel *without completing it* or inventing
fresh power. No command can teleport stranded equipment home.

\`hold\` preserves the job/position and charge; \`reset\` is allowed
only once the original machine has been physically restored to a
nonbroken condition. The operator must then explicitly order
\`continue\`. A returned machine physically follows its original
rail hops and 45-second airlock ingress. Depleted units out on rails
remain recovery incidents: no phantom automatic recharge or
instantaneous salvage.

While a crawler is deployed for remotely controlled work, the original
human EVA traversal cannot simultaneously use that same machine.
Likewise a real EVA crew transit/worker occupying the exterior inhibits
a new unmanned crawler job. Deployed mobiles inhibit propulsion,
attitude and translation release; drum-skin occupancy inhibits
rotation of that particular fitted drum.

## Verification and audit status

Dedicated workflow:
\`.github/workflows/ox-g19-exterior-mobile.yml\`.

The pure gate tests original identity, one-time finite battery survey,
real rail links, timed launch/return, rotor hazards, inspection,
failure latch, manual restart, exactly-once clock and collision gates.
The installed Evennia gate performs actual suit issue, inner-hatch
entry, airlock depressurisation, external release, remotely driven rail
movement and drum-skin scan, reverse rail return, operator receipts,
independent crawler failure and restart.

**Accepted:** both pure and installed Evennia tests passed in
[CI #40924922323](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40924922323),
tested at `2ebab10d`. The updated **808-original/91-family** strict
equipment audit also passed both jobs in
[CI #40925404027](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40925404027).
All four original exterior vehicles are now in the directly exercised
physics category; **zero outstanding independent equipment interactions**. Permanent structural repairs, exterior
replacement of depleted batteries and autonomous multi-vehicle
dispatch are not implied by observational robot acceptance.
