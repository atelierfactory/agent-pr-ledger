#!/usr/bin/env python3
"""Top up the 'other' group of validate_detection.py using the search API.

Listing the most recent PRs misses repositories whose recent activity is all
after AIDev's window. This pass asks the search API for PRs *inside* the window,
drops the ones AIDev labels, fetches one at random, and classifies it.

  python3 tools/validate_detection_topup.py pull_request.parquet --out result.json --other 200
"""
from __future__ import annotations
import argparse, json, os, random, socket, sys, time, urllib.parse, urllib.request, urllib.error
socket.setdefaulttimeout(30)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger import classify, API  # noqa: E402
from validate_detection import get, AIDEV_TO_LEDGER  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet"); ap.add_argument("--out", required=True)
    ap.add_argument("--other", type=int, default=200); ap.add_argument("--seed", type=int, default=20260906)
    a = ap.parse_args()
    token = os.environ["GITHUB_TOKEN"]
    import pandas as pd
    pr = pd.read_parquet(a.parquet)
    pr["repo"] = pr.repo_url.str.replace("https://api.github.com/repos/", "", regex=False)
    labelled = {}
    for repo, num in zip(pr.repo, pr.number):
        labelled.setdefault(repo, set()).add(int(num))
    src = a.out if os.path.exists(a.out) else a.out + ".partial"
    results = json.load(open(src))
    lo, hi = results["window"][0][:10], results["window"][1][:10]
    rng = random.Random(a.seed + 1)
    repos = list(dict.fromkeys(r["repo"] for r in results["agent"]))
    rng.shuffle(repos)
    seen = {r["repo"] for r in results["other"]}
    for repo in repos:
        if len(results["other"]) >= a.other:
            break
        if repo in seen:
            continue
        q = urllib.parse.quote(f"repo:{repo} is:pr created:{lo}..{hi}")
        data, err = get(f"{API}/search/issues?q={q}&per_page=30", token)
        time.sleep(2.5)                        # search API: 30 requests / minute
        if not data or not data.get("items"):
            print(f"  topup: {repo} no PRs in window ({err})", file=sys.stderr); continue
        cands = [it for it in data["items"] if int(it["number"]) not in labelled.get(repo, set())]
        if not cands:
            print(f"  topup: {repo} all PRs in window are AIDev-labelled", file=sys.stderr); continue
        it = rng.choice(cands)
        p, err = get(f"{API}/repos/{repo}/pulls/{it['number']}", token)
        if not p:
            continue
        agent, basis = classify(p)
        results["other"].append({"repo": repo, "number": int(p["number"]), "detected_agent": agent,
                                 "basis": basis, "login": (p.get("user") or {}).get("login"),
                                 "branch": (p.get("head") or {}).get("ref"), "title": p.get("title"),
                                 "html_url": p.get("html_url"), "via": "search"})
        seen.add(repo)
        json.dump(results, open(a.out + ".partial", "w"), ensure_ascii=False)
        if len(results["other"]) % 25 == 0:
            print(f"  other {len(results['other'])}/{a.other}", file=sys.stderr)

    summ = {}
    for r in results["agent"]:
        s = summ.setdefault(r["aidev_agent"], {"n": 0, "detected": 0, "name_match": 0, "basis": {}})
        s["n"] += 1
        if r["detected_agent"]:
            s["detected"] += 1
            if r["detected_agent"] == AIDEV_TO_LEDGER.get(r["aidev_agent"], r["aidev_agent"]):
                s["name_match"] += 1
        s["basis"][r["basis"]] = s["basis"].get(r["basis"], 0) + 1
    flagged = [r for r in results["other"] if r["detected_agent"]]
    traced = [r for r in results["other"] if r["basis"] == "trace"]
    results["summary"] = {"agent": summ, "other": {"n": len(results["other"]), "flagged_as_agent": len(flagged),
                          "trace_only": len(traced)}, "unavailable": len(results["unavailable"])}
    json.dump(results, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(results["summary"], indent=1))
    print("\nflagged in 'other' group:")
    for r in flagged:
        print(f"  {r['html_url']}  {r['detected_agent']} via {r['basis']}  branch={r['branch']}  login={r['login']}")


if __name__ == "__main__":
    main()
