# G3e-3 — Independent unanswered questions (verified)

**Merged implementation:** [PR #51](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/51), 50/50 final-head checks, merge `e1a92b3`.
**Historical G3e-2 baseline:** [Actions run 39247119254](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39247119254).
**Same-seed G3e-3 comparison:** [Actions run 39251131479](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39251131479).
**Final-head replication:** [Actions run 39251389912](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39251389912).

## Purpose

G3e-1 allowed the existing five characters to inspect a world-owned anomaly
and report separately fallible evidence; Lin could defer or propose a
tentative diagnosis. G3e-2 let a specialist **challenge an existing diagnosis**
before running further tests. The first real Gemini trial demonstrated two
failure modes: bridge deferral stopped everyone else, and specialists declined
to challenge an explanation even when it was wrong.

G3e-3 gives the four **existing** specialists (Ari, Iona, Mara, Teo)
independent authority to ask a **known unanswered diagnostic question**,
whether Lin has asserted a cause or not. No added rooms, roles, skills,
personality attributes, or root-cause omniscience.

## World / cognition boundary

1. A legitimate specialist personally receives an `anomaly_notice`,
   physically samples the original local instrument and files one
   `anomaly_report` WorkReceipt.
2. On their independent Concordia wake cycle, this character may choose
   **request independent measurement**, offer an alternative theory if an
   existing bridge assessment is present, or **defer**. A disagreement is
   not required for the first choice.
3. A question is accepted only via an authenticated `anomaly_question`
   receipt at the specialist's existing station. Evennia atomically stores
   that character's one question and evidence provenance on
   `InvestigationCase.questions` (migration 0006) and addresses a
   notice to Lin. A different character cannot borrow the question.
4. `oxprobe` produces a real world-sampled fallible diagnostic reading,
   repeat-stable within that case. It is visible only to the person
   performing the local measurement. The handler cannot see cause or
   world-private `probe_key`, and no actor can redraw indefinitely.
5. `anomaly_probe_report` sends the actual source-event-backed measurement
   to Lin. The specialist may subsequently propose a provisional
   hypothesis or report the measurement **without** a diagnosis.
6. Lin may revisit the question once the bridge receives at least one
   independent reported diagnostic from engineering and one from
   cargo/environment. `anomaly_reassess` accepts an unconfirmed tentative
   explanation whether the first-phase theory was correct, incorrect, or
   **deferred**. Existing world `assessment` and separate `reassessment`
   fields remain intact: no late theory rewrites hidden cause.
7. `AgentEpistemics.ask` records the existence of each character's
   known unknown. Verified world observations and fallible hypotheses remain
   distinct. An unknown unknown is not prematurely surfaced.

All world-affecting requests use the existing actor-bound immutable
`WorkReceipt` ledger, ship lock and atomic journal delivery.
A failed request ID cannot change into a success after evidence improves.
This case budget permits one additional diagnostic per eligible person.
The old challenge-first path remains available as a control.

### Opt-in use

With the existing G3e-1 case armed on a disposable or expressly opted-in ship:

```bash
export OX_G3E_INVESTIGATION=1
export OX_G3E_FOLLOWUP=1
export OX_G3E_INDEPENDENT_QUESTIONS=1
```

The external authenticated five-crew `serve` supervisor retains its normal
higher-priority alarms, hails and duty work. The bounded
`investigation-drain` and `followup-drain` modes are designed for
disposable trials. Set `OX_G3E_INDEPENDENT_QUESTIONS=0` to reproduce the
original G3e-2 challenge-before-probe behavior.

## Comparative observed behavior

The operator-only audit runs the **same five scenarios, causes and world RNG
seeds**, with four Gemini decision trials and one first-option-selecting
deterministic MockModel control. Source evidence resides in the
`scenario.md` and `scenario.json` job artifacts attached to each Actions
run; operator hidden truth is never included in crew prompts. Hosted model
choices are *not reproducibly seeded*, even with identical world evidence.

| Gemini case | G3e-2 baseline | G3e-3 first rerun |
| --- | --- | --- |
| Cargo vapors (seed 3) | Lin deferred; no second tests | Four independent tests; Lin formed correct but unconfirmed cargo-vapors theory |
| Scrubber bypass, initial false negative (seed 6) | Lin deferred; no second tests | Four independent tests; Lin formed correct but unconfirmed scrubber-bypass theory |
| Electrical interference (seed 5) | Lin initially correct; no second tests | Four independent tests, all `does_not_support`; Lin made no new assessment, original correct unconfirmed theory remained |
| All four initial signals elevated; scrubber bypass (seed 2) | Lin wrongly favored electrical interference; no second tests | Four independent tests; Lin reconsidered but retained the wrong electrical explanation |

**Aggregate, first rerun (four Gemini cases only):**
19/20 first-round participation before versus 20/20 after;
zero second-stage reports before versus **16 independent requests and 16
second-stage reports** afterward; two bridge deferrals each time, but both
deferrals in the G3e-3 run led to additional evidence and later provisional
diagnoses. End-of-run correct *available* bridge theory: 1/4 baseline
versus 3/4 first G3e-3 rerun. These counts are observations, **not**
statistically reliable estimates of model performance.

**Final-head replication:** all four Gemini scenarios again produced
independent specialist questions and post-test reports (15 reports
across four scenarios: one crew member did not join initial investigation).
The cargo and scrubber cases ended with correct unconfirmed bridge
hypotheses; the electrical case kept its original correct hypothesis
without a new recorded assessment; the all-elevated case remained wrong.
The scrubber case was especially informative: Lin initially proposed
the *wrong* electrical theory, then revised it after crew testing.

**MockModel:** In the first rerun, the deterministic control recorded
four independent questions, four probes and a new bridge hypothesis but
retained a wrong cargo-vapors guess. The old control had reached the
correct cause after four mandatory challenges, because MockModel selects
the first offered option; this is no evidence of general diagnosis quality.

## Verification and limits

World tests: 15/15 pass, including original behavior, actor-local authority,
replay idempotence, post-defer reports, unconfirmed wrong outcomes,
cross-department provenance, immutable failed requests and atomic rollback.
Five-crew legacy control and final-head observation battery also pass
(50/50 final-head checks).

This solves a **permission/scheduling** bottleneck, not general autonomous
scientific research: the four test types are still role-predeclared, model
choices are menu-bound, evidence quality is synthetic, and a confident wrong
diagnosis may persist even after additional testing. Do not claim repeat
accuracy, causal interpretation or unrestricted test invention on these results.
