#!/usr/bin/env python3
"""One-request GitHub Actions status overview for an exact commit."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

def summarize(runs):
    latest = {}
    for run in runs:
        name = run.get("name", "(unnamed)")
        if name not in latest or (run.get("created_at", ""), run.get("id", 0)) > (latest[name].get("created_at", ""), latest[name].get("id", 0)):
            latest[name] = run
    groups = {"passed": [], "failed": [], "waiting": [], "cancelled": []}
    for name, run in sorted(latest.items()):
        status, result = run.get("status"), run.get("conclusion")
        group = ("waiting" if status != "completed" else "passed" if result == "success" else "cancelled" if result in ("cancelled", "skipped", "neutral") else "failed")
        groups[group].append({"name": name, "status": status, "conclusion": result, "url": run.get("html_url"), "run_id": run.get("id")})
    return groups

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--sha", required=True, help="exact full commit SHA")
    parser.add_argument("--strict", action="store_true", help="fail when any listed workflow is not successful")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    if len(args.sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in args.sha):
        parser.error("--sha must be the exact 40-character commit SHA")
    if len(args.repo.split("/")) != 2 or not all(args.repo.split("/")):
        parser.error("--repo must be owner/name")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GH_TOKEN or GITHUB_TOKEN is required")
    owner, repo = args.repo.split("/")
    url = "https://api.github.com/repos/{}/{}/actions/runs?{}".format(
        urllib.parse.quote(owner), urllib.parse.quote(repo),
        urllib.parse.urlencode({"head_sha": args.sha, "per_page": 100}))
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except (urllib.error.URLError, ValueError) as exc:
        print("GitHub status query failed: " + str(exc), file=sys.stderr)
        return 2
    total = data.get("total_count", 0)
    if total > len(data.get("workflow_runs", [])):
        print("Too many runs for one API page; refusing incomplete status", file=sys.stderr)
        return 2
    groups = summarize(data.get("workflow_runs", []))
    if args.json:
        print(json.dumps({"sha": args.sha, "total_runs": total, "groups": groups}, indent=2))
    else:
        print("Commit {}: {} runs, {} unique workflows".format(args.sha, total, sum(map(len, groups.values()))))
        for group in ("failed", "waiting", "cancelled", "passed"):
            print("{} ({}):".format(group.upper(), len(groups[group])))
            for item in groups[group]:
                print("  {} | {}".format(item["name"], item["url"]))
    return 1 if args.strict and (not total or any(groups[x] for x in ("failed", "waiting", "cancelled"))) else 0

if __name__ == "__main__":
    sys.exit(main())
