# Medical

Physiology, treatment and moving casualties. Sources:
[crew physiology](../ship/G19_CREW_PHYSIOLOGY.md),
[medical care](../ship/G19_MEDICAL_CARE.md) and
[casualty transport](../ship/G19_CASUALTY_TRANSPORT.md).

## The plant

| Part | What it is | Status |
|---|---|---|
| `HAB-04-MED-PHARM` | Pharmacy; stock defaults to zero and is capped at 24 dressings and 12 kg of fluid | Runtime |
| `HAB-04-MED-TREAT` | Treatment room; up to two concurrent attended courses | Runtime |
| `HAB-04-MED-OBS` | Observation bay for convalescence | Runtime |
| Physiology | Per enrolled person: exposure to the gas of the cell they're in; breathing debits that cell | Runtime |
| Refuges | `HAB-04-REFUGE` and `HAB-08-REFUGE`, with their own air and oxygen | Data |

## Normal

- Each person breathes about 0.86 kg of oxygen a day from the cell they
  occupy (**Runtime**).
- Pharmacy stock is whatever was commissioned; nothing refills itself
  (**Runtime**).
- Nutrition and sleep are not modelled as physiology yet (**Runtime gap**).

## What the lead mind runs

**New:**

- **Watching exposure:** each person's cell conditions against the alarm
  limits, and warning anyone in a bad cell.
- **Stock:** pharmacy contents and what has been used.
- **Routing:** the safest route to the treatment room for a casualty, given
  doors, pressure and who can carry.

The lead mind does not diagnose; physiology is ordinary game-world condition,
not a medical system.

## What needs hands

All **Runtime**:

- **Care:** a medical crew member picks up kit at the pharmacy, carries it to
  the patient's room and treats them.
- **Observation:** a medical officer stays with the patient for the course.
- **Casualty transport:** a qualified lead and a capable helper carry the
  patient through each passage, taking at least 30 seconds or three times the
  passage's normal time; all three stay put until it completes.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| Bad gas in a cell | Exposure accumulates for everyone in it | Runtime |
| Incapacity | The person cannot travel or work | Runtime |
| Pharmacy empty | Care cannot be given | Runtime |
| A closed or damaged hatch on a carry route | The carry stops | Runtime |

## What it leaves behind

- **Health rows (Runtime):** per enrolled person, measured exposure and
  condition; each person reads only their own.
- **Receipts (Runtime):** kit pickup, delivery, care, observation, discharge,
  carries.
- **Pharmacy stock (Runtime).**

## Open questions

1. Who can read another person's health row? Today only the person themselves.
2. Should nutrition and sleep become physiology, given the food chain already
   records meals?
