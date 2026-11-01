# Ox GitHub Actions trigger policy

**Current policy (verified 30 October 2026):** Markdown-only changes are
checked by the [Ox documentation workflow](../.github/workflows/ox-documentation.yml).
Opening or updating any PR also triggers the separate, unconditional
[fast PR gate](../.github/workflows/ox-fast.yml); documentation-only changes
do not trigger the longer path-scoped gameplay and model-handling suites.
Before path filters were refined, those suites could be triggered even by
README-only edits under `game/**`, `services/ai-handler/**` or `design/**`.

## Event policy

| Change | Expected automation |
| --- | --- |
| Ox Markdown documentation only | Documentation consistency **and the unconditional fast PR gate on PR events**; no slow path-scoped gameplay suites |
| Python, fixtures, migrations, settings, or other non-Markdown code | Relevant path-scoped Ox game/handler workflows |
| Code plus documentation | Same code workflows as for code alone **and** documentation checks |
| A particular code workflow YAML | That workflow's tests plus the lightweight documentation/policy guard |
| New commit while a PR's old tests are still running | Prior runs of the **same workflow on that PR** are cancelled; the new commit is tested |
| Manual `workflow_dispatch` | Always available regardless of changed paths; experimental Gemini and broad inherited Evennia tests remain opt-in |

An automatic code workflow includes a final `!**/*.md` negative path
pattern **after all positive paths**. This is GitHub's documented
ordered path-filter syntax; it does not exclude code within a touched
directory. A non-Markdown workflow edit still matches the workflow's own
explicit path. The documentation workflow monitors `.github/ci/**`
and `.github/workflows/ox-*.yml` so CI policy edits receive validation.

Workflow-level PR concurrency keys use the workflow name plus the PR
number; only superseded **pull-request** runs are cancelled. Pushes to
`main` and manual runs are not cancelled by a later PR commit. This
reduces wasted CI on iterative feature branches without silently changing
acceptance criteria for a current head.

The no-dependency validator at
[`.github/ci/check_ox_ci_scope.py`](../.github/ci/check_ox_ci_scope.py)
guards representative documentation-only and mixed changes and checks
that broad code-test path filters have the Markdown exclusion last.

## Database

Ox CI runs on PostgreSQL only ([ADR 0010](decisions/0010-postgresql-only-game-managed.md)).
Each job uses the game-managed cluster in `game/server/pgdata/`, initialised
on first connection from the PostgreSQL programs GitHub's Ubuntu runners
already ship, so no service container is needed. Probes that need a
disposable database select it with `OX_PG_DATABASE` (`ox_contention_ci`,
`ox_g19_restart`). The inherited Evennia matrix is manual and PostgreSQL-only.

Installed-ship suites pass `--prebuilt-ship` to `world.test_runner`: the
canonical ship is built once per design fingerprint into `ox_ship_<hash>`
(about 70 s on a runner), vacuumed and analysed, and each test database is
cloned from it instead of rebuilding the 421 spaces (about 93,000 queries)
in every `setUp`. Use it only when every selected test runs on the canonical
installed ship; builder tests with synthetic models need an empty world.
Installed test classes set up with `ensure_canonical_ship()`, which returns
at once on a complete ship (as server startup does) instead of re-walking
every space and exit (about 78,000 queries per test). Together, the 38
installed-ship workflows take 172 runner-minutes on PostgreSQL against 308
on SQLite.

## Exceptions and limits

The old standalone test workflows remain explicitly manual; some tightly
scoped tests already target exact Python paths and did not need changes.
The inherited Evennia documentation build and compatibility matrix are
separate from the Ox-owned workflows.

GitHub can report intentionally path-skipped checks as pending if those
checks were configured as **unconditionally required** by branch protection.
Any future required-check policy must account for path-scoped workflows.
GitHub's file-diff path filtering also has platform limits for very large
PRs; critical release candidates can run the individual manual workflows
or the full validation matrix. A passing scoped check proves its tested
conditions, not general autonomous intelligence or production readiness.
