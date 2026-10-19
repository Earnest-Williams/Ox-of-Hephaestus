# G6 — Terminal atmospheric failure in the actual Evennia world

**Status:** experimental implementation on a new PR, not a shipped universe
mechanic. Separate from the closed/unmerged [PR #66](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/66).

## Why G6 follows the simplified pilot

The standalone six-run pilot exposed that the original non-generative
controller continued futile work because its GOAP state only tracked
procedural milestones. The updated GOAP read *private firsthand findings*,
actually addressed crew reports, sensor urgency and world-confirmed failures,
then avoided repeating known-impossible work. Its revised three seeds all
used both reserves and survived 164 synthetic minutes, while the prior rigid
GOAP policy did not reliably exploit evidence. Detailed results and the
baseline caution are archived in PR #66 at
[scenarios/terminal_loss/README.md](https://github.com/Earnest-Williams/Ox-of-Hephaestus/blob/experiment/terminal-atmosphere-six-runs/scenarios/terminal_loss/README.md).

**Do not generalize from Gemini's performance** in the synthetic pilot:
the GOAP policy was tailored to that exact world, the evidence was explicit,
and the comparison was too small to measure general reasoning ability. No
out-of-world facts may be leaked to any agent to improve a result.

## G6 experiment: actual world, real authority

- The original Evennia ship has **seven connected rooms** and actual P-01,
  C-01 and A-01 equipment. G6 adds one opt-in **downstream common plenum
  fracture**, not an alternative ship mock. A-01 can remain nominal even as
  pressure falls: this is a useful real-world diagnostic ambiguity.
- The operator arms the incident *once* on a disposable world database.
  The authoritative world object stores the hidden fracture, stable
  scenario seed, finite bottles, sampled evidence, work history, and
  death status. It rejects re-arming rather than resetting a living world.
- A persistent Evennia **Script** advances the atmosphere independently of
  AI decisions. Every 2 seconds it advances 4 approximate world minutes.
  Inspired by the isolated pilot, oxygen partial pressure declines
  monotonically while two emergency reserve bottles can delay—but never
  reverse—the fatal trajectory.
- Oxygen pressure at or below 8 kPa or excessive CO2 causes actual
  persistent character death. Dead characters cannot move through ordinary
  Evennia exits or execute any further work using the normal receipts.
- All six individuals are provisioned as **six non-privileged Evennia
  accounts**. The external six-person runtime opens separate authenticated
  WebSocket sessions and verifies the character bindings.
- Each actor observes atmospheric telemetry via an **authenticated world
  command**; station-specific firsthand evidence requires real local
  world-authorized work. The captain can issue real addressed commands,
  the engineers can attempt unsuitable repairs, Teo can check real A-01,
  and a role-qualified person at the Environmental Plant can discharge
  one finite atmospheric reserve bottle. The world can refuse attempts.
- Agent decisions use GOAP with **personal knowledge**, or Concordia/Gemini
  with bounded choices. Both receive only actor-owned status and
  individually addressed journal events. World state never trusts a model's
  description of success.
- Agents schedule independent wake cycles; each physical attempt uses the
  existing `oxwork` endpoint, one durable `WorkReceipt` ID and the
  normal Evennia navigation mechanism. Terminal observations use
  `oxterminal`, returning OOB data scoped to the authenticated caller.
- An independent operator audit **after the server stops** correlates
  each handler choice with the corresponding authoritative world receipt,
  verifies all six distinct accounts and deaths, and excludes the hidden
  cause from client-visible traces.

The exact same seeds (241, 577, 911) each run twice:
**non-generative GOAP** and **Concordia/Gemini**. Each trial has its
own disposable database. The world clock progresses in server time, so
inference latency can change the available reaction time. This is
authentic to the model but a comparability limitation to report.

## What is deliberately still bounded

This test runs through the **real implemented Evennia environment**;
it is not a completed deep-space voyage or a complete atmospheric
engineering model. It adds an explicit terminal overlay to the present
P-01/C-01/A-01 prototype. Four independent decision opportunities per
person, a finite typed choice menu, and approximated gas dynamics do
not represent unlimited character autonomy. The captain's new emergency
directive is a world-verifiable action, but the full G3f
captain-obligation workflow is not silently replaced or exercised by
that directive. The incident introduces no economic, propulsion,
eva/rescue or evacuation physics.

## How to run and audit

The focused workflow is
[Ox G6 six-authenticated terminal-voyage experiment](../../.github/workflows/ox-g6-terminal-live.yml).
On PR: run the narrow world-state gate first, then the three GOAP
and three Gemini cases using the secret `GEMINI_API_KEY`.
No default world is harmed; ordinary startup does not arm the failure.

The resulting six artifacts include a handler-side actor record,
an operator-only world state record, a Markdown comparison,
and concise process logs. A green workflow means **the invariant
checks passed**, not that agents handled the emergency wisely;
study each independent action trace and report failure cases.

Important negative checks: world truth must not leak into actor
context, work receipt IDs cannot be stolen, repeated acknowledgement
must not duplicate an action, a failed repair cannot clear the
leak, a dead person cannot keep working, and authentication
must bind each socket to exactly one real crew member.
