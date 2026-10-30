# Cross-system contracts: implemented transport and future APIs

**Current boundary (30 October 2026):** Ox uses ordinary authenticated
Evennia WebSocket sessions, actor-bound game commands and verified OOB
receipts. G19 full-ship equipment operations remain world-authorized,
not model-owned. G7b supplies persistent typed social agreements; G10b
adds authenticated clock reads; the PostgreSQL journal assigns sequences
through commit. The G16c/d opt-in personality routes consume the G16a
authored disposition catalog, but no model-selected action thereby gains
physical authority. The Python `WorldPort` is an internal prototype,
not a public multi-character server or combined browser API.
See [implementation status](../design/STATUS.md).

## Ownership rules

| Information | Sole authority | Handler/view behavior |
| --- | --- | --- |
| Character identity, location, roles, watch, physical machinery | Evennia | Observe or propose via character-authorized game actions |
| Real game time and scheduled due events | Evennia | Verify `oxclock` nonce/actor before mapping game seconds to private memory ticks |
| World physical operation receipts | Evennia | Reconcile unknown by request ID; never infer success from text |
| Stable person IDs, formative aptitudes, professional skills, theoretical mastery, procedure familiarity and awarded learning | Evennia | Read only authorized observations; no agent self-awarded capability or credit |
| Private observations legitimately delivered to a character | Evennia | Feed only that character's Concordia memory |
| Beliefs, private reinterpretations, cognition clocks, plans and unresolved actions | AI handler | Owner-specific records, independent cognition revision and private checkpoints; never world authority |
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
- `oxevent <nonce> <event-id>` is a read-only indexed exact historical
  lookup over the **same** journal. One `ox_event_lookup` OOB frame
  returns `version=1`, the original nonce, the authenticated actor, the
  requested ID, `found|missing|oversized` and the complete original event
  only on `found`. Foreign-recipient and unknown IDs return identically
  `missing`; an oversized event is never silently truncated. The typed
  handler `WorldEventPort` checks nonce, actor, source identity, event
  kind, scalar data and replay provenance. A recovered event is evidence
  of a past observation, **not** current work authority or proof of
  obligation resolution. [Exact lookup contract](../design/prototypes/p4f-world-exact-evidence.md).
- `oxaction <32-lowercase-hex-request-id> <isolate|repair|commission>`
  applies normal Evennia role, locality and pump-state checks, writing
  an actor-bound record in the world. The reply is typed `ox_receipt`,
  not arbitrary narrative. `oxreceipt <request-id>` queries it later.
- `DurableEvenniaPort` accepts `succeeded`, `failed` or `unknown`.
  On unknown, the handler must reconcile the **same ID** rather than
  replay the command. An action proposal and a world-issued result are
  different records.
- Supported radio, handover, captain, education and G7b bilateral social
  operations use typed actor-bound world receipts. Free-text speech does not
  form a persistent agreement or prove a motive; arbitrary mid-scene
  activities are not all recoverable.

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

## G6–G12 additions and transport safety

- G6/G6b terminal actions and mortality remain opt-in game-authoritative
  fixtures. A service receipt proves an equipment operation, **not**
  restoration of an unrelated atmospheric breach.
- G7b `oxwork <request-id> social_<operation> social <encoded-arguments>`
  is a typed participant-specific transaction; `oxsocialstatus` is
  restricted to the parties. Agreed terms do not prove desire; work
  consideration requires verified, unused world-receipt evidence.
- G8–G9 private memories and interpretations belong to the handler.
  `cognition_revision` protects against stale detached inference and
  `OxMemoryContext` exposes only fallible, owner-relevant read-only
  history to native Concordia prompts.
- G10b `oxclock <32-lowercase-hex-nonce>` returns actor-bound `ox_clock`.
  `WorldClockPort` verifies actor, nonce and finite game seconds before
  advancing private time. G8's virtual GOAP decision clock is distinct.
- PostgreSQL journal allocation is **commit-ordered** under a single
  transaction-held lock. `oxinbox` cursors are recipient-scoped and
  replayable; work receipts use events causally emitted by the operation.
  New per-recipient SHA-256 prefix seals and a durable journal generation
  support `oxjournal <nonce> <actor-cursor>`, returning a nonce/actor-
  challenged continuity certificate for an exact addressed prefix.
  This establishes the world-side basis for the now-implemented cache
  validation gate, not a new authority or a bound on world history.
  [Protocol](../design/prototypes/p4f-journal-continuity.md).
  A-01 alarms and captain reminders follow P-01 → ticket → journal locks.
- PRs #85–88 established actor-private authenticated inbox hydration,
  delta pages, indexed historical records and exact world-event proofs.
  Attested cache reuse now persists the complete recipient-scoped index
  across handler processes. A new process must recompute the full local
  historical prefix and derived obligation state, then authenticate it
  against Evennia's `oxjournal` generation/recipient/cursor/digest
  certificate before requesting only the remaining world inbox delta.
  The native brain, private agenda and epistemic cursors remain separate;
  evidence indexed before an interrupted brain save is replayed without
  repeating physical work or fabricating receipts. Corrupt, missing,
  foreign, rewound or divergent evidence fails closed.
- Local hot/cold optimization keeps the most recent 256 addressed event
  bodies **plus mandatory live proof pins** available uncompressed. Every
  other original event remains retrievable, with case/kind metadata indexed
  and its complete body stored losslessly in compressed local SQLite cold
  storage. It does **not** delete world evidence or bound total disk use.
  Physical SQLite repacking requires both 2,048 accumulated demotions
  and enough new cold records to constitute 25% of existing cold history,
  preventing quadratic whole-file maintenance as the voyage grows. It
  occurs only after the attested history transaction commits, before
  the native cognition checkpoint can advance.
  Repacking preserves every source proof and its authenticated world seal.
  Cache reuse is conditioned on the complete authenticated actor prefix;
  no old event or receipt independently grants world authority.
  [Cache-continuity contract](../design/prototypes/p4f-attested-cache-reuse.md).
- `receive_matching()` preserves unrelated WebSocket frames in order
  under a 512-packet bound. On saturation it raises **before** reading
  another wire frame. Malformed unattributable `ox_receipt` frames remain
  unmatched and never count as the desired result. The requested ID,
  actor and status remain subject to fail-closed validation.

G11 is a small manual matched-evidence hosted-model A/B harness. G12's
6/20/40 local native-brain profile is **not** 20/40 live crew sessions
or hosted inference latency. Neither changes the world/handler boundary.

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

## G16a — shared authored disposition tags (experimental)

The independent, installable Pydantic v2 `ox-contracts` distribution defines
one versioned typed schema for five action-disposition dimensions: risk,
deference, social, autonomy and procedure. The [validator](ox_contracts/personality_actions.py)
loads the sole [authored data catalog](ox_contracts/data/personality_action_tags.v1.json).
Install with `python -m pip install -e ./contracts`; both the future
Evennia and handler consumers must use this exact package, not diverging
copies. Every tag is an explicit, finite JSON float in [-1,1], and each
semantic action and command signature must be unique within its menu.

Positive dimensions favour risk-taking, legitimate authority deference,
social assistance, self-direction and procedural conformity respectively;
negative values describe opposite inclinations and zero is neutral. The
manifest includes four G14 hypotheticals, the real opt-in P4a Evennia
pump-choice menu, the offline gauge pilot and four other offline dilemmas
(**10 menus / 32 actions**). [G16a CI](../.github/workflows/ox-g16-action-tags.yml)
checks schema rules and matches the catalog against those actual Python menu
sources via AST, without loading models or sending world commands.

Seven unambiguous G14 tags have a **retrospective** sign sanity check against
the numeric independent-minus-original mean native score shifts in
[final-head G14 CI #40028008764](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40028008764).
These directions were known when the tags were authored, so agreement is **not**
a blind prediction, tuned policy, or personality-quality acceptance result.

This package is preparation only. G16a does **not** attach tags to deployed
world messages or enable personality scoring. The approved action menu and
actor-specific permissions are still Evennia's; a tag is never a work receipt,
safety approval, factual observation, or grant of authority. The later **G16c/d opt-in implementations do consume the shared package**
and include its catalog digest in durable routing decisions. This does
not enable personality scoring by default or replace Evennia's authorization;
see the [current G16 status](../design/STATUS.md).
