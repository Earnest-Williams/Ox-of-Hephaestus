# G4h — Conceptual learning from firsthand investigation

**Scope:** One bounded investigative-method activity, stacked on G4g's
conceptual-learning ledger. It uses a real actor-local inquiry and a fresh
training transfer check. It does not verify the physical cause or schedule
autonomous education.

## Verified activity

The activity `investigation.evidence_limits.v1` develops the theoretical
foundation `investigation.methods`. Eligible investigators are the four
existing local specialists: Ari, Iona, Mara and Teo. Each must use their
own installed station and their own authenticated account.

1. Collect and file a genuine initial sample using the existing uncertain
   investigation protocol. Register an independent question or an alternative
   to a bridge hypothesis. Both reports need successful global work receipts.
2. Before taking the follow-up diagnostic, record a prediction of its
   **observed reading**: `supports` or `does_not_support`. Neither prediction
   accuracy nor agreement with a diagnosis earns credit.
3. Perform the actual local probe and file its firsthand report. A client
   cannot supply substitute evidence IDs. The world binds the actor's exact
   case, initial report, question/challenge, prediction, later sample and
   receipted probe report in journal order.
4. Request a review. The investigator receives their own fallible reading,
   the hypothesis tested, the saved forecast and the source references.
   Authored guidance explains why indicative support does not confirm a
   cause and lack of support does not exclude it. A separate, newly generated
   training example asks whether two reports describe one repeated source
   or two independently collected sources. Training source IDs are explicitly
   defined as independent collections in that example; they are not ship data.
5. After at least five game minutes, interpret the actual reading within its
   limits and count independent training sources. Both answers must pass.
   This is a delayed reflection check, without a teacher or continuous
   attendance tracking. Elapsed time alone earns nothing.

One attempt is available per person and real case. A wrong answer consumes
that assessment; a fresh request ID cannot replace it. The attempt expires
one game day after its prediction. Review and reflection require the actor
at their own station, but an already collected case may have closed in the
meantime. Reflecting on it does not reopen or resolve it.

This verifies a narrow authored comprehension check grounded in actual
investigative conduct. A wrong forecast and a retained wrong provisional
diagnosis can coexist with learning about evidence limits. It does not
establish general understanding, teaching quality or LLM reasoning ability.

## Authority, privacy and progression

Migration `0012_inquiry_learning` adds `InquiryLearningAttempt`, recording
the actual person/case, stage, source event references, forecast, review
exercise, answers, times and global receipts. G4f's existing
`CharacterLearningEvidence` attributes conceptual change; G4g's existing
`CharacterKnowledge.study_progress` remains the sole progress store.

A passed reflection creates one evidence row for the person/case/foundation.
It can credit one study unit below mastery 70/100, subject to the existing
increasing 4/7/12/20/30-unit mastery thresholds and three credited events per
foundation per game hour. Any investigative assessment completed within the
previous game day, passed or failed, prevents another study credit. A passed
but capped reflection remains auditable with zero credit. Further real
investigations and reflections remain available; learning limits do not
prevent crew work. Existing advanced study progress is preserved when an
elementary assessment gives no credit.

The learning path loads only source provenance and case status. It never
loads the hidden cause, private signal draws, probe random key, probability
tables or bridge assessment/reassessment to grade an answer. Neither a correct
diagnosis nor fabricated client confidence can bypass the check. New
`inquiry_*` events are delivered only to that investigator. Ordinary shared
investigation reports retain their existing authorized recipients.

Practical skills, exact procedure familiarity, aptitudes, psychological
dispositions, roles, permission and physical outcomes do not change. Passing
does not certify or close the investigation or the captain's obligation.
The world record is not automatically inserted into a character's beliefs,
self-assessment or private memory. Existing theory may affect operator-only
task shadow comparisons; it still does not determine live repair outcomes.

## Existing authenticated work protocol

~~~text
oxsample <case-id>
oxwork <id-1> anomaly_report ship <case-id>
oxwork <id-2> anomaly_question ship <case-id>
oxwork <id-3> inquiry_predict learning <case-id> <prediction>
oxprobe <case-id>
oxwork <id-4> anomaly_probe_report ship <case-id>
oxwork <id-5> inquiry_review learning <case-id>
oxwork <id-6> inquiry_reflect learning <case-id> <interpretation> <independent-sources>
~~~

`interpretation` is `supported_unconfirmed` for a `supports` observation or
`unsupported_not_excluded` for `does_not_support`. `independent-sources` is
`one_source` or `two_sources`, derived from the delivered training reports.
An existing valid `anomaly_challenge` may replace `anomaly_question`.
Clients supply no scores, credit, source events, mastery or hidden causes.

All stages share the existing world-work lock and actor-bound global receipt
namespace. Activity, result event, receipt, evidence and progression commit
or roll back together. A successful submission receipt means the reflection
was performed; the private `inquiry_reflected` event supplies its passed or
failed result. An early refusal remains refused under its original ID even
after the waiting period. Lost acknowledgments are reconciled by the original
persisted ID, and another actor cannot read the receipt.

## Verification and limits

The world suite exercises positive/negative observations, copied/separate
training sources, pre-test provenance, question and challenge paths,
foreign/remote actors, missing receipts, stale samples, timing and expiry,
wrong answers, daily spacing, ceilings, missing initial foundations, retained
advanced progress, closed cases, real mastery gain, novel-task shadow transfer,
replay and complete rollback after the learning writer fails. A descriptor
guard makes any learning-path read of hidden case fields fail the test.

[`ox-g4h-inquiry-learning.yml`](../../.github/workflows/ox-g4h-inquiry-learning.yml)
also runs ordinary Ari/Lin clients against a real server. Ari learns the case
only from an addressed notice, predicts before probing, reports and reviews
their own measurement. The world restarts before reflection. A separate
client process then reconciles a deliberately forgotten acknowledgment and
replays the original ID. Lin's receipt lookup is refused. An independent
world verifier checks exactly one study credit, private learning events,
unchanged independent competencies and an open case/captain obligation.
The opt-in CI clock is 60×; normal game settings are unchanged.

**Remaining:** autonomous learning agendas, general experimental design,
freeform explanations and rubrics, further curricula and graded physical
attempts. The five/six-crew supervisor does not yet choose these activities.
