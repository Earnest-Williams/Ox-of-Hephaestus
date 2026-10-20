# G8: authored private memory seeding and 500-turn social pilot

**Scope:** Add an opt-in, bounded, version-independent initial memory interface
to the actual Concordia character constructor. Preserve the existing world/agent
authority boundary and all restored native component state.

Each `SeededMemory` records a unique per-character ID, subjective text, subject,
source kind (recollection, testimony, interpretation), confidence and salience.
It renders with an explicit **NOT world-verified** label into the new character's
private Concordia `ListMemory`. Existing users default to an empty initial bank.
Only new character construction accepts seeds. Native checkpoints restore the
bank verbatim; no seeds are reinserted during recovery or inference cloning.
All information remains private until an actor legitimately communicates it.

Blueprint `history` and world-authoritative `CharacterKnowledge` remain
separate. Seeds do not create world events, physical items, permission, romantic
agreements, professional expertise, or factual truth.

## Disposable long-run observation

A separate, local **offline shadow-world** runner tested 500 individual
decisions for each of seeds 241, 577 and 911 with six adult characters and
conflicting romantic recollections. The fixture supplied five small maintenance
faults and checked single-owner, in-order work receipts. All 15 fault instances
were verified across three independent 500-decision runs. In seed 241, the
married pair declared separation, an on/off relationship underwent three
separations and reunions, and an initially unexpected pair started dating.
Those findings are **not** results from Evennia, hosted language models, or
the native Concordia seed interface; they motivate the next integration gate.

## G8 live acceptance runner (draft PR #73)

The separate six-client real-Evennia 500-decision experiment uses six ordinary
password-authenticated accounts, one private native Concordia `CrewAgent`
checkpoint per person, a shared symbolic GOAP operator catalogue and
source-verified conversations. It targets five world-created equipment faults:
three C-01 cargo shifts and two A-01 scrubber saturations. Repairs have actual
world-owned WorkReceipts and local inspection requirements. The trusted
CI operator injects each fault **between** handler process segments, while
Evennia is stopped, then restarts the original server. This deliberately avoids
out-of-process modification of cached live equipment state.

Each of the six segments must preserve world-owned agreements, personally
received journal evidence, private memory checkpoints and work receipts.
The final gate requires exactly 500 decisions and five independently verified
work sequences. No world-altering action is accepted merely because a local
planning state predicts it. The simulation has **zero hosted model calls**;
its typed GOAP and seeded private psychology are not freeform conversation.

The first live CI attempt failed at the first C-01 restow after an operator
injection while Evennia was already running. That demonstrated a test
fixture/cache consistency failure, not a passing 500-turn result.
The operator-stop/restart correction and explicit readout-state assertions
require a new complete successful trial before any merge or result claim.

## Remaining integration work

- Pass approved memory seeds into live supervisors' first-time role creation.
- Define bounded retrieval and dynamic memory updates without confusing
  remembered claims with authenticated world evidence.
- Make GOAP relationship selection consult the appropriate actor-private
  memories, and test disagreement, hearsay, reciprocity and explicit refusal.
- Run six independently authenticated live clients for 500 decisions with
  real world-issued minor work receipts and no preselected social outcome.
- Record complete choice/evidence traces, checkpoint recovery, and
  cross-character privacy regressions. Do not present an offline fixture as
  full social intelligence or a live ship run.

Run the narrow native unit tests with
`python -m unittest discover -s services/ai-handler/tests -p 'test_memory_seeding.py' -v`.


## G8 temporal and causal memory upgrade

A private per-person \`TemporalMemoryBank\` now records two distinct times:
**when an event occurred** and **when the character learned about it**. The
G8 social experiment measures both in a single relative simulation-turn
domain; this must not be conflated with wall-clock time or Evennia's absolute
game-time seconds. Seeds can represent events long before the test begins.

Retrieval blends occurrence age, time since latest voluntary rehearsal,
confidence, salience, remembered source reliability and bounded repetition.
A formative memory can retain influence despite great age; more recent
directly observed conversations can supersede its current social weight
without rewriting the original memory. Contradictory recollections remain
distinct and privately attributable, and a character's recollection is not
a verified fact about the other person.

GOAP interpersonal appraisal now uses retrieved experiences rather than a
flat count of mentions in authored backstory. Recall affects candidate
selection, trust, romantic interest, proposal/reply/withdrawal thresholds,
choice of social goal and what a person chooses to disclose. When real
authenticated speech is heard, only those present receive that episode.
Bilateral social events enter both individual histories only *after* durable
world receipts and addressed recipient delivery.

The temporal index persists in the same private per-character checkpoint as
native Concordia state, is copied independently for inference, is bounded at
1,024 entries and accepts the older no-index checkpoint shape. It is a
supplementary indexed memory for explicit GOAP access; it does **not** replace
Concordia's native text memory or the world's authoritative ledger.
The six-client acceptance run remains model-free and deterministic; these
changes still need full 500-turn re-verification on the revised head.


### Verified temporal-memory run

The dedicated 500-turn real-Evennia G8 workflow for the first temporal
implementation succeeded: [run 39471476461]
(https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39471476461).
All five real equipment incidents were repaired with twelve verified
physical work receipts. Each character finished with 323–386 private
time-indexed records, including original conflicting backstory, witnessed
conversations and world-backed agreements. In that run the GOAP decisions
produced 65 disclosures, 60 confrontations, 76 questions, eight commitment
proposals, five acceptances and three deferrals. These are test outcomes, not
evidence of fully emergent human psychology.

The subsequent policy clarification makes acceptance of a proposed
commitment **neutral with respect to romantic desire**: a character may
interpret accepted terms as a modest trust improvement, but consent,
agreement or obligation does not manufacture affection. That corrected head
also needs its own focused final acceptance result.


## G8 private reinterpretation (continuation)

An independently owned \`InterpretationBank\` now sits beside the actor's
unchanged private chronological event records. It holds attributed hypotheses,
confidence, contradictory accounts, correlated source groups, and revision
history. **What happened or was said is never overwritten when the character
changes their explanation.**

Memories may contain explicit *subjective claim metadata*, including the
proposition key, inferred subject, supporting or opposing stance, source
credibility, source group and original observation ID. Memories without a
semantically typed claim are simply remembered, not interpreted by guessing
from free text. No NLP model is silently promoted to a truth authority.

Interpretations are updated only when a new, topic-relevant, personally
received claim provides independent evidence or the original source recants.
Repetition from the same source is not corroboration. Opposed evidence can
shift a view from \`favoured\` through \`unsettled\` to \`doubted\`; competing
interpretations and the original account remain visible to that character.
The confidence computation is bounded, source-weighted, character-specific
and fallible, not an objective probability of truth. Directly hearing a
statement proves the words were spoken, **not that their content is true**.
Real world receipts can only support propositions explicitly entailed by
their action, such as agreeing to, refusing or withdrawing the exact offer;
they cannot prove romantic desire, motive, or sincerity.

Each agent's interpretation and revision history is saved in its existing
native Concordia checkpoint. Inference forks receive detached copies. Older
checkpoints without an interpretation ledger can rebuild it from typed
chronological memories, without creating any world receipts. The engine is
limited to 128 interpretations, 24 independent source groups per claim, and
96 recent revision entries per claim.

The six-person live G8 runner now deliberately permits adults to disclose
their *own* third-party recollections. Only co-located clients that confirm
receipt of the actual Evennia utterance incorporate it. A disagreement changes
GOAP attention, the likelihood of seeking clarification, trust assessments,
willingness to approach and eventual decisions about relationships. It **never
automatically creates desire, consent, or canonical knowledge**.

The acceptance gate additionally exercises correlated testimony, recantation,
contradictory records, explicit non-reconsideration on irrelevant or duplicate
evidence, private checkpoint/fork recovery, and six real Evennia sessions
across a complete 500-decision ship run. A published summary must distinguish
unit-test reinterpretations from those actually witnessed during the run.
