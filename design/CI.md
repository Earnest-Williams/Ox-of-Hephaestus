# Ox GitHub Actions trigger policy

**Current policy (19 October 2026):** changes to Markdown project documentation
are checked by the lightweight [Ox documentation workflow](../.github/workflows/ox-documentation.yml),
not by the real-world, multi-client or model-handling suites. These were
previously triggered unnecessarily by `game/**`, `services/ai-handler/**`
and `design/**` even for README-only changes.

## Event policy

| Change | Expected automation |
| --- | --- |
| Ox Markdown documentation only | Documentation consistency, including agent-context rot, local links and the trigger-policy regression |
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
