# Ox AI Handler

**Status: P4 autonomous crew prototype.** The three native Concordia entities connect to real Evennia character sessions. A separately runnable event-driven watch supervisor restores agent checkpoints, follows world-owned watch deadlines, and reconciles a lost physical action receipt. The observer UI and production deployment are still unimplemented.

A separately installed Python service will supervise the game's significant autonomous NPCs. The cognitive engine is **[Google DeepMind Concordia](https://github.com/google-deepmind/concordia)** (Apache-2.0); the rest of the system—agent lifecycles, event routing, model workload coordination, persistence, world transport, and inspection API—is an Ox concern. There is one logical cognitive entity per NPC, not one operating-system process or inference server per NPC.

Read [Prototype 1](../../design/prototypes/01-autonomous-crew.md), the [Concordia decision record](../../design/decisions/0001-concordia-first.md), and [world authority rules](../../design/decisions/0002-game-master-world-authority.md) before implementing the service.

## Current directory structure

| Path | Planned responsibility |
| --- | --- |
| `src/ox_ai/agents/` | Concordia entity factory and typed action selection |
| `src/ox_ai/agents/components/` | Identity, duties, commitments, procedures, beliefs and planning components |
| `src/ox_ai/gm/` | Deterministic GM adapter for mock-world experiments; never a second physical-world authority |
| `src/ox_ai/ports/base.py` | **Provisional Python-only** world interaction contract |
| `src/ox_ai/ports/mock/` | Deterministic test-world backend |
| `src/ox_ai/ports/evennia/` | Ordinary MUD-client/WebSocket connections to Evennia |
| `src/ox_ai/scheduler/` | Agent wake-up triggers, urgency, game-time integration |
| `src/ox_ai/memory/` | Durable agent-owned memories, beliefs and checkpointing |
| `src/ox_ai/inference/` | Shared model client and inference budget |
| `src/ox_ai/observability/` | Structured logs and correlation IDs for human inspection |
| `src/ox_ai/api/` | Handler's authenticated API for the human interface and operator controls |

Most directories still contain package markers. The first real entity implementation is in `src/ox_ai/agents/crew.py`, with inference-call metering in `src/ox_ai/inference/usage.py`. It accepts character-scoped observations, proposes only bounded world commands, emits optional JSONL traces, and atomically checkpoints native Concordia memory together with unresolved request IDs. **It does not execute world commands by itself.** The temporary `game/world/ai_repair.py` experiment binds it to one existing Evennia character via ordinary command dispatch, not a network transport. The world contract does not define the final network API. The latter belongs in the shared [contracts](../../contracts/README.md).

## Python packaging

The `ox-ai-handler` distribution is **separate** from the inherited `evennia` distribution. From the repository root, with Python 3.12+ and a virtual environment active:

```sh
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -v
```

The above installs the tiny stdlib-only contract skeleton; there is no service entry point yet.

When beginning Concordia work, install the **optional** integration dependencies:

```sh
python -m pip install -e "./services/ai-handler[concordia]"
```

This requires Git and downloads a reviewed upstream Concordia commit. The published `gdm-concordia==2.4.0` release **does not include** the newer interrupt-driven GM, so don't silently swap it into tests based on current upstream source. The source pin is not a claim that Concordia has already been installed or tested here. Once we have a working experiment, lock resolved dependencies for reproducibility.

The `openai` dependency extra is used for Concordia's configurable OpenAI-compatible client (including possible local inference endpoints). An external inference server, credentials, and model weights are **not** bundled.

## Service invariants

1. Evennia or the mock world alone decides physical outcomes and authoritative game time.
2. NPCs receive only authorised, character-specific observations; no handler-wide omniscience.
3. `act()` proposes action; a separate world response confirms, rejects, or leaves the outcome unknown.
4. The deterministic GM must not call an LLM to settle the physical world.
5. NPCs and the world continue operating when the human interface is disconnected.
6. Decision operations have identifiers and agent-state revisions. Unknown outcomes require reconciliation, never automatic blind retries.
7. A later dedicated Evennia service endpoint replaces the transport only, not character cognition.

See the first scenario fixtures under [scenarios](../../scenarios/).


## P2: Three-crew event-driven mock watch handover

`ox_ai.ports.mock.watch_world` is a deterministic, authoritative mock world
with the initial engineering/bridge roster, explicit game clock, scoped
sensor observations, physical co-location checks and event receipts.
`ox_ai.agents.mock_watch` represents **three separate** watchkeepers:
Ari Sen, Iona Vek and Lin Sato. Each keeps a private observation journal;
there is no shared omniscient agent context.

`ox_ai.scheduler.watch.WatchSupervisor` wakes policies only for delivered
world observations and scheduled duties. In the runnable first scenario,
Ari remembers an unverified pump concern, briefs Iona at 07:55, and Iona
acknowledges before the mock world transfers the watch. Lin is not
privy to their engineering conversation. Quiet time causes zero wakeups
or LLM calls. Requests are idempotent, and a lost ACK can be queried from
the world after restoring the handler snapshot, without replaying an action.

This is a **mock-world P2 checkpoint**, not a live independent handler
connecting to Evennia and not yet the complete P2 fault-coordination gate.

Run it with Python 3.12+, from the repository root:

```bash
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_watch_*.py' -v
python -m ox_ai.scenarios.watch_handover
```

Once merged, the manually triggered **Ox three-crew watch handover**
GitHub Actions workflow runs the scenario with no API keys, Concordia,
or server installation on your own machine. It attaches a JSON artifact
with an operator-only world event ledger and separate agent memories.

See [Scenario 0](../../scenarios/shift_handover/README.md) and
[ADR 0007](../../design/decisions/0007-three-crew-watch-supervision.md).

## P2 Scenario 1: Coordinated cooling fault

The second P2 mock scenario extends the same three-crew watch supervisor
with a **world-authoritative** coolant pump, ordinary character-scoped
instrument readings and radio alerts:

- Lin on the Bridge receives the initial cooling alarm and radios Ari.
- Ari in Engineering inspects actual local telemetry and uses the existing
  model-free GOAP planner to isolate, repair and later commission P-01.
- Iona independently inspects the repaired pump and approves the safety
  release; only the mock world permits commissioning afterward.
- Ari verifies normal pressure before sending incident closure reports.

The mock world is the sole source of mechanical and authorization truth.
Every observation is scoped to one recipient. A new urgent safety reading
causes stale command rejection and local reinspection, and an ambiguous
isolation receipt is reconciled after handler restoration without
duplicating the physical operation.

Test and print the operator-only JSON record:

```bash
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_coolant_*.py' -v
python -m ox_ai.scenarios.coolant_fault
```

The credential-free, manually triggered **Ox three-crew coolant incident**
GitHub workflow runs the same experiment with no Concordia or LLM.

This is a *deterministic three-crew mock*, not a persistent Evennia server.
The mock chief-release requirement has not yet been introduced to real
Evennia P-01. P3 still needs proper character sessions, scoped observations
and reconnect-safe action submission. See [Scenario 1](../../scenarios/coolant_fault/README.md)
and [ADR 0008](../../design/decisions/0008-coordinated-coolant-incident.md).

## P1 one-engineer integration candidate

Install the optional pinned Concordia revision, then exercise a native Concordia entity with a deterministic model:

```bash
python -m pip install -e './services/ai-handler[concordia]'
python -m unittest discover -s services/ai-handler/tests -p 'test_concordia_*.py' -v
python services/ai-handler/examples/one_engineer.py
```

The deterministic model tests framework wiring, not language-model quality. The options selected by Concordia are *proposals*, with no world connection or effect. The separate `ox-concordia.yml` job must pass on the pinned source before P1 is treated as tested. A restored pending/unknown action needs later world-side reconciliation; the code never replays it automatically. P2 adds the mock world, event routing and genuine autonomous multi-agent coordination.

## In-process pump-repair experiment

The [game README](../../game/README.md#experiment-can-an-ai-engineer-physically-fix-p-01)
describes a bounded local integration experiment. It uses native Concordia
choices, a real Evennia engineer character, and actual game commands. CI
supplies a **scripted** choice model; model intelligence is only evaluated
through a separate opt-in live run with an inference endpoint. The generic
`inference/compatible_chat.py` adapter uses portable chat completions for
local OpenAI-compatible endpoints, avoiding the GPT-specific parameters
sent by Concordia's own hosted OpenAI adapter. Both models reject choices
outside the finite action menu.

This is *not* a completed external WorldPort, authenticated service, or
multi-agent simulation. Real room movement and pump operations cannot
bypass Evennia's world-side constraints.

## Free-tier hosted, typed decisions (opt-in)

The [ADR 0005](../../design/decisions/0005-typed-decisions-free-api.md)
adds a provider-neutral bounded choice contract and an optional Gemini
3.1 Flash-Lite backend. It returns a schema-constrained option identifier
through the existing Concordia `sample_choice` pathway, never a claimed
world outcome. Google requires `GEMINI_API_KEY` even for free usage.
No account, key, model download, hosted call or network access is required
for the offline tests.

Run the no-network adapter tests:

```sh
python -m unittest discover -s services/ai-handler/tests -p 'test_gemini_decisions.py' -v
```

To try the actual hosted model with the real pump fixture, see the
[game README](../../game/README.md#optional-free-tier-gemini-choice-experiment).
Inference runs synchronously inside the disposable developer trial only.
A real scheduler, GOAP baseline, timeouts and operator-safe failure handling
are separate milestones.


## Zero-inference GOAP planning

The independent GoapPlanner and GoapCrewAgent in this Python package have
no Concordia, model-server or API requirements. Search operates on a
character's symbolic beliefs and known action schemas; the world still
decides whether attempted physical actions succeed.

```bash
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_goap_*.py' -v
```

The real-world comparison and manual GitHub Actions workflow are described
in game/README.md and ADR 0006. This is narrow equipment expertise,
not a general replacement for dialogue or novel diagnosis by an LLM.


## P4b — Running the persistent watch supervisor

With the private development crew accounts provisioned and the Evennia
server running, install the optional Concordia and transport dependencies,
then start an independent handler process using the module command
`python -m ox_ai.runtime.watch_service serve`. It will block awaiting
character-scoped world events when no incident requires attention.

The disposable CI workflow runs `begin` and `resume` in separate processes
to deliberately lose a pump-isolation ACK and prove actor-bound reconciliation
without executing isolation again. Checkpoints are written beneath
`.ox-state/`. No inference or wall-clock polling is required while idle.

The default provider is a deterministic native Concordia test model. Set
`OX_COGNITION_PROVIDER=gemini` and privately provide `GEMINI_API_KEY` only
for optional hosted-model evaluations. Never expose development credentials
or serve the prototype to untrusted networks.
