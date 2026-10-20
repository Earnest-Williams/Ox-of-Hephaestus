# G6b: continuous autonomous terminal-response experiment

**Scope:** opt-in follow-up to the six completed G6 paired trials (PR #67).
PR #66's synthetic benchmark and PR #67's six full-world trial histories
remain unchanged and were merged before G6b was created.

## Findings prompting G6b

- The original full-world runner stopped each of six actors after *exactly
  four decisions*, long before the server-owned fatality. It missed critical
  atmospheric alerts as decision triggers.
- Its handler automatically moved people to a workstation after they chose
  an operation; G6b makes travel a separately selected character intention.
- It counted repeated addressed orders/reports as successful progress.
  G6b distinguishes new evidence from repeats in the world receipt path.
- Comfort could be attempted without a physically present colleague;
  the actor now sees recipient-scoped nearby living crew and only receives
  the option when somebody is actually co-located.
- A-01's nominal reading prevented Teo from exchanging a cartridge despite
  two real spares. **Nominal does not imply trustworthy sensor instrumentation,
  nor does it prohibit an authorized diagnostic substitution.**

## World effects and epistemic distinction

A-01's real finite stock, already represented in the fixture and physical
supply ledger, is consumed by the authorized environmental technician during
a safe diagnostic replacement. The operation isolates A-01, exchanges one
physical cartridge, and restarts the machine. The **work receipt reports
only the maintenance operation** and use of one spare; it does not announce
whether the pressure emergency improved. Teo must choose a subsequent
authenticated local survey and compare readings before drawing that
conclusion. The GOAP controller explicitly considers this post-service
observation rather than receiving an automatic diagnosis. The independent
differential-pressure crosscheck is a separate optional observation. No operator secret is
revealed to any actor: hypotheses of sensor or cartridge failure can still be
wrong, and actions cannot alter the hidden plenum fracture.

The world stores one newest addressed-evidence sequence per captain command
and one last transmitted finding per sender. Repeating a message without new
information returns a failed/no-progress receipt without sending five new
messages. If new private evidence arrives, a later update is again permitted.
Periodic re-inspection is still legal, and comfort is an addressed event for a
physically present colleague, not an empty receipt.

## Continuous six-person experiment

The new `continuous_trial.py` creates one independent coroutine per genuine
authenticated Evennia identity. Each character remains responsive to addressed
events, changing sensor urgency, and periodic watch intervals until world-owned
death **or an explicit safety ceiling**. The ceiling is **100 decisions per
character and 480 decisions total**, comfortably above the previous 137-decision
trial. The runner also retains an independent wall-clock watchdog. If either
turn ceiling is reached with anyone still alive, the run stops, preserves its
trace and marks itself **incomplete/turn-capped**, never successfully fatal.
The world's Script, not the handler, owns elapsed time and mortality.

The action menu is generated from the actor's authentic location,
recipient-specific observations, local stock and nearby crewmembers. Travel
is offered as an explicit intention, executed through ordinary Evennia exits
and followed by an authenticated arrival check. Work continues through
the existing actor-bound global WorkReceipt path. Monitoring and travel are
recorded separately from physical work, never fabricated into receipts.
GOAP uses personally observed urgency/evidence to select among competing
goals (diagnosis, life extension, reporting, welfare, and archiving).
These are **authored policy goals**, not free-form general reasoning. Gemini
is supported as an experiment option but **not run in this PR**.

The G6b refusal investigation found that nine allegedly duplicated
provisional assessments were not necessarily identical: changes in measured
oxygen, CO2 or danger interpretation were being ignored by world-side
deduplication. Assessment work now carries the *actor's own* conclusion,
confidence, reasoning, authenticated sensor reading, firsthand finding
fingerprint, and highest cited addressed event sequence. The world checks
authorship and evidence provenance but does not decide whether the conclusion
is correct. Only an identical normalized submission (including its evidence)
is refused as unchanged; reinterpreting old evidence, changing confidence,
receiving a new report, or seeing different atmospheric measurements remain
legitimate.

GOAP remembers the exact last accepted and refused submissions, including a
typed refusal reason. It does not blanket-suppress the assessment verb after
failure. Risk-band changes in either direction, new addressed evidence, new
firsthand findings, materially changed sensor readings within a band, and
changed interpretations can trigger reconsideration. Sensor changes below
the planner's relevance threshold may simply be monitored; the world does
not relabel genuinely different readings as duplicates. The immutable
actor-submitted content and its evidence are preserved in each WorkReceipt
and in the operator's post-run assessment audit. The signed sensor reference
is bound to one authenticated character, so another person's private
measurement cannot be cited as firsthand evidence.

The audit verifies six unique accounts, six deaths, a real critical alarm
received by each, continued decisions *after* the critical alert, and exact
one-to-one reconciliation of world receipts for all physical actions.
Real movement and watch decisions are distinguished.

### Intentionally narrow validation

The dedicated `ox-g6b-continuous.yml` workflow runs focused G6b world tests
and **exactly one non-generative GOAP integration trial (seed 241)**.
It does not run any Gemini trials. The historical six-trial G6 workflow is
manual-dispatch-only to avoid silently repeating paid model experiments.
Other existing repository checks may run because we modify shared Evennia
equipment code; the new scenario itself never requests the large test matrix.

## Questions for the single trial

- Can Teo cross-check doubtful instrumentation, replace a nominal cartridge
  when a spare remains, and then separately remeasure A-01 and atmosphere
  without receiving an unearned diagnosis from the work result?
- Does the captain move deliberately to Environmental Plant if atmospheric
  urgency makes use of an available reserve useful?
- Does each crew member continue reacting to evidence and urgent messages
  **after** the fourth decision and after the critical alarm?
- Do duplicate broadcasts and orders cease generating false progress?
- Are welfare actions offered only when a living colleague is present?
- Are all physical operations, including refused ones, backed by real receipts?

The result is a bounded, event-responsive *experiment*, not proof of
unconstrained autonomy. Keep the single run's artifact as evidence rather than
generalizing to model performance.
