# G16o — balanced binary proposals and per-host capacity observations

**24 October 2026. Experimental implementation; production remains off.**

The P4k report/defer work offer has two actions. G16n preserves its exact
station arguments, but G16c previously required three actions in its native
scorer, score adjustment, controller budget and saved-choice replay. Adding
an invented third world action would change the decision. G16o extends the
shared path to accept exactly two or three actions instead.

## Scoring and recovery contract

Each semantic option occupies every response-code position once: two native
System One forwards for a binary menu, three for a ternary menu. The complete
Concordia offer is canonically ordered before building the actor prompt.
Partial or malformed forwards fail closed. No generated chat text chooses
an action. The scheduler bills two or three native units respectively;
replaying a saved choice performs zero new native forwards.

Existing three-action **policy v1** arithmetic and ledger fields remain
unchanged. Binary choices use **policy v2**, two saved native picks and
`all_two_positions_per_semantic_option`. A two-action checkpoint cannot claim
v1, three forwards or three-position coverage. The surrounding ledger retains
its existing schema version. Actor, catalog, evidence revisions, prompt digest,
score arithmetic and original request identity remain checked on recovery.

The gain, shift cap, temperature and safety-lock constants are unchanged,
**provisional experimental inputs for binary v2**. The G16b calibration and
G16e behavioural holdout concerned three-action choices and do not validate
binary calibration, personality quality or a binary confidence threshold.
Synthetic safety fixtures check refusal and forced argmax only; a score is
not world authorization or a calibrated probability of correctness.

Tests exercise a separately injected **offline-only** report/defer catalog
with `round_report ship {station:cargo}`, actual native Concordia components,
synthetic logits, two-unit budgets, full prompt/order invariance, pre-adoption
checkpointing, crash replay and late-worker containment. The shipped catalog
is unchanged. No P4k or production supervisor is activated. Exact GOAP station
arguments are supplied by G16n PR #130, merged at `4f21481`.

## Native capacity measurement registered before execution

`scenarios/profiling/g16o_binary_capacity.py` uses the existing two-action
`offline.personality_gauge` menu, actual Concordia actor components, distinct
explicitly synthetic private histories and the same durable controller.
These are not the authentic G9 character histories or authenticated world
actors. No world connection, command or receipt is involved.

The native experiment runs on **three independently allocated CI runners**.
Each verifies the same Decider Q4 GGUF SHA-256
`c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b`,
weight revision `3b02c98fa0b19e9daab247d633095b6e8a6cd4c5`, publisher tokenizer
revision `d3a78581751d518bbfa9e871a6d84059554d53c5`, two CPU inference threads
and one shared native worker. CPU model, affinity, runtime package versions,
source SHA and runner sample identity are retained with each result.

Each runner measures, in this fixed order:

1. Six separate sequential binary decisions with a 120-second measurement
   ceiling, retaining every end-to-end sample, including the first decision.
2. Six, twenty and forty independently owned decisions arriving together,
   each with the unchanged **25-second queued deadline**.
3. Full drain of abandoned workers, checking that no late actor proposal or
   choice ledger was adopted and that started/finished forwards reconcile.

The six-sample median, sample P95 and maximum describe only that runner.
When all six native sequential samples finish, a planning estimate uses the
observed maximum plus 25% headroom. It is not a latency guarantee, an automatic
scheduler configuration or a production acceptance result. A censored baseline
or synthetic fixture produces no native capacity estimate. Queue completions
are actually observed, not extrapolated from that estimate.

Successful execution of the experiment means measurements and containment
were recorded. It does not mean the operational deadline passed. Native
All three [independent native CI samples](g16o-three-host-native-results-2026-10-24.md) are complete: median service times 13.804 / 23.638 / 39.797 seconds, 6/198 on-time burst proposals, all late workers drained. The operational capacity gate failed on every host. One independently checked [local native run](g16o-local-binary-results-2026-10-24.md) measured a 27.024-second median binary choice and zero on-time proposals across the 6/20/40 bursts; all late workers drained. The 25-second operational capacity gate failed on that host.

## Local structural verification

The original recovered branch passed **408 handler tests and seven strict contract
checks**, including sixteen G16o checks. The original ternary raw choice and
metadata were additionally compared directly against the `3bfffc3` source and
matched exactly under the same deterministic native-interface fixture.
All 145 Ox Markdown documents have valid local links; workflow YAML parses,
the CI scope guard passes, Python sources compile, and agent-context checks
pass. After integrating merged G16n, **414 handler tests** pass; the seven strict
contract checks remain green. These are local checks, not an asserted GitHub
CI run. The integrated code head subsequently passed **56/56 regular CI
checks**; the three-host native measurements are separately recorded above.

## Remaining activation gates

Target-host capacity and admission policy must accommodate actual measured
service variation; changing a timeout does not make a forty-character burst
fit one worker. Source-tagged world offers, station/role authorization,
authenticated forty-person work and original receipt recovery still require
their independent live acceptance. G16g's independent blinded human speech
review also remains separate. `OX_PERSONALITY_CHOICE` remains disabled in the
production supervisor.
