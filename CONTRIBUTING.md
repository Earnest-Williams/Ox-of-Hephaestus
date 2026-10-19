# Contributing to Ox of Hephaestus

Ox is a functioning **prototype built on a fork of
[Evennia](https://github.com/evennia/evennia)**. Keep Ox-specific work
separate from the inherited engine and avoid treating early P2/P3 notes as
the current implementation. Read the [project overview](README.md),
[current status](design/STATUS.md), [architecture](ARCHITECTURE.md) and
[roadmap](design/ROADMAP.md) before proposing work.

## Development priorities and boundaries

The world already implements a seven-room ship, three equipment systems,
five authenticated autonomous specialists, an opt-in sixth captain,
persistent character capabilities, narrow receipt-backed learning and
bounded investigations. The [current-state index](design/STATUS.md)
distinguishes these facts from planned general task grading, acquired
attributes, autonomous learning agendas, propulsion, economy and UI.

- Preserve **Evennia as sole physical authority**. LLM outputs do not
  mutate equipment, invent observations or award experience. Agent memory
  cannot read hidden world causes or other people's private observations.
- Use **normal actor authentication, locality, skill/role checks and typed
  world receipts**. Uncertain acknowledgments must reconcile the original
  request ID; duplicate effects and duplicate learning credits are bugs.
- Keep formative aptitudes, psychological dispositions, practical skills,
  theoretical knowledge, exact procedure familiarity, and acquired
  conditions conceptually distinct. The task-comparison resolver is still
  **operator-only shadow logic**, not a live outcome roll.
- Keep the existing three-person and five/six-person regression paths; do
  not start competing supervisors against one game world. Do not mistake
  deterministic MockModel CI for verified open-ended hosted-model behavior.
- Prefer changes under `game/`, `services/`, `contracts/`, `design/`
  and `scenarios/`. Restrict stock Evennia gameplay through Ox-specific
  command allowlists rather than removing engine authentication, typeclasses,
  movement, locks, ORM or transaction services.

## Proposals, tests and documentation

Use the [Ox repository](https://github.com/Earnest-Williams/Ox-of-Hephaestus)
for discussion and pull requests; do not assume issue tracking is enabled.
Describe the invariant, affected world authority, authorization boundary,
migration/backfill consequences, restart/replay handling and specific test
evidence. Add focused Ox unit/integration gates before relying on a new
physical or educational mechanic.

Run the applicable `ox-*` workflows and the repository's documentation
check. The [Ox documentation workflow](.github/workflows/ox-documentation.yml)
validates local Markdown links and agent-guidance drift. For agent-context
changes also run `make cleanrot`. The upstream broad Evennia CI matrix is
not the routine gate for Ox-only work. Do not provision fixture users against
a populated ship, commit secrets or claim that tests passed until verified.

For bugs or improvements in **unmodified Evennia**, prefer its
[upstream issue tracker](https://github.com/evennia/evennia/issues) and
[contribution guide](https://www.evennia.com/docs/latest/Contributing.html).
Preserve the inherited copyright notices and
[BSD 3-Clause license](LICENSE.txt).
