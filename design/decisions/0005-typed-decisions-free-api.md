# ADR 0005 — Bounded decisions before local model deployment

**Status:** Prototype adapter tested; the later single-engineer Gemini live run succeeded on 2026-10-18. Three-model cooperation remains unverified.

> **Current implementation note:** This ADR preserves the earlier schema rejection and debugging record. Its original “no live success” statements are historical and were superseded by a verified single-engineer hosted-model run.

## Motivation

Ox must remain mechanically competent without a language model on every
step. Offline rules, procedures, GOAP and other control policies remain the
target for routine work. We want to benchmark a small semantic decision
provider without first downloading or serving model weights.

A tiny local Kev model is therefore deferred, not adopted as a dependency.
Start with a free-tier hosted Gemini Flash-Lite model for a **choice-only**
experiment. This is a test convenience, not a commitment to Google's API or
an argument that generative JSON classification is equivalent to Jev's
calibrated decision probabilities.

## Decision boundary

- Define a provider-independent `ChoiceRequest` (state, option identifiers,
  descriptions, instructions) and `ChoiceDecision` (selected option,
  provider/model provenance). This interface can later support deterministic,
  Kev/Jev, local and other hosted providers.
- A Gemini adapter uses a JSON Schema with an enum of offered identifiers.
  It validates the HTTP response after receipt. Malformed, extra, missing,
  timed-out or unoffered answers fail without silently selecting any action.
- The adapter is **synchronous and choice-only** in this bounded local trial.
  The future handler supervisor must schedule it off the game loop and handle
  failures and timeouts without halting unrelated agents.
- The existing Concordia entity and Evennia command path remain unchanged:
  a typed selection becomes an **attempt**, never an authoritative fact.
- No calibrated likelihood, score or posterior is claimed for Gemini output.
  That is a future separate evaluation of Kev/Jev-style decision providers.
- Existing offline scripted integration tests remain valid and network-free.
  Real hosted inference is strictly opt-in and its success is not assumed.

## Free-tier constraints and privacy

Google AI Studio requires an API key even for free-tier Gemini access.
Model availability and request/token quotas can change. Free-tier inputs
and outputs may be used to improve Google's products. Never send real
secrets or private player information in prototype prompts. The key must
be supplied through `GEMINI_API_KEY` at runtime, never committed.

Gemini GenerateContent supports the JSON schema mode via
`generationConfig.responseFormat`. The first provider defaults to
`gemini-3.1-flash-lite`, with the model ID configurable for comparison.

Official docs:
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/generate-content/structured-output

## Explicitly incomplete

This change does not implement GOAP, multi-agent scheduling, a networked
Evennia transport, or fallback from unknown physical outcomes. It does not
prove an unscripted hosted model will repair the pump. Future acceptance
should compare deterministic, hosted and local providers on identical
scenario fixtures, with request volume, latency, action counts, errors and
physical outcomes recorded separately.

## Live API incident and contract correction (2026-10-18)

After fixing the fresh-database startup in PR #5, the first real hosted
decision request returned **HTTP 400** (run
https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39088416596).
The live log proved the credential was provided and the ship had bootstrapped,
but the adapter discarded Google's error response, so the specific rejected
field was not recorded.

The adapter sent `generationConfig.responseFormat.text.mimeType` as
`"application/json"`. For **this enum-valued field**, Google's API contract
requires `"APPLICATION_JSON"`; the older **different** field,
`generationConfig.responseMimeType`, accepts `"application/json"`.
Google clarified the distinction on 2026-10-16:

https://discuss.ai.google.dev/t/generatecontent-structured-json-mime-contract-conflict-and-bare-http400/188396

This is a likely cause of the HTTP 400, not a verified explanation of that
particular response (which was not logged). The code now uses the documented
enum, asserts it in network-free tests, and extracts only safe provider status
and field names from rejected responses. Raw error messages are never printed,
since they can echo a crew member's observations or request data. We must
repeat the live trial before claiming Gemini works.


## Later result: successful hosted single-engineer trial (2026-10-18)

The opt-in [Ox live Gemini pump repair workflow run 39088886933](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39088886933) completed **successfully** after the earlier HTTP 400 investigation. That verified a bounded hosted Gemini model could make the offered sequence of actions in the **one-engineer local game harness**, with Evennia independently validating the real pump result.

It did **not** evaluate unscripted three-crew dialogue. [P4a](../prototypes/p4a-live-cognition.md) later used three native Concordia entities and a deterministic `MockModel` to validate the live multiplayer wiring; hosted multi-agent model intelligence remains a separate opt-in benchmark. API model availability, quotas and data terms can change.
