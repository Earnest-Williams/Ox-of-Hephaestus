# Terminal atmosphere experiment (bounded synthetic precursor)

**Status:** completed and verified six-run standalone behavioral benchmark,
retained in the repository alongside—not inside—the Evennia ship world.
This is a disposable isolated simulation of irreversible common
air-processing plenum damage, with the existing six Ox crew identities and
Concordia choice machinery. No normal ship database or other gameplay is altered.

The operator knows the common pressure plenum has catastrophically fractured.
The crew do **not** receive that root cause or any global operator truth. Instead,
each actor receives their own local sensor readings and inspection evidence,
plus only communications legitimately addressed to them. All six share one
declining atmospheric oxygen pressure. A bounded carbon-dioxide trend is also
modeled. Crew members can survey, attempt available mitigation, exchange reports,
log an assessment, or assist. The simulation does not silently fix the breach
when an agent claims a repair.

Two emergency bottles can temporarily raise oxygen pressure; they never heal
the ongoing leak. Cartridge replacement consumes finite stock but cannot seal
a downstream fracture. World time advances between opportunities to act and
terminates on physically modeled atmosphere thresholds. This is an intentionally
simplified monotonic shared-atmosphere model, **not** a validated pressure vessel
or physiology simulator and not a finished ship-wide air-volume network.

## Exactly six paired trials

The dedicated GitHub Actions job matrix runs seed **241**, **577**, and **911**
for both **GOAP** and **Gemini**. GOAP is a non-generative symbolic planner
and never invokes a language model. Gemini uses existing separate Concordia
crew entities and the bounded choice adapter (no free-form text generation).
The two controllers receive identical initial physics, action affordances,
recipient-scoped evidence and per-character wake-time schedules. Each seed
fixes sensor noise and wake-time jitter, but not hosted Gemini decisions.
World trajectories legitimately diverge after different actions.

Every disposable run outputs `scenario.json` and `scenario.md` with action
ordering, per-character choices, observed oxygen, actually addressed reports,
world-confirmed failures and effects, GOAP belief/goal snapshots, number of
inference calls, death time and whether all six are dead. Operator-only hidden
cause is shown in the *post-run* audit only. Model error fails the run; it
must not substitute GOAP or a MockModel decision.

### Run

Open [Ox terminal atmosphere six-run experiment](../../.github/workflows/ox-terminal-atmosphere.yml)
under GitHub Actions or create a PR touching the experimental workflow/source.
The live half requires the existing repository `GEMINI_API_KEY` secret.
No full repository test matrix is required for this pilot.

From a Python 3.12 environment at repository root with the handler installed:

```sh
python -m pip install -e './services/ai-handler[concordia]'
python scenarios/terminal_loss/trial.py --self-test
python scenarios/terminal_loss/trial.py --provider goap --seed 241 --output .ox-state/terminal
```

For the Gemini command, explicitly set `GEMINI_API_KEY` in the environment
and use `--provider gemini`. Never commit or print the credential.

## Interpretation and limits

This is **not** proof of unbounded free-form character autonomy, continuous
Evennia character mortality, actual ship-board movement or a valid clinical
death model. The available action menu is intentionally finite; GOAP and
Gemini differ only in selecting from those options. World effects remain
separate from selected intentions. GOAP updates its **per-person** symbolic
beliefs from local inspection evidence, verified attempt outcomes, attributed
crew reports and noisy oxygen/CO2 readings; it then plans against those
beliefs, not the operator's failure truth. Compared with a deterministic
MockModel (first offered option), this is a genuinely observation-sensitive
non-generative planner. It remains a small authored policy, not a general
reasoning engine.

Actor wake times now vary by seed, rather than always serializing in one fixed
role order. Addressed communications can wake recipients earlier after a
bounded interval; there is still only one world action at a time and at most
three decision opportunities per crew member. This is a discrete-event
scheduler, not actual asynchronous Evennia character sessions.

Do not infer that the three repeated seeds give statistically independent
generalized measurements of model quality. Look at qualitative outcomes:
recognition, futile repair, resource use, truthful reporting, communications,
crew welfare, premature declaration, and time management. This simulator
deliberately guarantees eventual death but **does not guarantee specific crew
choices**, and its minutes/physiology are only scenario abstractions.

**Next integration gate:** If these results are useful, move the world physics,
finite consumables, actor incapacitation/death and inspection/reporting into
authoritative Evennia models, then rerun the paired experiment over six
authenticated actual crew clients. That integration is not claimed here.

## Why this revision exists

The first six-run baseline (GitHub Actions run 39329210735) showed all three
GOAP traces selecting exactly the same eighteen actions despite differing
noisy sensors. A GOAP engineer tried an unavailable repair even after personally
finding it impossible. Moreover, a crew broadcast picked the latest inspection
**receipt text**, rather than the underlying factual evidence; that incorrectly
weakened inter-character information flow. The revision fixes these issues
without changing the physical failure or inventing free-form actions. The
trial remains illustrative: only an integrated Evennia run will exercise
real travel, world work authority, mortality and authenticated clients.

## Archived findings from the completed six-run comparison

This scenario is **retained as a merged, runnable experimental benchmark**.
Its results must not be confused with integrated Evennia behavior. The initial six runs
([workflow 39329210735](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39329210735))
used an overly procedural GOAP: all three seeds produced the same sequence of
18 actions, including futile repairs even after local evidence ruled them out.
Additionally, the broadcast action sent a recent action-receipt summary rather
than the actual instrument finding, reducing useful secondhand knowledge.

The revised runs
([workflow 39331019012](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39331019012))
passed all six trials and corrected those defects in the **standalone sandbox**.
The non-generative GOAP controller now updates actor-private symbolic facts
from firsthand inspections, addressed communications, oxygen/CO2 readings,
and verified work outcomes. It treats an impossible workaround as ruled out,
then plans useful follow-up without claiming a repair succeeded. A seed-specific
individual wake scheduler replaced the fixed role order; successful broadcasts
now actually contain the sender's findings. Focused assertions verified the
change in the next GOAP action after finding an inaccessible fracture, the
receipt's actor-bound idempotency, information delivery, and deterministic
replay under one seed.

### Revised results (all six crew died in every trial)

| Seed | GOAP death (world min) | Gemini death (world min) | GOAP emergency bottles | Gemini emergency bottles |
|---|---:|---:|---:|---:|
| 241 | 164 | 143 | 2 | 0 |
| 577 | 164 | 143 | 2 | 0 |
| 911 | 164 | 143 | 2 | 0 |

Revised GOAP trials each chose six firsthand surveys, five broadcasts, four
provisional no-recovery assessments, one captain command, and two uses of the
emergency reserve, with **no** structurally futile repair attempts. Their
waking order varied by seed, but authored belief rules produced the same broad
response. Gemini's bounded choices continued to favor some repairs and not
use the reserves in these particular three runs; that observation is retained
for later analysis, **not** a generalized conclusion about Gemini performance.

**Interpretation:** GOAP's *observation sensitivity* improved; it did not
acquire a general ability to infer novel physics or reason about uncertainty.
The scenario's unusually explicit findings made the rule-based assessment
relatively easy, and the GOAP policy was tailored to this scenario while the
Gemini controller did not receive that identical explicit decision policy.
The apparent 21-minute survival advantage therefore cannot be treated as a
fair estimate of comparative intelligence. All six tests were disposable
synthetic-world executions; they did not exercise Evennia character motion,
world database durability, or six authenticated client sockets.

These findings provide a reproducible behavioral regression baseline for
the separate Evennia-integrated G6 experiment in PR #67. The pilot is
retained in main to test how per-actor knowledge changes non-generative
planning, while keeping the simplified physics and limitations explicit.
