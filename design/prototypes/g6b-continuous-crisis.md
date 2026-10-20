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

The world continues to accept *genuinely different* actor-authored assessments
and verifies evidence ownership; this is not a world-enforced theory of
reasonable beliefs. In the first revised live trial, however, GOAP chose to
file 69 assessments in 142 decisions because every changed sensor reading
was treated as a reason to reconsider prognosis. Those assessments were not
technically identical, but frequent updating was neither useful nor the
intended crew behavior.

The corrected **actor policy** now separates ongoing operational urgency from
an established prognosis. A character makes an initial provisional prognosis
after receiving firsthand or addressed evidence. Thereafter, the character
does not reconsider or construct another prognosis unless NEW information
*contradicts* the previously accepted view. Further oxygen decline, higher
CO2, a more severe alarm, independent confirmation, or an isolated temporary
oxygen improvement are not counterevidence. They still trigger operational
responses, resource allocation and investigation.

The bounded non-generative policy can recognize two sources of disconfirming
evidence: (1) a typed, authenticated, actor-addressed report of a possible
sustained recovery or refuge; or (2) observed oxygen AND CO2 stability over
at least 24 game minutes, not a single potentially noisy sample. A subsequent
typed refutation can invalidate a reported candidate. Reports of confirming
deterioration or absence of safe refuge do not prompt another prognosis.
Typed contradictory reports are an extensibility contract, not a claim that
this fatal-world fixture currently produces positive recovery evidence.
GOAP remembers the evidence that triggered each assessment, as well as
the exact last accepted/refused submission and any refusal reason. It
suppresses an identical retry without banning genuinely changed assessments.

The character's ordinary choice menu, including the Gemini-accessible menu,
offers `terminal_assess` only when an initial assessment is due or a real
counterevidence gate opens. In a terminal failure where the evidence only
confirms continued deterioration, the expected behavior is **one prognosis
per character**, with all later attention spent on operational questions.
The 100-per-character / 480-total decision ceilings remain unchanged.
The immutable authored content and its evidence remain recorded in each
WorkReceipt and operator audit. World evidence provenance remains
character-scoped; neither the handler nor an actor reads the latent cause.

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
- Does each crew member form an initial assessment, then refrain from
  revisiting prognosis when worsening atmospheric readings *confirm* it?
  Do independently addressed contradictory reports or sustained instrument
  stabilization open a justified opportunity to revise it?

The result is a bounded, event-responsive *experiment*, not proof of
unconstrained autonomy. Keep the single run's artifact as evidence rather than
generalizing to model performance.
