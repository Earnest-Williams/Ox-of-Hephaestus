# Contributing to Ox of Hephaestus

Ox of Hephaestus is an early-stage independent project built on a fork of [Evennia](https://github.com/evennia/evennia). Contributions and design discussions should distinguish **Ox-specific systems** from **changes to the underlying Evennia engine**.

## Before proposing a change

Read the [project overview](README.md) and [initial architecture](ARCHITECTURE.md). Much of the repository remains unmodified Evennia code and documentation, and the ship simulation and AI handler are not yet implemented.

Useful initial contributions may include project design notes, small and testable AI-client prototypes, shipboard duty and skill mechanics, operational-observability ideas, and reproducible development improvements. These are possible areas of work, not a claim that the corresponding systems already exist.

## Issues and pull requests

- Open Ox-specific issues and proposed changes in the [Ox repository](https://github.com/Earnest-Williams/Ox-of-Hephaestus/issues).
- Explain what problem is being solved, which subsystem it affects, and whether it depends on an unfinished component.
- Keep changes focused and document how they were checked. Do not claim successful tests or working gameplay where they have not been demonstrated.
- Preserve normal character permissions and authoritative game state in any AI integration; a future privileged service transport must not confer unintended in-world privileges.

For bugs, general improvements, or documentation corrections in **unmodified Evennia**, prefer [Evennia's upstream issue tracker](https://github.com/evennia/evennia/issues) and [contribution guide](https://www.evennia.com/docs/latest/Contributing.html). If a fork-specific engine patch is necessary, explain why it belongs here.

## Code boundaries and attribution

- Prefer project-specific code and extensions over invasive changes to `evennia/` until a concrete need is established.
- Leave the upstream package identity and distribution metadata alone unless the project deliberately undertakes a separate packaging effort.
- Keep the original copyright notices and [BSD 3-Clause license](LICENSE.txt) required by the inherited Evennia code.
- Follow relevant upstream code-style and testing guidance for changes to the engine.

This is a working starting point for collaboration, not a final project governance policy.
