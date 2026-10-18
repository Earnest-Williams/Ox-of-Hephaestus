# ADR 0004 — Scope continuous integration to Ox

**Status:** Accepted (2026-10-18); focused P0–P4 suites are established.

> **Current implementation note:** The CI decision below preceded the later P3/P4 workflows. Focused end-to-end server tests now complement, rather than replace, the original scaffold and root-package smoke checks.

## Context

This repository is an Evennia fork being developed into Ox of Hephaestus. The inherited Evennia test workflow runs a full 3-Python-version x 3-database matrix (SQLite, MySQL and PostgreSQL) on routine PRs. A sample run on 2026-10-18 passed all nine jobs but took approximately 27 minutes and emitted inherited dependency/tooling notices. Its Docker deployment was skipped because upstream explicitly restricts publishing to `evennia/evennia` on its main branch.

The full matrix is appropriate for upstream framework maintenance, but it is an expensive default for a mostly isolated, Concordia-based AI handler and user interface.

## Decision

- **Automatic:** `.github/workflows/ox-scaffold.yml` installs/checks the independently packaged handler and interface and runs their contract tests.
- **Automatic when root Evennia packaging or engine changes:** `.github/workflows/ox-evennia-smoke.yml` installs the root Evennia distribution on Python 3.12, checks dependency resolution and verifies the CLI.
- **Manual only:** `.github/workflows/github_action_test_suite.yml` retains the inherited full nine-environment matrix behind `workflow_dispatch`. It is available for a deliberate upstream engine rebase or a compatibility investigation, but it is not a routine PR gate.
- **No upstream publishing:** remove the inherited Evennia Docker deployment job. A future Ox deployment will use an explicitly named Ox image, its own build recipe and credentials.
- **No upstream docs publishing:** allow inherited documentation checks when appropriate, but guard the actual upstream documentation release step to execute only in `evennia/evennia`.

As meaningful Ox game mechanics are added through Evennia extensions, introduce targeted integration tests for those mechanics. Do **not** interpret the lightweight packaging smoke as a substitute for behavioural integration tests.

## Notice and alert policy

Distinguish failed checks from nonfatal notices. The completed upstream matrix logged deprecations for older Node.js-based GitHub Actions, MySQL `utf8mb3`, Django queries during startup, and some noncritical runner/cache/database messages. Passing the matrix does **not** mean the warnings have all been resolved.

Fix warnings in Ox-owned code when they occur. Track inherited Evennia and GitHub Actions toolchain updates separately and avoid blanket warning suppression. Security analysis remains a separate concern; this ADR does not disable it.

## Future review

Reconsider the CI split if Ox begins changing the inherited `evennia/` engine regularly, adopts multiple production database backends, or needs automated release images.


## Implementation outcome (2026-10-18)

The focused Ox suite now includes `ox-p3-live.yml`, `ox-p3-durable.yml`, `ox-p3-three-crew.yml`, `ox-p4a-concordia-crew.yml` and `ox-p4b-autonomy.yml`, alongside the base ship and handler workflows. These verify ordinary client transport, physical receipts, three-client cooperation, three native Concordia entities and two-incident restart recovery. All nine applicable focused workflows succeeded on `main` after [PR #14](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/14). The inherited broad Evennia matrix remains a separate manual engine-maintenance concern; a passing Ox scenario does not establish upstream compatibility across all database engines.
