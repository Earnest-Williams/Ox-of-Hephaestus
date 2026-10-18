# G2 personality-sensitive cognition: initial evidence harness

This increment is intentionally below any hiring, interview or browser UI. It consumes the immutable, versioned CrewBlueprint introduced by PR #31 and uses the existing Concordia entity, not a second brain design.

## What runs

- An authorised live-role wrapper may optionally receive a blueprint: its native Concordia entity then has the proposed person's name, occupational brief and personality context. Its stable person ID differs from the role ID. Historic roles and checkpoints still work without one.
- Restoring a profiled checkpoint verifies character DBref and immutable person ID, refusing mismatched character/agent bindings. Ordinary world commands and permissions are not widened.
- `ox_ai.agents.decision_trials` creates completely separate agents and simulated character identifiers, shows them the SAME observations and offers the SAME options, and records only proposed actions. It has no Evennia transport, world effect, work receipt or game database connection.
- Two simple situations exercise uncertainty and collaboration. The cohort has the same authored environmental-technician skills but distinct OCEAN profiles. Repetitions and provider are configurable.
- CI runs native Concordia MockModel as a negative baseline: it picks the first option regardless of profile. A deliberately synthetic profile-sensitive fake model additionally tests that the profile context actually reaches the Concordia choice prompt and can change the selected offered proposal. This **does not** prove a hosted model will display human-like personality.

## Example commands

After installing the native pinned Concordia extra:

    python -m ox_ai.agents.decision_trials --provider mock --repeats 3

An explicitly opted-in hosted choice comparison can be run only by the operator supplying their own Gemini credentials:

    OX_COGNITION_PROVIDER=gemini python -m ox_ai.agents.decision_trials --provider gemini --repeats 3

The latter makes 12 actual choice requests; the operator is responsible for provider availability and cost. It must not be a required public CI workflow, and results must be treated as observations about that model at that time, not a psychometric validation.

## Remaining work

Live five-crew service still uses its own legacy role constructors by default; no new employee is automatically provisioned. Neither this test nor its models are connected to physical actions. Agent state, actual skills, assignments, certification and safety permissions remain separate. Upcoming work: nonblocking inference with supervisor fencing, world-owned skill evidence, training and persistence; generalised character slot assignment; persistent candidate population, delayed expensive recruiting, contracts and departures, without an interface.

## Acceptance

All native Concordia tests and the existing real-server workflows must pass. The probe report must confirm zero world actions submitted; both profiles must see the same offered choices; deterministic baseline must remain identical, while a synthetic prompt-sensitive fixture must demonstrate the personality context changes available cognition inputs. The old five agents must continue to pass all current incident, recovery and privacy regressions.