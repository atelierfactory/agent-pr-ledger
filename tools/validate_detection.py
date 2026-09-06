#!/usr/bin/env python3
"""Measure the detection rules in src/ledger.py against AIDev labels.

Two groups, same repositories, same collection window:

  agent  - PRs that AIDev labels with an agent  -> recall, per agent
  other  - PRs in the same repositories, inside AIDev's window, that AIDev
           does NOT label                        -> upper bound on false positives

"other" is not "human": AIDev labels the presence of an agent, not its absence.
So the false-positive figure is an upper bound, and every flagged PR is listed
so it can be inspected by hand.

Sampling is one PR per repository per agent, so no single account dominates.

Requires: pandas + pyarrow (for the parquet file only) and GITHUB_TOKEN.
The ledger itself has no dependencies; this is a research script.

  python3 tools/validate_detection.py pull_request.parquet --per-agent 60 --other 200 --out result.json
"""
from __future__ import annotations
import argparse, json, os, random, socket, sys, time, urllib.request, urllib.error
socket.setdefaulttimeout(30)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger import classify, API  # noqa: E402

AIDEV_TO_LEDGER = {"Google_Jules": "Jules"}   # other names are identical


def get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/vnd.github+json",
                                               "User-Agent": "agent-pr-ledger-validation"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                remaining = r.headers.get("X-RateLimit-Remaining")
                if remaining is not None and int(remaining) < 50:
                    reset = int(r.headers.get("X-RateLimit-Reset", "0"))
                    time.sleep(max(0, reset - time.time()) + 5)
                return json.loads(r.read().decode()), None
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} {url}", file=sys.stderr)
            if e.code in (403, 429) and attempt < 3:
                time.sleep(30); continue
            return None, e.code
        except Exception as e:  # noqa: BLE001
            print(f"  {type(e).__name__}: {e} {url}", file=sys.stderr)
            if attempt < 3:
                time.sleep(5); continue
            return None, str(e)
    return None, "gave up"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet")
    ap.add_argument("--per-agent", type=int, default=60)
    ap.add_argument("--other", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260906)
    ap.add_argument("--out", default="validation_result.json")
    a = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required")
    import pandas as pd
    pr = pd.read_parquet(a.parquet)
    pr["repo"] = pr.repo_url.str.replace("https://api.github.com/repos/", "", regex=False)
    window = (pr.created_at.min(), pr.created_at.max())
    labelled = {}                      # repo -> set of PR numbers AIDev labels
    for repo, num in zip(pr.repo, pr.number):
        labelled.setdefault(repo, set()).add(int(num))
    rng = random.Random(a.seed)

    # --- agent group: one PR per repository per agent ---
    agent_rows = []
    for agent, g in pr.groupby("agent"):
        one_per_repo = g.groupby("repo").sample(n=1, random_state=a.seed)
        pick = one_per_repo.sample(n=min(a.per_agent, len(one_per_repo)), random_state=a.seed)
        for r in pick.itertuples():
            agent_rows.append({"repo": r.repo, "number": int(r.number), "aidev_agent": agent,
                               "aidev_user": r.user})
    print(f"agent group: {len(agent_rows)} PRs", file=sys.stderr)

    ckpt = a.out + ".partial"
    results = {"window": [str(window[0]), str(window[1])], "seed": a.seed,
               "agent": [], "other": [], "unavailable": []}
    if os.path.exists(ckpt):
        old = json.load(open(ckpt))
        results.update({k: old.get(k, []) for k in ("agent", "other", "unavailable")})
        print(f"resuming: {len(results['agent'])} agent / {len(results['other'])} other already done", file=sys.stderr)
    done = {(r["repo"], r["number"]) for r in results["agent"] + results["unavailable"]}
    def save():
        json.dump(results, open(ckpt, "w"), ensure_ascii=False)
    for i, row in enumerate(agent_rows, 1):
        if (row["repo"], row["number"]) in done:
            continue
        data, err = get(f"{API}/repos/{row['repo']}/pulls/{row['number']}", token)
        if data is None:
            results["unavailable"].append({**row, "error": err}); continue
        agent, basis = classify(data)
        results["agent"].append({**row, "detected_agent": agent, "basis": basis,
                                 "login": (data.get("user") or {}).get("login"),
                                 "branch": (data.get("head") or {}).get("ref")})
        if i % 25 == 0:
            save(); print(f"  agent {i}/{len(agent_rows)}", file=sys.stderr)
    save()

    # --- other group: same repos, inside the window, not labelled by AIDev ---
    repos = list(dict.fromkeys(r["repo"] for r in agent_rows))
    rng.shuffle(repos)
    lo, hi = window
    seen_other = {r["repo"] for r in results["other"]}
    for repo in repos:
        if len(results["other"]) >= a.other:
            break
        if repo in seen_other:
            continue
        print(f"  other: listing {repo}", file=sys.stderr)
        data, err = get(f"{API}/repos/{repo}/pulls?state=all&sort=created&direction=desc&per_page=50", token)
        if not data:
            continue
        cands = [p for p in data if lo <= p["created_at"] <= hi
                 and int(p["number"]) not in labelled.get(repo, set())]
        if not cands:
            continue
        p = rng.choice(cands)
        agent, basis = classify(p)
        results["other"].append({"repo": repo, "number": int(p["number"]), "detected_agent": agent,
                                 "basis": basis, "login": (p.get("user") or {}).get("login"),
                                 "branch": (p.get("head") or {}).get("ref"),
                                 "title": p.get("title"), "html_url": p.get("html_url")})
        save()
        if len(results["other"]) % 25 == 0:
            print(f"  other {len(results['other'])}/{a.other}", file=sys.stderr)

    # --- summary ---
    summ = {}
    for r in results["agent"]:
        s = summ.setdefault(r["aidev_agent"], {"n": 0, "detected": 0, "name_match": 0, "basis": {}})
        s["n"] += 1
        if r["detected_agent"]:
            s["detected"] += 1
            if r["detected_agent"] == AIDEV_TO_LEDGER.get(r["aidev_agent"], r["aidev_agent"]):
                s["name_match"] += 1
        s["basis"][r["basis"]] = s["basis"].get(r["basis"], 0) + 1
    other_n = len(results["other"])
    flagged = [r for r in results["other"] if r["detected_agent"]]
    traced = [r for r in results["other"] if r["basis"] == "trace"]
    results["summary"] = {"agent": summ, "other": {"n": other_n, "flagged_as_agent": len(flagged),
                          "trace_only": len(traced)}, "unavailable": len(results["unavailable"])}
    json.dump(results, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(results["summary"], indent=1))
    print("\nflagged in 'other' group:")
    for r in flagged:
        print(f"  {r['html_url']}  {r['detected_agent']} via {r['basis']}  branch={r['branch']}  login={r['login']}")


if __name__ == "__main__":
    main()
