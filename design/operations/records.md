# The ship's records

Every record the Ox keeps, who can see it, and whether it exists today. If
something happened and the world could know it, it belongs in a record here.

**Rules for every record:**

- The world writes it; no character, gateway or handler can write it directly.
- It keeps the game time of the event and of when it was recorded.
- It is append-only. Corrections are new entries that point at the old one.
- It survives restarts without loss or duplication.
- Who may read it is part of the record, not of the interface.

## Records that exist today

**Runtime.**

| Record | What it holds | Where it lives |
|---|---|---|
| **Event journal** | Recipient-scoped world events with stable IDs, commit-ordered, paged replay | `CrewEvent`, `JournalEpoch`, journal chain ([ADR 0009](../decisions/0009-durable-events-and-work.md)) |
| **Work receipts** | Every consequential action: request ID, actor, target, outcome; replays deduplicated | `WorkReceipt` |
| **Alarms** | Per panel: stable key, first and last witnessed time, severity, count, active or cleared, human acknowledgement with who acknowledged; 2,048-entry transition ring | [Instrumentation](../ship/G19_INSTRUMENTATION_AND_RECOVERY.md) |
| **Electrical meters** | Generated kWh, shore imports, battery and flywheel charge and discharge, load delivered and not served, trip meters, cartridge magazine and spent-housing custody | [Power](power.md) |
| **Equipment condition and wear** | Condition per equipment row; service hours since maintenance, wear stage, repair timestamps and prior failures for the 26 secondary machines | [Wear and maintenance](../ship/G19_EQUIPMENT_WEAR_AND_MAINTENANCE.md) |
| **Pressure cells** | Gas masses per cell, including oxygen and CO₂, temperature, damage, leaks, smoke | Physics state |
| **Crew physiology** | Per enrolled character: measured exposure, condition; breathing debits the occupied cell | [Crew physiology](../ship/G19_CREW_PHYSIOLOGY.md) |
| **Food chain** | Stock per store, items taken and delivered, meals cooked, served and eaten (receipted), refuse mass carried and deposited, crop biomass | [Food operations](../ship/G19_FOOD_OPERATIONS_AND_ACCEPTANCE.md) |
| **Cargo climate** | Per drum: temperature, target, cooling output; per sensitive lot: quality, time out of band | [Cargo](cargo.md) |
| **Cargo manifest** | Lots, positions, splits, transfers; manifest hash in clock snapshots | [Movement and rotary operations](../ship/G19_MOVEMENT_AND_ROTARY_OPERATIONS.md) |
| **Indexed transfers** | Each drum, workshop or habitat transfer: request, start, completion, who moved | [Indexed personnel transfer](../ship/G19_INDEXED_PERSONNEL_TRANSFER.md) |
| **Inventory and supply** | Items, custody, supply orders | `InventoryItem`, `SupplyOrder` |
| **Investigations** | A case's latent cause, sampled evidence, reports and assessments, kept out of observations unless relayed | `InvestigationCase` |
| **Captain's obligations** | Commitments the captain has taken on | `CaptainObligation` |
| **Character records** | Profiles, skills, knowledge, techniques, learning evidence | `Character*` models |

## Records the operations need

**New.**

| Record | What it holds | Why |
|---|---|---|
| **Access log** | Each motorised door, hatch and lock: opened, closed, sealed, by switch, by the lead mind or by hand, from which side, when. **Who** only at controlled-access points: the ship's entrances, the bridge and the lead mind's machine rooms | Ordinary movement through doors is not recorded today. |
| **Location history** | Where each person was last seen, by which source, and when | Built from the access log, cameras, suits and panels; never complete. |
| **Gateway traffic** | Per gateway: readings passed, commands requested, accepted, attempted and refused, link-state changes, mapping revisions | The core of provenance on the network. |
| **Local control log** | Takeovers, hand-backs and emergency trips at each local control station, with who and why if given | Required by the local-control contract ("local takeover is logged"). |
| **Remote command log** | Every command the lead mind sends, with its request ID, reason and authority | So the lead mind's own actions are as auditable as anyone's. |
| **Communications log** | Messages, announcements and intercom calls: sender, recipients, route, delivery or failure | So what was said, and whether it arrived, is a fact. |
| **Sensor histories** | Time series per channel at stated retention, with gaps marked as gaps | Alarms alone don't show trends. |
| **Maintenance history** | Scheduled, deferred, done and verified, per unit, across all machinery, not only the 26 secondary machines | So "due", "overdue" and "worn early" are measurable. |
| **Consumables ledger** | Per person and per space where measurable: oxygen, water, food, medical supplies | So stores can be accounted for and forecast to the end of the voyage. |
| **Core log** | Machine state, parity layout, rebuilds, and every handover of a system to a subsystem and back | So the lead mind's own health and delegations are facts, not claims. |
| **The lead mind's model** | Its expectations: what each command should change, what each reading should be | So mismatches between expectation and world are themselves records. |

## Who can read what

| Reader | Can read |
|---|---|
| **The world** | Everything. |
| **The lead mind** | Records that reach it over working network paths, plus its own logs. Nothing behind a dead or isolated segment, nothing from a blind spot, no private crew cognition. |
| **A crew member** | Their own receipts and events; local panels in their room; records they are shown or told about. |
| **The captain** | As crew, plus whatever the captain's standing orders make available. |
| **Developers** | The developer view of the read model, which is never a player view. |

## Retention

**New.** Each record states how long it keeps detail. The alarm ring's 2,048
transitions are the only stated limit today. Where retention runs out, the
record says what was dropped, so an absence of evidence is never mistaken for
evidence of absence.
