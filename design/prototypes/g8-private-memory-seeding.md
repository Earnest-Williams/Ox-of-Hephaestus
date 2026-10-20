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
