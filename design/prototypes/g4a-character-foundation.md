# G4a - Character foundation and Evennia command-surface reduction

**Implementation:** stacked on captain PR #54 while its six-character authority rules remain under review. No change to equipment physical outcomes, world skill qualifications, or population management.

## Foundation

Version-two `CrewBlueprint` adds exactly twelve stable aptitudes (1-10), two operational psychological dimensions (Persistence and Isolation Tolerance), and retains the existing five OCEAN dimensions, five original Ox dimensions, styles, starting-skill estimates, histories, and person identity. Aptitudes are distinct from learned skills and current conditions. MBTI presets remain writing/interpretive styles, not duplicate modifiers.

`CrewBlueprint.from_record` accepts exact v1 records: it preserves existing ten psychological scores and other fields, adds neutral 50 to new dispositions, adds neutral 5 for all twelve aptitudes, and emits v2 on reserialization. Unknown versions and malformed schemas are rejected. This is a character *seed* change only: it does **not** grant effective world skills, injury modifiers, diagnosis, or authority. Do not overwrite past world-owned skill vectors or existing character identities during bootstraps.

## Evennia reduction

The default Ox character command set now derives directly from `CmdSet` rather than importing all stock Evennia character commands through `super().at_cmdset_creation()`. An explicit allowlist keeps ordinary look, say, whisper, pose, help and Ox ship procedures. This removes the ordinary character command paths for stock get, drop, give, home, description edits, building/admin operations and other unsupported gameplay. Exit commands still come from Evennia exit objects. This deliberately does not alter the account-level command set, authentication, developer permissions, WebSocket framing, event journal, historical receipts, or world physics.

The account/session command sets must be examined separately before pruning their self-provisioning controls; live six-session authentication and operator tooling must not be stranded. The Ox world will continue to use Evennia's engine, ORM, object/typeclass and lock primitives; do not delete inherited engine modules just to remove command availability.

The G3f 0-4 `ox_skills` vector and `captain_inspect` threshold remain operative until an explicitly tested world-owned competency migration. No second authoritative skill ledger is introduced in this slice.

## Test and follow-up

- Model-free character-factory tests: exact legacy round trip, v2 independent aptitude values, schema validation, preset collision handling, independent agent binding.
- World command boundary test: allowlist includes core operational verbs, excludes stock mutators and generic MUD inheritance.
- Existing G3f six-character integration, real transport, event privacy and work receipt checks remain required.
- Next increment: world-owned profile persistence and competency catalogue. Define observable/self-perceived character information separately from world truth before connecting to Concordia decisions.
- Framework pruning is mandatory for every subsequent character-system PR: inventory replaced only after authoritative item semantics are complete; role-scoped temporary authorization retired only after job/qualification alternatives are verified.

**No evidence of game integration success should be claimed until applicable CI has passed for the actual head.**
