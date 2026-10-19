# G3e-3 — Independent questions: implementation and observed behavior

**Status:** merged in [PR #51](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/51) on 19 October 2026; 50/50 final-head checks successful. The same five existing Concordia crew, seven compartments, and original atmospheric analyzer anomaly are used. No new skill, personality, crew or room has been introduced.

## The authority change

Under G3e-2, a crewmember could run a further diagnostic only by *challenging* Lin's specific existing theory. Two actual Gemini scenarios showed Lin declining to supply any theory, which blocked all follow-up experimentation. Where Lin did propose a theory, no Gemini specialist chose to challenge it, including one case where Lin was wrong.

G3e-3 permits an independently authenticated specialist who has filed their own initial firsthand reading to **open one world-receipted unanswered question** about the discrepancy without contradicting Lin or obtaining a new bridge diagnosis. At their existing installed station, they can take one probabilistic follow-up measurement; repeated reads return the same persisted world evidence and event ID. They then send Lin a firsthand instrument report, with immutable provenance, and *may* propose an uncertain hypothesis or withhold judgment. Lin can assess the new evidence even after an initial deferral. Reported instrument readings do not become verified root-cause conclusions.

- World primitive: `anomaly_question` through the original global, actor-bound `WorkReceipt` mechanism. The question and two addressed notifications are transactionally committed; no remote or role-bypassing test.
- Persistence: `InvestigationCase.questions` (additive migration 0006), distinct from `challenges`, `probes`, `reconsiderations` and `reassessment`.
- Handler: `IndependentInquiry`, enabled with `OX_G3E_INDEPENDENT_QUESTIONS=1`. Without this flag, existing G3e-2 challenge-only behavior still runs.
- Authority boundary: Evennia retains latent cause and probabilistic instrument outcomes. The external agent cannot access that cause or other actors' private readings; it receives only its own events and correctly addressed reports.
- Limits: this is **one bounded follow-up test per eligible specialist per case** with fixed role-local instrument selection, not general scientific planning, arbitrary experiments, continued investigation indefinitely, or correctness guarantees.

## Comparison method

Three sets of disposable world-and-handler trial jobs used the same four scenario causes and integer seeds, plus a separate deterministic control:

| Source | Workflow | Description |
| --- | --- | --- |
| [G3e-2 baseline](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39247119254) | Original five-scenario observation battery | Four Gemini cases + deterministic MockModel control; no independent-question authority |
| [G3e-3 first rerun](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39251131479) | Same cases and seeds | Independent-question authority on; four Gemini cases + deterministic control |
| [G3e-3 final-head rerun](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39251389912) | Same cases and seeds, final implementation head | Independent-question authority on; four Gemini cases + deterministic control, all five successful |

Every job separately provisioned five authenticated crew accounts, armed a world-owned latent cause, executed initial and follow-up handlers, then **audited the world outside crew sessions**. Each job published a `scenario.json`, a readable `scenario.md`, and run logs as a time-limited artifact. The after-the-fact operator report alone states the actual physical cause.

The seeds reproduce **world-side observations**. They do not force Gemini to choose the same action or answer across runs. MockModel makes deterministic first-option choices and is **only an integration control**, not evidence of inference quality.

### Original G3e-2 versus final-head G3e-3

| Hidden cause / seed | Before: initial judgment → later | After: initial judgment → later | Independently requested new tests |
| --- | --- | --- | ---: |
| Cargo vapors / 3 | Lin **deferred** → no further work | Lin **deferred** → cargo vapors (correct, unconfirmed) | 4 |
| Scrubber bypass, misleading reading / 6 | Lin **deferred** → no further work | Lin **bus interference** (wrong) → scrubber bypass (correct, unconfirmed) | 4 |
| Bus interference / 5 | Lin bus interference (correct, unconfirmed) → no further work | Lin bus interference (correct, unconfirmed) → no second assessment | 3 |
| All four signals elevated, scrubber bypass / 2 | Lin bus interference (wrong, unconfirmed) → no further work | Lin bus interference (wrong) → bus interference again (wrong, unconfirmed) | 4 |
| Deterministic MockModel, scrubber bypass / 6 | Mock initially wrong cargo vapors; four *challenges* and tests → correct scrubber bypass | Mock initially wrong cargo vapors; four *independent questions* and tests → still wrong cargo vapors | 4 |

In the **final-head four Gemini runs** there were **19/20 initial firsthand crew reports**, **15/15 eligible independent-question requests**, and **15 additional world-recorded follow-up instrument reports**. The corresponding baseline Gemini runs had **19/20 initial reports and zero follow-up instrument reports**. Of the four final-head Gemini cases, three ended with an available correct *provisional* diagnosis (including the original correct bus theory), and the ambiguous all-elevated case retained a wrong diagnosis.

The **first G3e-3 rerun** had 20/20 initial reports, 16 independent questions and 16 additional reports. Its final diagnostic outcomes had the same aggregate 3/4 correct available provisional theories, but individual crewmember participation and positions differed. This variation is not an A/B accuracy estimate: the small sample, different action menus, and nondeterministic hosted inference prevent such a claim.

### Specific revealing behavior

1. **Deferral no longer terminates science.** In both cargo reruns, Lin deferred the first diagnosis, yet independently initiated specialist measurements led to a new (correct, but still unverified) working theory.
2. **No accusation prerequisite.** In the final scrubber rerun, Lin initially selected the *wrong* bus-interference hypothesis; all four specialists investigated without challenging Lin and new measurements preceded a corrected bridge assessment.
3. **More evidence needn't yield confidence.** In both bus-interference reruns, some instruments produced false negatives. Lin kept the originally correct, unconfirmed bus theory and did not assert a new verified cause.
4. **More evidence needn't yield truth.** The all-elevated world gave evidence favorable to *both* the incorrect bus theory and actual scrubber bypass. Four fresh tests did not stop Lin retaining the wrong explanation. No world action quietly repaired the diagnosis.
5. **The control follows menus.** MockModel always takes the first offered option; its incorrect final answer under G3e-3 is a strong warning against using green integration checks as a measure of scientific reasoning.

## Verification and next tests

The functional PR's final head passed **50/50 CI checks**, including **15/15 targeted world investigation tests**, the original G3e-2 real-server restart/replay integration and two completed five-case observation runs. No cross-actor privilege transfer or latent-cause leak was observed in the scoped tests. This is not a guarantee against all such failures.

Future experiments, still without increasing the crew or ship, should vary the *ordering and wording* of the offered actions and repeat the same world seeds across several Gemini runs. Measure (a) independent evidence requests versus blanket agreement, (b) hypothesis revision after misleading observations, (c) decisions to defer, and (d) unnecessary tests. More consequential scientific choices would require alternative test proposals, explicit evidence-discriminating experiment selection, and a way to keep questions open after one inconclusive reading. None is claimed by G3e-3.
