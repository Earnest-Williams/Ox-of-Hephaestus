# G3e-2: independent challenges, contradictory experiments, and revision

**Verified, opt-in extension of G3e-1 (PR #48, 46/46 final-head checks).**
Five existing Concordia characters, existing seven compartments, existing
world-sourced work receipts, no new personalities, skill vectors, or fixtures.

## Genuine uncertainty, not a quiz

The game owns a hidden root cause for an intermittent atmospheric analyzer
discrepancy. The crew receives only the symptom, its own station evidence, and
subsequent character-addressed reports. The original Lin assessment is
**unconfirmed**. After that assessment, each specialist may disagree, defer,
or later change their position on the basis of a fresh diagnostic.

| Specialist | Follow-up test (existing station) | Question tested |
| --- | --- | --- |
| Ari | Electrical bus reference measurement at P-01 | Is electrical interference contributing? |
| Iona | Independent thermal reference at P-01 | Is a scrubber bypass plausible? |
| Mara | Cargo sampling blank at C-01 | Do cargo volatiles explain the disagreement? |
| Teo | Scrubber differential at A-01 | Is a bypass plausible? |

Each instrument has both false-positive and false-negative results.
A `supports` reading increases plausibility but does not certify a cause;
`does_not_support` does not mathematically falsify it. The operator-controlled
seed makes all four draws reproducible for integration tests. The root cause,
world-only probe seed, unchosen readings and ground-truth comparison are never
returned to a character, model prompt, capability menu, or report.

**Source-bound stages (each separately authorized by Evennia):**

1. Specialist sees a hypothesis explicitly shared by Lin after G3e-1; receives
   no shared memory or unseen crew evidence.
2. Specialist proposes a *different* explanation or defers. `oxwork <id>
   anomaly_challenge ship <case-id> <hypothesis>` records a single provisional
   challenged view with the actor's original world-verified report as basis.
3. At their physically accessible station, `oxprobe <case-id>` records one
   world-sampled role-specific reading. Replays yield the same persisted
   result and event ID, not a redraw. The sample is private to its examiner.
4. `oxwork <id> anomaly_probe_report ship <case-id>` relays that firsthand
   instrument reading to Lin, with a source event ID and no conclusion.
5. Specialist chooses to revise, retain, or defer a personal hypothesis.
   `oxwork <id> anomaly_reconsider ship <case-id> <hypothesis>` records
   either result. The change is testimony, not verified world state.
6. Lin must receive at least one **post-test** view from engineering and one
   from cargo/environment. Lin's own Concordia agent sees those addressed
   reports, then chooses among all three explanations and **defer**.
   `oxwork <id> anomaly_reassess ship <case-id> <hypothesis>` records one
   unconfirmed reassessment, even when unchanged or incorrect. The original
   assessment and hidden physical cause remain intact.

The model may choose to disagree with another person, keep a wrong opinion,
or defer. Concordia's deterministic MockModel always takes the first offered
option: this validates persistence, routing, permission and response gating,
**not** open-ended scientific competence. One seeded test includes
contradictory false positives under the actual scrubber-bypass cause.

## Safety / authority / persistence

- All physical/local readouts are world-issued through authenticated ordinary
  commands. The external handler cannot import `world.investigation_followup`,
  access the database or inspect the latent cause.
- Every consequential report and social claim uses a global
  `WorkReceipt` bound to actor, case, operation, arguments and a durable
  handler intent. Lost ACKs reconcile under the **same** request ID.
- The case row is locked during world-owned edits. Event journal writes,
  evidence history, addressed delivery and work receipt share a transaction.
  Replaying a world-confirmed probe produces no additional evidence.
- Private Concordia and `AgentEpistemics` ledgers retain a hypothesis as
  `believed`. Only authenticated, firsthand probe readings are
  `observed`; another person's interpretation is not a verified fact.
- Original diagnosis, challenges, local probe evidence, post-probe opinions
  and final bridge reassessment have separate world fields. No later
  conclusion erases an earlier mistaken decision.

## Invocation and acceptance

Arm one G3e-1 case through the operator's `arm_anomaly` command.
For deterministic isolated CI set `seed=6, cause="scrubber_bypass"`.
Enable both `OX_G3E_INVESTIGATION=1` and `OX_G3E_FOLLOWUP=1` in the
*external* five-crew handler. It handles emergencies, human requests and
handover before optional G3e duties; no idle model calls. The disposable
`investigation-drain` and `followup-drain` modes each make a finite pass
over independently authenticated actors. G3d remains separately opt-in.

`game/world/tests/test_investigation_followup.py` validates role restrictions,
provenance, local travel gating, irreversible refused IDs, wrong hypotheses
and rollback of failed second/third journal events.
`.github/workflows/ox-g3e-investigation.yml` does the G3e-1 and G3e-2
world tests plus a true five-WebSocket-client, separate-world restart trial,
followed by an independently queried authoritative DB verdict. Final-head CI passed and PR #48 was merged. The CI outcome confirms protocol
and world integration, not general model diagnostic accuracy.

**Out of scope:** generalized scientific research plans, repeated rounds of
sampling, automatic proof of cause, physical intervention/safety resolution,
interactive UI, and a guarantee that a particular AI diagnosis is correct.
