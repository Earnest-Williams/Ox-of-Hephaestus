# G16l — genuine controller integration tests for positive/negative safety locks

**Status: synthetic score fixtures through the actual G16c/controller
Concordia inference, not a new native safety-performance measurement.**

The [full six-actor real native G16e holdout](g16e-native-six-role-results-2026-10-24.md)
passed its frozen non-safety behavioural criteria, but **none of 36
safety-critical native presentations reached `evidence_lock=0.85`**.
All refused. Thus G16e contains no real high-confidence lock and cannot
validate a positive safety override guarantee or the probability threshold.

G16l adds the missing integration *mechanics* by delivering explicitly
synthetic but fully specified three-way System One scores into the real
`CharacterRouteController` when `OX_PERSONALITY_CHOICE=1` is
**scoped only to the test invocation**. The test uses the genuine typed
G16a safety-critical menu, real Concordia `CrewAgent` detached snapshots,
three native-style code rotations, real `DecisionScheduler` callback,
actor-bound `PersonalityRouter`, durable `PersonalityChoiceLedger` and
unchanged deterministic semantic action replay.

Positive synthetic controls require **0.96** on a specified semantic
action: both procedural and independent characters must force the same
native semantic winner, record zero personality shifts, use one-hot
adjusted scores, checkpoint before live pending proposal adoption and
replay with zero extra inference. Reordered external menus must preserve
prompt hashes, probabilities, final action and stable proposal ID.

Negative synthetic controls require uncertain **0.34/0.33/0.33**
scores to **fail closed** with no action request and no silent GOAP
fallback. A safety-critical GOAP branch must also refuse instead of
applying personality-weighted costs to safety work. Altered durable lock
fields, confidence that switches the winner, selection key or shifts
must be rejected on replay. No promise is made that an untrusted party
who can arbitrarily rewrite a whole persistent record cannot forge it;
the checkpoint's source and world ownership remain separate trust
boundaries.

One deliberately adversarial positive test supplies high confidence
for **`support_loan`**, a potentially risky action. The controller
must still produce **only a pending proposal**, never a completed
repair, permission, commitment or work receipt. It demonstrates why
confidence locking controls *personality override only* and is **not**
evidence of physical safety or authorization. Evennia always retains
the final authoritative eligibility and world-state checks.

No weights are loaded, no native GGUF forward is executed and no
Evennia command is submitted by G16l. Production remains
`OX_PERSONALITY_CHOICE=0`; a true native high-score safety case,
authenticated world permission refusal/acceptance and 40-actor actual
queue/soak must pass separate evidence gates. Existing author choice
threshold `0.85`, gain, max shift and temperatures are unchanged.
