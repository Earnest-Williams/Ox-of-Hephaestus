# Cross-system contracts: implemented transport and future APIs

**Status (19 October 2026, through merged G4h):** Ox has a working **ordinary Evennia
WebSocket + game-command/OOB protocol**, and a provisional Python `WorldPort`
type interface. It does **not** yet publish a versioned, independent
multi-character service endpoint or a browser/handler API.
See [implementation status](../design/STATUS.md).

## Ownership rules

| Information | Sole authority | Handler/view behavior |
| --- | --- | --- |
| Character identity, location, roles, watch, physical machinery | Evennia | Observe or propose via character-authorized game actions |
| Real game time and scheduled due events | Evennia | Follow delivered timestamps/deadlines |
| World physical operation receipts | Evennia | Reconcile unknown by request ID; never infer success from text |
| Stable person IDs, formative aptitudes, professional skills, theoretical mastery, procedure familiarity and awarded learning | Evennia | Read only authorized observations; no agent self-awarded capability or credit |
| Private observations legitimately delivered to a character | Evennia | Feed only that character's Concordia memory |
| Beliefs, memories, plans, proposed decisions and unresolved actions | AI handler | May be stale; persist by individual agent |
| Joined dashboards and charts | Future interface | Derived and permissioned; never world authority |

## Implemented ordinary-client wire path (P3/P4)

- Each AI character has its own ordinary Evennia account/session and an
  account-bound puppet permission. The first handshake is `connect`,
  `ic <character-dbref>` and a nonce-backed `oxidentity` proof.
  Bot passwords are not stored in Ox source code.
- The wire uses Evennia's existing `v1.evennia.com` JSON framing.
  Character speech/text cannot stand in for a world receipt.
- A private `ox_event` is an **addressed** game-produced OOB message:
  `event_id`, `recipient_dbref`, `sender_dbref`, `kind`,
  `game_time`, `text` and flat `datum_*` scalar fields for details.
  Nested object dictionaries are **not** valid Evennia OOB payloads.
- `oxinbox <after-sequence>` returns only the authenticated character's
  own persisted events, followed by `ox_inbox_done`. The handler
  verifies recipient, stable ID and framing before placing an event
  in that character's memory.
- `oxaction <32-lowercase-hex-request-id> <isolate|repair|commission>`
  applies normal Evennia role, locality and pump-state checks, writing
  an actor-bound record in the world. The reply is typed `ox_receipt`,
  not arbitrary narrative. `oxreceipt <request-id>` queries it later.
- `DurableEvenniaPort` accepts `succeeded`, `failed` or `unknown`.
  On unknown, the handler must reconcile the **same ID** rather than
  replay the command. An action proposal and a world-issued result are
  different records.
- Game-side release approval, radio and handover events are
  recipient-scoped, but **not every social action** has a durable
  physical-style receipt or crash-recovery guarantee.

This is **Ox's current convention on top of ordinary game commands**,
not a stable publicly versioned network schema. See
[`game/commands/ship.py`](../game/commands/ship.py),
[`game/commands/crew.py`](../game/commands/crew.py),
[`world.live_crew`](../game/world/live_crew.py), and the
[external port](../services/ai-handler/src/ox_ai/ports/evennia/durable.py).

## Extended world-owned work and learning (G3–G4)

In addition to the early `oxaction` form above, the game now exposes
`oxwork <request-id> <operation> <subject> ...` and
`oxworkreceipt <request-id>` for typed, globally actor-bound transactions.
The world validates role, locality, current observation and operation-specific
preconditions; receipts and effects are committed together. This common
namespace covers supported physical work, captain handoffs, investigative
reports and the G4g/G4h learning stages. A successful submission receipt
**does not imply a passing assessment**: the actor's addressed assessment
event supplies that result. Replaying the same ID cannot repeat a physical
effect or educational credit, and an unrelated character cannot query it.

G4f practice credits only selected **successful, actual** P-01/C-01/A-01
work receipts. G4g credits one supervised controlled-comparison curriculum
after a world-graded transfer assessment. G4h credits bounded
`investigation.methods` study after a real local question, saved pre-test
forecast, receipted probe and delayed evidence-limits/source-independence
assessment. Hidden causes, bridge hypotheses and unearned role claims cannot
be grading inputs. World capability records remain distinct from an AI's
private belief or self-description. See [G4f](../design/prototypes/g4f-world-receipt-learning.md),
[G4g](../design/prototypes/g4g-verified-conceptual-learning.md) and
[G4h](../design/prototypes/g4h-investigative-learning.md).

## Python-only contract

`services/ai-handler/src/ox_ai/ports/base.py` defines `WorldObservation`,
`ActionRequest`, `ActionOutcome` and the `WorldPort` async protocol.
It is an **internal prototype abstraction**, not a claim that all
implementations already satisfy a formal versioned remote schema.

An observation is delivered to exactly one character with provenance.
A request carries a stable ID, intended character/operation and agent
revision. A missing/ambiguous receipt stays unknown. An agent's
recorded narrative or belief is not an alternative source of physical
truth. On restart the game may continue to progress even while the
handler has missed private events, which must be replayed **only when
legitimately addressed to that character**.

## Planned API boundary (P5 postponed)

Future human inspection requires **two separately authenticated APIs**:
an Evennia-facing world read model and a handler-owned cognitive read
model, joined in the interface with provenance and access control.
Before making those public, design schema versions, pagination/cursors,
stable agent-to-character IDs, access roles, operator-only endpoints and
private-event retention. There is no live API server or published
OpenAPI/JSON wire schema today.

See the [architecture](../ARCHITECTURE.md) and
[deferred interface](../services/interface/README.md).
