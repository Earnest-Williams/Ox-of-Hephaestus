# Ox playable ship — authoritative Evennia game

**Status (18 October 2026):** Real three-compartment world; independent
authenticated AI-character transport; authoritative pump actions, private
alarms, chief/reviewer signoff, posted watch and persistent world-owned
handover deadline. A separately runnable three-crew handler exists. This
is a **small proving ground**, not the entire cargo freighter.
[Current milestone status](../design/STATUS.md).

All Ox ship content is under `game/`; the inherited `evennia/` engine has
not been converted into a different distribution.

## What is in the world

| Object | Game-owned behavior |
| --- | --- |
| Bridge | Lin Sato, posted roster, real-time pump telemetry and in-world radio |
| Connecting Passage | Ordinary movement between bridge and engineering |
| Engineering | Ari Sen, Iona Vek and physical access to pump P-01 |
| Cooling Pump P-01 | `normal → low_pressure → isolated → repaired → normal`; durable event history and physical command receipts |
| Ship roster | Active engineering duty holder, independent safety reviewer and handover state |
| Duty Script | Persistent `world.live_clock.ShipDutyClock` checks an armed world deadline; it never calls a model |
| World-private events | Receiver-specific `ox_event` observations and `oxinbox` replay; no cross-crew memory access |

The physically authoritative coolant loop is deliberately tiny. There
are no working propulsion, cargo-management, economy or character-skill
progression systems yet.

## Start the game

With Python 3.12+ and a virtual environment, run from the repository root:

~~~sh
python -m pip install -e .
cd game
evennia migrate
evennia start
~~~

Default settings bind **only to localhost**: Telnet `127.0.0.1:4000`,
web client `http://127.0.0.1:4001` and AI-character WebSocket
`127.0.0.1:4002`. Registration is disabled by the Ox development
settings; use an existing developer/test account or the one-time
Evennia initial owner setup. The first-start hook `at_initial_setup`
builds the ship. If the database predates it, from `game/` run:

~~~sh
evennia shell --command="from world.bootstrap import build_ship; build_ship()"
~~~

`build_ship()` is idempotent: it will not duplicate rooms or reset a
faulted pump, existing events or crew positions. Stop the local server
using `evennia stop` from `game/`. The private signing key lives in an
ignored `game/server/conf/.local-secret` unless supplied as `OX_SECRET_KEY`.
These settings are **not suitable for a public deployment**.

## Ordinary in-world exploration

From Limbo, the `board` exit leads to the Bridge:

~~~text
board
look
look console
look roster
aft
engineering
look pump
inspect pump
~~~

The route is:

~~~text
Bridge <--fore/aft--> Connecting Passage <--out/engineering--> Engineering
~~~

A **Developer-authorized** character may enter Engineering and use
`shipengineer` to acquire a test engineering role, then use
`shipfault pump` to introduce a synthetic failure. Only a character
physically present and authorized by the current world rules can
operate the pump:

~~~text
shipengineer
shipfault pump
inspect pump
isolate pump
repair pump
commission pump
inspect pump
~~~

These are actual game commands, not instructions to change `.db` fields.
The Bridge console permits **remote observation**, not remote repair.
When the P4 safety gate is enabled, the engineer must also obtain a
fresh independent safety release after repair, before commissioning.
The chief cannot self-approve during her own engineering watch.

## Authenticated three-crew protocol (P3)

The external AI handler connects through Evennia's ordinary JSON
WebSocket sessions. The game binds a nonprivileged account to one
specific character via an identity/nonce challenge.

- `oxidentity` verifies the caller's own character identity.
- `oxinbox <cursor>` replays private world events addressed to that
  character, with stable IDs, sender, time and scalar details.
- `oxradio` transmits a bridge alarm to the **currently assigned**
  engineer (Ari or Iona).
- `oxaction <request-id> <isolate|repair|commission>` issues a
  physical operation. The game returns an actor-bound, durable
  `ox_receipt`. `oxreceipt <request-id>` reconciles it if the response
  was lost; retrying with a new request ID would be unsafe.
- `oxrequest` requests independent safety review; `oxapprove`
  records a world-validated local inspection and signoff.
- `oxresolve` reports independently verified normal pressure.
- `oxhandover` and `oxaccept` transfer an in-world watch only after
  the correct due event, briefing and authorization.

See [wire and authority contracts](../contracts/README.md),
[`game/commands/crew.py`](commands/crew.py),
[`game/commands/ship.py`](commands/ship.py) and
[`game/world/live_crew.py`](world/live_crew.py).

## The genuine watch clock (P4b)

Earlier P3 acceptance fixtures used an artificial jump to 07:55
after closing the incident. P4b adds an **Evennia-owned persistent
`ShipDutyClock` Script**, which fires a due event according to a
world-stored time deadline. The fixture's `scheduled_clock=True` mode
arms a short experimental deadline; it is **not** a complete shipboard
calendar or realistic eight-hour schedule.

On the test handover, active engineering duty transfers from Ari to Iona.
Ari is separately assigned independent safety-review authority; Iona
cannot operate P-01 **and** approve her own commissioning. The second
coolant incident is therefore repaired by Iona and reviewed by Ari.

For executable evidence, use [P4b world tests](world/tests/test_autonomy.py)
and the [full P4b Actions workflow](../.github/workflows/ox-p4b-autonomy.yml).

## Automated game tests

From a repository-root environment with Evennia installed:

~~~sh
cd game
evennia test world.tests.test_ship --verbosity=2
evennia test world.tests.test_live_cooperation --verbosity=2
evennia test world.tests.test_autonomy --verbosity=2
~~~

Use `--verbosity=2`, not `-v 2` (Evennia reserves `-v` for version
information). These tests use Django's test database. The independent
full-server workflows validate session behavior and persisted SQLite
state separately. Focused CI is intentionally distinct from the large
inherited Evennia matrix.

## Live P4 demonstrations in GitHub

The most useful demonstration is **Actions → Ox P4b autonomous
two-incident ship → Run workflow** on `main`:

1. CI builds a disposable game with three ordinary bot accounts.
2. Three native Concordia entities perform finite choices during an
   initial P-01 fault; GOAP performs ordinary physics through receipts.
3. A game-owned watch event lets Ari offer and Iona accept the handover.
4. The world then develops a second fault; Iona is the active repairer
   and Ari must independently inspect/approve the release.
5. CI terminates/restarts the independent handler after a deliberately
   lost isolation ACK. It reconciles the same action ID and verifies
   the game's eight physical transitions—exactly two complete cycles.

`ox-p4a-concordia-crew.yml` tests a single live incident with three
native Concordia entities. `ox-p3-three-crew.yml` retains the earlier
purely deterministic three-client regression. All three use **synthetic
test data and a deterministic model**; they do not demonstrate unscripted
conversation among three hosted models. No Gemini secret is needed.

## Earlier single-engineer experiments (retained)

The in-process developer harness `game/world/ai_repair.py` predates the
external transport. It uses normal Evennia character commands, but
executes a local trial **inside the game process**. This remains useful
as a control experiment, not the current handler architecture.

After installing `./services/ai-handler[concordia]`, from `game/`:

~~~sh
evennia test world.tests.test_agent_repair --verbosity=2
evennia shell --command="from world.ai_repair import live_trial; live_trial()"
~~~

`live_trial()` is **state-changing**: it faults the real local P-01,
may move Ari, and validates the final world event history. Use a
throwaway database. For local OpenAI-compatible models, set
`OX_LLM_BASE_URL`, `OX_LLM_MODEL` and the necessary API placeholder/key.
For the older Gemini choice experiment, `OX_TRIAL_PROVIDER=gemini`,
`GEMINI_API_KEY` and `OX_LLM_MODEL` configure that in-process harness.
This older `OX_TRIAL_PROVIDER` setting is different from the P4 external
handler's `OX_COGNITION_PROVIDER`.

The manual **Ox live Gemini pump repair** GitHub workflow is available
with a repository Actions secret named `GEMINI_API_KEY`. It runs the
single-engineer test on synthetic ship data; it is neither an
always-on inference service nor a three-crew LLM benchmark.
Provider availability, free-tier terms and quotas are external and may
change. Do not commit credentials or real private player data.

The **Ox GOAP pump repair (zero LLM)** workflow tests the deterministic
engineer without a model, including a repeat-fault/replanning case.
Its reuse in P3/P4 does not mean GOAP can diagnose unknown machinery
or perform general language tasks.

## Boundaries and future work

P4b supplies a **runnable** independent `serve` supervisor, but it is
not automatically deployed by `evennia start`. Test provisioning in
`world/transport_probe.py` creates disposable accounts sharing one
CI password and refuses to overwrite existing accounts. Do not use it
as a production account registrar.

Only pump operations currently have full world-authoritative durable
receipts. Recovery from every possible mid-social-command crash is not
established; the documented two-process test specifically proves
unknown-isolation reconciliation. The browser observatory is deferred.

See [setup](../INSTALL.md), [handler operations](../services/ai-handler/README.md),
[P4 status](../design/STATUS.md) and [original P2 scenario](../scenarios/coolant_fault/README.md).
