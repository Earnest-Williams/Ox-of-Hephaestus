# Terminal atmosphere experiment (bounded synthetic precursor)

**Status:** experiment branch; not a completed six-run result or a real Evennia
death mechanic. This is a disposable isolated simulation of irreversible common
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
The two controllers receive identical case physics and action affordances; the
seed fixes per-character sensor noise, but not hosted Gemini decisions.

Every disposable run outputs `scenario.json` and `scenario.md` with action
ordering, per-character actions, world-confirmed failures and effects, number of
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
python -m ox_ai.scenarios.terminal_loss --self-test
python -m ox_ai.scenarios.terminal_loss --provider goap --seed 241 --output .ox-state/terminal
```

For the Gemini command, explicitly set `GEMINI_API_KEY` in the environment
and use `--provider gemini`. Never commit or print the credential.

## Interpretation and limits

This is **not** proof of unbounded free-form character autonomy, continuous
Evennia character mortality, actual ship-board movement or a valid clinical
death model. The available action menu is intentionally finite; GOAP and
Gemini differ only in selecting from those options. World effects remain
separate from selected intentions. Compared with a deterministic MockModel
(first offered option), GOAP is an actual non-generative planner.

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
