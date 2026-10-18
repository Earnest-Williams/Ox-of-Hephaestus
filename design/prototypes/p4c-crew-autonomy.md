# P4c — unified autonomous event dispatch and crew interaction

**State:** proposed in PR #16; merge only after the new one-process real
Evennia workflow and existing Ox regressions pass.

## Capability

The persistent external `serve` handler can respond to previously unseen
bridge cooling alarms, world-owned watch-handover events, and individual
addressed player hails. Idle waiting suspends on all three authenticated
character WebSockets without per-tick model calls. A fresh process replays
only recipient-private event inboxes and reconciles pending isolation
against the world-owned durable request receipt.

A player may ask an existing crew member for a short response through the
ordinary `oxhail lin|ari|iona = message` command. The world delivers an
individual `crew_hail` event to that crew character. Concordia selects from
bounded reply kinds; the world, not the model, constructs a factual
`status` reading from equipment accessible to that character.
`oxanswer hail-0001 status|ack|decline` is an ordinary crew command.
The addressed sender receives a `crew_reply` event, which can be recovered
from their own `oxinbox`. The world rejects a second outstanding hail to
the same crewmember, ensures a resolved hail receives only one reply,
and refuses to provide an absent local reading.

This is deliberately **not open-ended dialogue** or an untrusted prompt
controlling machinery. In particular, hailing an engineer cannot isolate
a pump. Physical operations still use the existing role-checked durable
world receipt, and watch acceptance still requires world authorization.

## Acceptance

`.github/workflows/ox-p4c-crew-interaction.yml` starts the real server,
then runs only `python -m ox_ai.runtime.watch_service serve`. The world
has one pre-existing low-pressure fault, one genuine timed handover and a
pre-delivered human hail. Without launching the P4a scenario script, the
single handler must repair, request independent review, commission, close,
perform the scheduled handover, and answer the addressed hail. After the
server stops, a separate shell verifies the world record and private reply.

## Boundaries

- The current dispatcher covers three named crew members, P-01, one
  handover and bounded replies. It does not implement a general job scheduler
  or natural-language dialogue.
- The operator supplies a fixture fault and hail before this CI run.
  The handler does not invent either world event.
- Deferred choices are not yet persisted as full first-class reschedulable
  obligations. Further work must implement deadlines and reconsideration.
- Social commands are world-deduplicated for answered hails, but arbitrary
  mid-command failures are not yet transactionally recoverable.
- Real three-hosted-model inference remains opt-in and is not a passing
  deterministic integration gate.
