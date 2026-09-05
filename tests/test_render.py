#!/usr/bin/env python3
"""Rendering checks. Runs every representative shape without touching the GitHub API.

What these guard:
- if even one merge lacks a review record, that line appears before any comparison
- when none lack a record, state the fact rather than warn
- never invite comparison between agents
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from ledger import render, DEFINITION_VERSION


def row(n, agent, itype, how, ym, outcome):
    return {"number": n, "agent": agent, "identity_type": itype, "detected_by": how,
            "created_at": f"{ym}-15T00:00:00Z",
            "merged_at": None if outcome == "not_merged" else f"{ym}-16T00:00:00Z",
            "outcome": outcome}


CASES = {
    "mostly unrecorded (human-authored type)": dict(
        rows=[row(i, "OpenAI_Codex", "self", "branch", "2025-07",
                  "unrecorded" if i < 24 else "recorded" if i < 35 else "not_merged")
              for i in range(42)],
        coverage={"author": 0, "branch": 42, "body": 0, "unknown": 5}),
    "none unrecorded (bot-authored type)": dict(
        rows=[row(i, "Copilot", "bot", "author", "2025-07",
                  "recorded" if i < 10 else "not_merged") for i in range(17)],
        coverage={"author": 17, "branch": 0, "body": 0, "unknown": 3}),
    "nothing merged": dict(
        rows=[row(i, "Cursor", "self", "branch", "2025-07", "not_merged") for i in range(4)],
        coverage={"author": 0, "branch": 4, "body": 0, "unknown": 0}),
    "no agent PRs at all": dict(rows=[], coverage={"none": 30}),
}

# Known false positives: a human PR carrying a single co-authored-by trailer
from ledger import classify
FP = [
    ({"user": {"login": "alice"}, "head": {"ref": "fix/typo"},
      "body": "Co-Authored-By: Claude <noreply@anthropic.com>"}, "body",
     "human PR with one trailer -> classified as agent-authored (known false positive)"),
    ({"user": {"login": "bob"}, "head": {"ref": "codex/experiment"}, "body": ""}, "branch",
     "human using a codex/ branch name (known false positive)"),
]
print("=" * 66); print("Known false positives (always measured in the precision check)"); print("=" * 66)
for pr_, expect, note in FP:
    a, how = classify(pr_)
    print(f"  {note}\n    -> classified {how} / agent={a}")
print()

fails = []
for name, d in CASES.items():
    led = {"repo": "example/repo", "definition_version": DEFINITION_VERSION,
           "rows": d["rows"], "coverage": d["coverage"], "api_calls": 0}
    out = render(led)
    print("=" * 66); print(f"■ {name}"); print("=" * 66); print(out); print()

    merged = [r for r in d["rows"] if r["outcome"] != "not_merged"]
    unrec = [r for r in merged if r["outcome"] == "unrecorded"]
    lines = out.splitlines()
    warn_idx = next((i for i, l in enumerate(lines)
                     if "% of merged agent PRs have no review record" in l), None)
    if unrec:
        if warn_idx is None:
            fails.append(f"{name}: {len(unrec)} unrecorded merges but no warning line")
        else:
            before = lines[:warn_idx]
            if any(("median" in l or "percentile" in l or "distribution" in l or "母集団" in l) for l in before):
                fails.append(f"{name}: comparison appears before the warning line (reads as absolution)")
    else:
        if warn_idx is not None:
            fails.append(f"{name}: warning line shown although nothing is unrecorded")
    if any(w in out for w in ("better than", "ranking", "score", "grade", "より優れて")):
        fails.append(f"{name}: comparative or evaluative wording leaked in")

# Mutually exclusive flags: never silently pick one (a --dry-run must never send)
import subprocess, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
print("=" * 66); print("Mutually exclusive flags"); print("=" * 66)
for combo in (["--dry-run","--send"], ["--preview","--send"], ["--dry-run","--preview"]):
    r = subprocess.run([sys.executable, os.path.join(ROOT,"src","ledger.py"), "a/b", "10", *combo],
                       capture_output=True, text=True, timeout=30)
    ok = r.returncode == 2 and "mutually exclusive" in r.stderr
    print(f"  {' '.join(combo):24} → {'exits 2' if ok else '*** ACCEPTED — must not be'}")
    if not ok:
        fails.append(f"mutually exclusive flags {combo} were not rejected")
print()

print("=" * 66)
if fails:
    print("FAILED:"); [print("  -", f) for f in fails]; sys.exit(1)
print(f"all passed ({len(CASES)} cases)")
