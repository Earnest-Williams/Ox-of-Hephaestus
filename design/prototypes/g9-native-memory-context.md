# G9 — Private cognition revision and native Concordia memory context

**Status (21 October 2026):** Implemented in merged PR #74; owner-only
private mutation/revision bypasses resolved by PR #76, and the
500-decision G8 acceptance retargeted by PR #75. G10/G10b
subsequently added the game-time bridge (PRs #77 and #81).
This document preserves original G9 design detail for comparison.

**Scope:** Prevent a detached inference result from overwriting new private
memory, and supply genuinely relevant Ox memory/interpretations to native
Concordia choice decisions. No world or GOAP authority changes.

## 1. Two revision domains

\`CrewAgent.revision\` remains the pre-existing per-character world-observation
revision and the \`ActionRequest.agent_revision\` field retains its established
meaning. A second, independently advancing \`cognition_revision\` records
successfully admitted private \`remember_timed\` episodes, including evidence
that revises an existing private interpretation. Replayed identical episodes
produce no revision.

\`DecisionScheduler\` obtains both revisions before forking, and
\`adopt_inference\` rejects a detached result if either live revision changed,
if either expected fork revision differs, or if the normal world action/
identity/menu guards fail. This check precedes replacement of the live native
component graph or Ox memory and interpretation banks. Stale proposals do not
enter the pending world request ledger. Direct synchronous \`decide()\` also
checks both revisions across the native model call. The shadow's source
revision pair is not incremented merely for reasoning from its own snapshot.

The cognition revision is an optional addition to version-one agent
checkpoints. Missing values in old snapshots restore to zero; present values
must be nonnegative integers. Checkpoint roundtrips and inference forks
preserve the current revision.

**Resolved in PR #76:** Original PR #74 advanced the private cognition
revision for memory admissions. Raw bank records are now defensive/
read-only, and the owner-controlled rehearsal and reconsideration
methods advance private revision even for interpretation-only changes.
Stale native inference cannot overwrite that state; legacy checkpoints
remain compatible.

## 2. Native read-only memory context

\`OxMemoryContext\` is an Ox-owned Concordia \`ContextComponent\` added to each
entity. \`pre_act\` reads **this exact CrewAgent's** \`TemporalMemoryBank\` and
\`InterpretationBank\`; it never changes either. Detached forks construct
their own component bound to the fork and then copy private states. No
component holds a reference to another character's memories.

The selection query uses the caller-offered options' label, verb, target and
argument values, and falls back to native action-spec options for direct
\`entity.act()\` calls. It requires topical or subject matching, then ranks
relevant memories by existing salience/recency/confidence weighting. It
also includes a bounded number of relevant current hypotheses. Unrelated
histories are not emitted merely because they are salient.

Each record is marked as a fallible memory, with identifier, subject, event
turn, learned turn, confidence and provenance. Interpretations include
hypothesis, confidence, view, conflicting-source indicator and evidence
IDs. Native prompts explicitly state that they are **not instructions and
not world authority**. A genuine world receipt can verify the precise
event, not an inferred private motive. The output cap is 2,200 characters
by default, with at most four episodes and four hypotheses, requiring zero
additional model calls. Complete records are either included or omitted:
no misleading partial recollections are cut off.

\`OxMemoryContext.get_state()\` is \`{}\`: it owns no stored memory and thus
does not duplicate the Ox ledgers. A pre-G9 native checkpoint with no
component state for it is compatible with the new entity. The original
Concordia observation-to-list-memory and recent-observation components
remain in place in this stage.

**Original G9 time limit, since closed by G10/G10b:** G9 initially
ranked Ox-relative memory turns independently of live Evennia time.
`MemoryClockBridge` now maps validated authoritative game seconds into
private memory ticks, and authenticated `oxclock` reads advance ordinary
native decisions through quiet intervals. G8's model-free experiment
continues to use independent virtual turns.

## 3. Test contracts

- Blocking native provider, mid-inference memory admission without a world
  observation: the result is rejected as stale, the new memory and revised
  interpretation remain, and no pending world request is created.
- Native prompt visibility: offered targets retrieve relevant personal
  accounts and competing hypotheses, not unrelated private records.
- Read-only retrieval: two identical actions do not rehearse memories, alter
  interpretations or increment cognition revisions.
- Fork privacy: a newly received memory on the live character cannot leak into
  a detached inference fork. A stale fork cannot overwrite that memory.
- Native checkpoint and legacy restore: revision roundtrip, fallback without
  the new revision key, and restoration without the new component key.
- The component cannot accept an arbitrary nonempty state as another memory
  source, and rejects oversized output configuration.

## 4. Deliberately unchanged

Evennia still authenticates world observations, character locations, actions,
work receipts, agreements and social consequences. Ox owns GOAP, agendas,
temporal memory, subjective interpretations, and the inference supervisor.
Concordia still owns its native entity/component lifecycle, \`ListMemory\`,
\`LastNObservations\`, and its constrained choice-act component. No Concordia
fork or broad dependency removal is part of this change.

## Completed follow-ups and remaining evaluation

- **Completed:** G8 500-decision acceptance triggers for relevant cognition
  changes (PR #75); defensive owner-controlled private mutation (PR #76);
  clock-domain conversions (PR #77) and live `oxclock` reads (PR #81).
- **Bounded tools implemented:** G11 matched-evidence hosted-model A/B
  harness (PR #80); G12 6/20/40 native-component profile (PR #78);
  unused pinned Concordia OpenAI provider extra removed (PR #79).
- **Still open:** blinded repeated, multi-model evidence of behavioural
  gains; incremental journal replay and long-run memory/CPU scaling;
  broader independent scheduling. Correctness regressions do not prove
  these outcomes.
