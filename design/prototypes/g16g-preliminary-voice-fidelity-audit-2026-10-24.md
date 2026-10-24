# G16g — preliminary unblinded dialogue-fidelity audit (24 October 2026)

**Source:** actual 48 generated Qwen3.5-4B Q4_K_M lines in [Actions #40048702488](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40048702488), artifact `ox-g16g-48-genuine-qwen35-4b-voice-samples`. This is an engineering/source-content inspection, **not** the protocol's independent two-person blinded voice review. It cannot be used to certify model preference or a human personality score. See [measured cost and provenance](g16g-local-speech-results-2026-10-24.md).

## Observable repeated wording

| Fixed intent | Literal word recurrence in all 12 authentic samples (six roles × two profile presentations) |
| --- | --- |
| Decline optional invitation | **12/12** open with some form of “I appreciate the invitation/invite”; **4/12** assert “already planned”; another **4/12** mention “personal plans” |
| Request optional paperwork help | **11/12** use “before I sign”; the source context says only that the notes are *not yet signed* |
| Suggest private reconciliation | **10/12** use “clear the air” |
| Pressure warning | **2/12** translate unspecified “pressure deviation” into a “pressure spike” (direction not supplied by the scenario) |

Iona's two `request_optional_help` outputs (numeric and prose personality treatments) were **textually identical**, so a persona-presentation change did not always modify even phrasing, let alone character intent.

## Specific grounding warnings

- A character says “I'm heading home early tonight” when the scenario establishes only an off-duty shipboard gathering and a desire to keep the evening free. This invents a destination and a reason.
- Multiple characters claim already-scheduled personal plans rather than simply declining the optional invitation. That may be plausible, but it is not a supplied fact or actor memory and cannot be treated as world truth.
- The Captain's numeric `request_optional_help` sample says “You're the only one I trust with this,” inventing an exclusive personal relationship not established in that scenario, and never actually asks the nearby colleague to examine the unsigned notes.
- The two “pressure spike” samples infer a direction of pressure change that the stated deviation does not establish. Safety-relevant equipment dialogue must not transform uncertainty into asserted sensor readings.
- Some alarm lines propose particular diagnostic/clearance steps that were not verified as approved world operations. As speech they remain **unexecuted utterances**, not action requests, repairs or authorizations.

These are examples of **content-boundary and voice-fidelity risks**, not evidence that the model actually changed Evennia state: the experiment recorded **zero** world commands and zero action requests.

## Next evaluation design, without changing preregistered G16g v1

Retain the 48 native v1 responses as immutable baseline evidence. The [blinded review instrument in draft #121](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/121) must present each anonymous role with its same neutral six-trait reference across numeric and prose arms, conceal the provider/arm key, and obtain at least two independent complete reviewer sheets. Without that process, do not turn this audit into a formal provider score.

For a separately versioned **v2 hypothesis**, reduce shared bureaucratic prompt wording and differentiate the actor's voice using a *short authenticated personal history*, ordinary habits, preferred phrasing and relationship stance from the character's own accessible memory, not global GM truth. Pass the externally determined **intent**, not an entire example utterance, and preserve the same nonauthority requirement: dialogue can express or decline, never choose, execute or certify world actions. Explicitly check unsupported details, role-specific voice differences, repeated stock phrases and same-role continuity across different scenes. Compare v2 with the frozen v1 controls under matched prompts and report any trade-off in quality and generation time. Do not secretly retune G16e action-choice gains or the G16h model comparison based on these *speech* observations.
