# Communications

How the lead mind, the captain and the crew reach each other. Most of this is
**New**: the installed ship has little communications equipment beyond the
habitat comms nodes and the fire relay.

## The plant

| Part | What it is | Status |
|---|---|---|
| `HAB-01-COMMS-NODE` … `HAB-08-…` | Protected comms node in each habitat section | Runtime (relay); Data (hardware) |
| Bridge fire relay | Serious habitat alarms to the three command and engineering rooms | Runtime |
| `LP-COMMS-AFT` | Local panel in the aft comms room | Data |
| Event journal | World events delivered to recipients, with stable IDs and replay | Runtime |
| Intercoms, announcements, panel displays | How the lead mind and people speak across the ship | New |

## Normal

**New:**

- The lead mind can make **announcements** to a section or the whole ship,
  send **addressed messages**, call a compartment's **intercom**, and put text
  on any **panel display** it can reach.
- Crew can call the lead mind, the captain or each other from intercoms and
  panels.
- Every message has a route — which nodes and segments it crosses — and is
  delivered only if that route works.

## What the lead mind runs

**New:**

- **Routing:** picks a working route for each message and reports
  undeliverable ones.
- **Alarm relay:** extends the fire relay's honesty to every alarm it carries:
  a dead source is reported as lost, never as quiet.
- **The log:** keeps every message it sends and receives, with delivery
  status.

## What needs hands

- Repair of comms nodes and their protected supplies.
- Speaking face to face, which leaves no record unless someone reports it.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| A habitat detector or comms node fails | The relay reports lost links for that section | Runtime |
| A message's route fails | It is not delivered, and the failure is recorded | New |
| An intercom is in a dark room | It doesn't work; nobody hears the call | New |

## What it leaves behind

- **The event journal (Runtime).**
- **The communications log (New):** sender, recipients, route, time, delivery
  or failure. Messages are kept in a log the crew can read.

## Open questions

1. Is the habitat comms node the habitat segment's gateway as well as its
   comms hub?
2. Do people carry personal communicators, and are they tracked?
3. What does a face-to-face conversation leave behind, if anything?
