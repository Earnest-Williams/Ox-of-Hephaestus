# Propulsion and navigation

Sublight drive, attitude control, FTL passage and the helm. Sources:
[movement and rotary operations](../ship/G19_MOVEMENT_AND_ROTARY_OPERATIONS.md),
[propulsion bay service](../ship/G19_PROPULSION_BAY_SERVICE.md),
`game/world/ship_ftl_navigation.py` and the installed design data's
propulsion contract.

## The plant

| Part | What it is | Status |
|---|---|---|
| Main drive and RCS | Separately operated, each with its own fault gate; finite reaction mass; a propulsion thermal store that trips when hot | Runtime |
| Helm | Receipted `helm` and `attitude` actions, only at the primary bridge or aft propulsion control | Runtime |
| `FTL-TRANSLATION-FIELD` | FTL field system in `FTL-SVC` (life-extension refit); 0.2 MW auxiliaries, 150 kW of field heat | Runtime |
| `DEBRIS-RADAR-FWD` | Forward debris sensor, gen-3 replacement | Data |
| Local control | `LCS-PROP` (propulsion safing, feed, service), `LCS-FTL` (field safing, readiness) | Data |
| Navigation computer | **Decided:** a specialist AI, reasonably capable, on the backbone directly with no gateway, fitted on the bridge (`CMD-PRIMARY`). Not yet in the design data, where navigation planning is a local panel (`LP-NAV-PLANNING`) | New |

## Normal

| | Value | Status |
|---|---|---|
| Reference mass | 1,187,500 t at departure, including 900,000 t of cargo | Runtime |
| Sublight | 5,000 t standard reaction mass; about 4 km/s total delta-v fully loaded; 25 % protected; at most 0.001 g | Data (contract) |
| FTL envelope | 5–100 c; 400 t of fuel per light-year at reference mass, rising with the log of speed; 6,000 t bunker, 1,200 t protected | Runtime |
| Power | Thrust comes from the drive's own plant and reaction mass, not the 3.3 MW hotel bus; drive auxiliaries draw from the bus | Runtime |
| Heat | Firing fills the propulsion thermal store; LT cooling rejects it first ([cooling](cooling.md)) | Runtime |

## What the lead mind runs

**New:**

- **Holding course and attitude** between the captain's decisions, through
  the helm, within its delegated authority.
- **Burn planning and execution** as the captain approves: timing, duration,
  reaction mass and the heat it will cost habitat and cargo cooling.
- **FTL readiness:** fuel against route, field auxiliaries and heat, and the
  protected reserves.
- **Debris watch** through the forward radar, where its segment reaches.

Route, destination and when to burn are the captain's decisions.

**The navigation computer** is a reasonably capable specialist AI that speaks
the backbone's own protocol, so it needs no gateway. It proposes trajectories
and burns, can disagree with the lead mind, and can hold course and carry out
an approved burn on its own when the lead mind hands navigation to it.

It has **no personality by default**: it reasons about navigation, not about
people or loyalties. It has the capacity to run one. **Decided:** a personality
can be installed or removed **only at the machine itself, on the bridge** —
not over the network. So the lead mind cannot do it directly; it needs a
person on the bridge. Every install or removal is recorded as a change to
fitted equipment (**New**).

## What needs hands

**Runtime:**

- **Thermal-trip reset:** an engineer at `PROP-CTRL` waits for cooldown and
  resets the trip.
- **Propulsion bay entry:** main drive and RCS inhibited, helm coasting,
  attitude held, FTL inactive, drive heat low, a suited engineer, measured gas
  in the bay before the rated hatch opens.
- **Repairs** to drive, RCS and field machinery.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| Drive overheats | Thermal trip; an engineer must reset it after cooldown | Runtime |
| LT cooling short | The drive takes cooling first; habitat and cargo lose theirs | Runtime |
| FTL fault | Passage fails without free arrival; bunker mass is conserved | Runtime |
| Drive or RCS fault gate | That system is unavailable; the other may still work | Runtime |
| `LCS-PROP` gateway fails | Local safing still works; the lead mind loses drive telemetry | New |

## What it leaves behind

- **Helm and attitude receipts (Runtime).**
- **Reaction mass and FTL bunker accounting (Runtime).**
- **Position and velocity state (Runtime),** readable only at an eligible
  station.
- **Burn plans, approvals and course holds** in the remote command log (**New**).

## Open questions

1. What does the navigation computer depend on besides the bridge's power and
   the backbone?
2. How much of the helm does the lead mind hold without the captain on the
   bridge?
