# G16n — retain exact argument-bearing GOAP world-command identities

**Engineering prerequisite, not activation.** G16a's typed command signature
is `(verb, target, sorted arguments)`. The G16c/D GOAP branch previously
matched operators to G16a tags using only `(verb, target, ())`;
this could not represent the existing 40-crew `round_report ship
station=<station>` duty operations. Two different authorized station
reports can share a verb and target but must never share a plan
execution identity. A missing or guessed station is a different
world command, not merely a label.

G16n adds an immutable, sorted, bounded optional `GoapAction.arguments`
field, preserving all legacy empty-argument operators unchanged.
Its exact signature is propagated through the personality-weighted
GOAP cost lookup and the opt-in G16c operator/ledger replay checks.
The original (non-opted-in) CharacterRouteController now also matches
full option arguments so two same-verb/target choices cannot be
ambiguously assigned the wrong station.

Negative cases reject untagged argument variants, malformed pairs,
duplicate/unsorted argument keys and replay attempts to replace
`station=cargo` with `station=scrubber`. A real synthetic
Concordia `CrewAgent` and an injected immutable *offline* authored
G16a catalog demonstrate the GOAP path choosing and checkpointing
`round_report ship {station:cargo}`, with the exact same
`ActionRequest` on repeat. No native inference call, real
station observation, world action or work receipt is produced.

This repairs a semantic interface mismatch **only**. The P4k fleet
currently offers two commands (report/defer); G16c's deliberately
preregistered model branch still requires an exact **three-option**
position-balanced menu. We have **not** fabricated a third shipboard
action to fit that model, broadened the original G16b model calibration,
or installed a new live-tagged menu. Binary action scoring and the
Evennia-backed 40-actor world authorization/recovery soak must be
designed and separately tested before an actual live opt-in.

The operational goal is plausible freighter work and actual world
consequences, not a real-spacecraft certification exercise.
Evennia retains final work authority; no prediction of GOAP effects,
LLM score or written action request counts as a completed station round.
