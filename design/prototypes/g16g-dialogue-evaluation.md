# G16g — speech is a generative task, not a decision-making authority

**Status: prerecorded evaluation protocol and isolated harness; no provider
is yet adopted for live character speech.** The action policy remains
disabled, and an utterance cannot create an Evennia work receipt, alter
a social commitment, bypass a permission or select an action.

The shared [G16g protocol](g16g-speech-preregistration-v1.json) fixes
six original G9 actor blueprints, four hypothetical speech situations
and **two presentation arms per actor**: the original numeric profile
and the [G14 prose profile](g14-experimental-results.md). These produce
48 outputs **per provider** at a fixed seed, temperature 0.4 and 120
output-token ceiling. The profile/text renderer is shared across
providers, preserving actor identity and the *same preselected speech
intent* in each pair. There is no generated command menu and no
attempt to infer a new decision from free text.

The first native candidate is the previously evaluated, independently
SHA-256-verified **Qwen3.5-4B Q4_K_M local generative model**
(`00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`).
The CPU execution uses the pinned local llama.cpp OpenAI-compatible
endpoint on 127.0.0.1, never a public provider.
The harness also supports an independently configured
hosted Gemini `generateContent` provider, **only** with an explicitly
provided `GEMINI_API_KEY`; no secret is stored or logged, and the
hosted provider is not used in the ordinary repository checks.
Neither provider has authority over Evennia's world.

## Evaluation and honest limits

The [harness](../../scenarios/g16g_speech_evaluation.py) captures
complete generated text, source role/profile and scene IDs, per-response
latency, model ID, prompt/completion token usage when supplied and
SHA-256 of the precise prompt. The original G9 role blueprints
are not modified. A separate **blinded reviewer sheet** excludes
role, presentation arm and provider identification and preserves
the fixed known scenario and preselected speech intent.

At least **two blind human reviewers** must evaluate character
distinctiveness, profile fidelity, factual fidelity, natural
spoken dialogue and appropriate emotional register. Generated responses
should neither invent resolved causes, repair approvals or signed
commitments nor turn speech into operational authority. The automated
smoke tests check **only** bounded, nonempty text, source identity,
full factorial coverage and independent output classification.
They cannot meaningfully judge whether a character sounds human.

Costs are measured as elapsed seconds and reported prompt/output
tokens. Native model speed is *machine-specific*. Hosted dollar
charges **must not be invented**: record actual provider pricing
and billable token usage when/if a hosted comparison is run.
Only after qualitative review and measured cost should one
generative speech model be chosen. A purely local result is a
local-candidate evaluation, not an honest hosted-versus-local win.

The first workflow is a fixture contract gate; it deliberately uses
canned synthetic text and reports `real_text_generation_measured=false`.
The expensive local native study is isolated on a dedicated experimental
branch. G16g is separate from G16e's scored semantic action choices
and cannot change G16b's frozen personality-routing policy.

## Blinded review and the private answer key

The generation-time `blind_review_sheet` intentionally did **not**
include a neutral trait reference or a stable speaker grouping; that is
not sufficient to judge profile fidelity and voice distinctiveness.
After native generation, use the separate
[`g16g_blind_review.py`](../../scenarios/g16g_blind_review.py)
review-instrument exporter. This does **not** modify the original
model-generation protocol or rerun/retune any native prompt.

The [human review instrument](g16g-blind-review-protocol-v1.json) was
written **before seeing any human ratings, but after model generation
had started**. It requires two distinct complete reviewers, integer
1–5 scores on distinctiveness, profile fidelity, grounding,
naturalness and emotional fit, plus a fixed list of independently
flagged invented permissions, consent, diagnoses, completed repairs,
action reversals and contradictory facts.

The exporter generates three files: (1) a shareable reviewer sheet
with no actor identity, input arm or model-provider labels; (2) a
**separate confidential answer key** containing the provider, actor,
input arm and random 128-bit salt; and (3) an empty reviewer rating
template. Each speaker has one opaque group ID across profile arms
and providers. Every utterance has a separate opaque ID and the same
neutral six-trait reference regardless of which presentation arm
generated the words, making cross-arm comparison possible without
telling reviewers which arm they are reading. The private key must
not be published with the reviewer sheet.

Example after retrieving a successful native results artifact:

```bash
python scenarios/g16g_blind_review.py prepare \
  --native-results /path/to/qwen4b-48-voices.json \
  --public-sheet /path/to/anonymous-voice-review.json \
  --private-key /secure/voice-answer-key.json \
  --blank-template /path/to/reviewer-template.json
```

After two independent reviewers fill their entire templates, run
`g16g_blind_review.py assess --private-key ... --reviewer-files
reviewer-one.json reviewer-two.json --output review-summary.json`.
The assessor rejects missing utterances, duplicate reviewers, missing
scores and unknown fidelity flags. It reports comparative ratings
**without selecting a production provider**; a local Qwen-only run
cannot establish hosted pricing or hosted speech quality.

Synthetic fixtures explicitly fail genuine-source verification and
cannot be exported as a completed human speech assessment.
