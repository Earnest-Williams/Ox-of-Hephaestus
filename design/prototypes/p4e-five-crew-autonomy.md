# P4e — Five independently authenticated autonomous crewmembers

**Status:** PR #19 integration candidate; not a merged capability until the
real-server five-crew workflow and all earlier Ox regressions pass.

## Goal

The ship's existing three AI crew are joined by Mara Voss (Cargo Hold) and
Teo Hale (Environmental Plant). Unlike P4d's inert crew bodies, **each new
specialist has a nonprivileged authenticated WebSocket identity, a native
Concordia `EntityAgentWithLogging`, private ListMemory and checkpoints**.

One external event-driven process is responsible for five normal character
clients. It listens for addressed alarms without doing LLM work during idle
ticks. The world's P-01 coolant emergency takes priority, followed by an A-01
environmental fault, C-01 unsecured freight, player hails and routine watch
handover. No model controls the world event clock or writes physical Attributes.

## Concrete departmental work

- **Teo:** independent `atmosphere_alarm`, local saturated-cartridge
  inspection, authorized isolation, new inspection of isolated equipment,
  one physical cartridge replacement (consumes exactly one stock item),
  fresh serviced-unit inspection and restart, followed by verification.
- **Mara:** independent `cargo_shift`, local restraint survey, actual restow,
  a second inspection and load certification, followed by local verification.
- **Lin/Ari/Iona:** existing bridge alarm relay, GOAP pump recovery,
  independent reviewer approval, world-clock handover and player hails
  continue in the same event-driven handler.
- **Human players:** normal `oxhail mara = ...` and `oxhail teo = ...`
  lead to recipient-scoped requests; the specialist can choose a bounded
  status response sourced from equipment accessible at their station,
  not an imagined answer.

The supervised specialist routines are deliberately bounded procedures
selected through Concordia finite options and tied to actual world
readouts. **This is tested event-driven autonomy, not yet novel diagnosis
or open-ended language-based collaboration.** The deterministic CI model
uses Concordia MockModel; five simultaneous hosted Gemini models are
possible through the opt-in provider but not evidenced by deterministic CI.

## Exactly-once authority and recovery

P4e extends `oxaction` and `oxreceipt` beyond P-01, adding an explicit
`cargo` or `scrubber` target:

```text
oxaction <32-hex-request-id> restow cargo
oxaction <32-hex-request-id> certify cargo
oxaction <32-hex-request-id> isolate scrubber
oxaction <32-hex-request-id> replace scrubber
oxaction <32-hex-request-id> restart scrubber
oxreceipt <same-request-id> cargo|scrubber
```

The historical two-argument P-01 forms remain unchanged. Each fixture
records the authorized actor, operation, durable result and authoritative
physical event ID within the same database transaction as the effect.
Failure receipts remain failures on replay; another actor cannot claim
the prior request. A rejected or unknown outcome is **never retried with
a newly generated ID**.

Each specialist job checkpoint saves its current plan step and pending
request ID *before* the handler sends a potentially physical command.
On restart the handler queries `oxreceipt` for that exact character and
equipment; it never executes a second cartridge replacement after a lost
acknowledgment. A snapshot contains a character's private cognition and
in-progress task state, not another character's observations.

The CI acceptance test deliberately interrupts Teo after the world has
consumed one cartridge but before saving its acknowledgement. A fresh
five-client process must restore Teo, finish both specialist jobs, complete
a P-01 pump incident and its independent approval, answer two human hails,
honor the world-owned watch handover, and leave exactly one cartridge
consumed.

## Deliberate limits

The two specialists begin at their posted equipment, and this PR does not
implement independent movement or general-purpose freight delivery.
Both technical procedures are known finite action menus, not improvised
repairs. The supervisor executes jobs sequentially by hazard priority,
while keeping five independent cognitive states; it does not yet
parallelize conflicting jobs, dynamically auction work or negotiate
supplies. A crew choice to defer leaves a durable unacted obligation but
does not yet create a deadline-based retry policy.

P4d's `SKILL_TAGS` reserve distinct skill families for later use-based
progression. **No numerical skill XP, level, class, competence gate or
training feedback exists here.** The next milestone should award
competence from world-verified work and support supplies crossing
departments while retaining actor-local observation and durable receipts.

The three-crew historical `watch_service` remains supported. It must not
run simultaneously with the five-crew process against the same live ship.
The P4e fixture provisions separate disposable `OxBotMara` and
`OxBotTeo` accounts with `provision(include_specialists=True)`, writing a
five-role mapping to `.ox-state/p4e-ids.json` while preserving the older
three-role P3a identity file for regression tests.
