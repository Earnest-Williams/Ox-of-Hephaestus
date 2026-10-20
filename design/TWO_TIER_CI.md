# Two-tier CI (October 2026)

Draft PRs receive the always-on **Ox fast PR gate**: source compilation, CI-scope checks and targeted transport/inbox unit tests. Existing Ox code workflows are retained and triggered on **ready-for-review** PRs, later commits to ready PRs, manual dispatch, and their existing main-branch push events. Their original code-path filters and scenario assertions remain intact. Historical, manual-only upstream/LLM workflows remain opt-in.

**Important:** GitHub cannot natively require a dynamic collection of path-filtered individual workflows without appropriate branch rules. The repository currently lacks protected-branch required checks. Do not merge until the head SHA has completed and all applicable final-tier jobs have passed; configure a protected branch rule once the required checks strategy is decided. Do not treat the fast gate alone as final verification.

For an overview in one Actions API request:

```bash
GH_TOKEN="$(gh auth token)" python .github/ci/ox_bulk_status.py --repo Earnest-Williams/Ox-of-Hephaestus --sha "$(git rev-parse HEAD)"
```

Use `--strict` only when validating the applicable runs for an exact head. Check for intentionally skipped workflows and the expected final-tier set separately. The status tool refuses truncated results rather than silently considering an incomplete page a pass. The GitHub UI remains the record of authoritative per-job checks.

Python setup uses `actions/setup-python`'s pip download cache keyed by project metadata and `uv.lock`. It avoids repeated network downloads but still installs dependencies in each runner; it does not cache virtual environments or share a world database. Cached dependency restoration is scoped to the repository trust model, and no credentials are included.

The historical paths in `design/CI.md` continue to apply. Documentation-only changes retain their dedicated documentation validator and the fast gate; full live verification remains available by manual dispatch or an appropriate ready-for-review code change.
