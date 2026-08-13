#!/usr/bin/env python3
"""表示ロジックの検証。GitHub APIを叩かずに、代表的な形を全部通す。

とくに確認したいこと：
- 審査記録なしが1件でもあれば、警告行が必ず最初に出る（パーセンタイルを免罪符にしない）
- 記録なしがゼロなら、警告ではなく事実を書く
- エージェント間の比較を煽らない
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
    "記録なしが多数（本人名義型）": dict(
        rows=[row(i, "OpenAI_Codex", "self", "branch", "2025-07",
                  "unrecorded" if i < 24 else "recorded" if i < 35 else "not_merged")
              for i in range(42)],
        coverage={"author": 0, "branch": 42, "body": 0, "unknown": 5}),
    "記録なしがゼロ（ボット名義型）": dict(
        rows=[row(i, "Copilot", "bot", "author", "2025-07",
                  "recorded" if i < 10 else "not_merged") for i in range(17)],
        coverage={"author": 17, "branch": 0, "body": 0, "unknown": 3}),
    "マージが1件も無い": dict(
        rows=[row(i, "Cursor", "self", "branch", "2025-07", "not_merged") for i in range(4)],
        coverage={"author": 0, "branch": 4, "body": 0, "unknown": 0}),
    "エージェントPRがゼロ": dict(rows=[], coverage={"none": 30}),
}

# 判定の偽陽性ケース（人間のPRに co-authored-by トレーラーが1行あるだけ）
from ledger import classify
FP = [
    ({"user": {"login": "alice"}, "head": {"ref": "fix/typo"},
      "body": "Co-Authored-By: Claude <noreply@anthropic.com>"}, "body",
     "人間のPRにトレーラー1行 → エージェント作と判定される（既知の偽陽性）"),
    ({"user": {"login": "bob"}, "head": {"ref": "codex/experiment"}, "body": ""}, "branch",
     "人間が codex/ をブランチ名に使った場合（既知の偽陽性）"),
]
print("=" * 66); print("■ 既知の偽陽性（精度検証で必ず測る）"); print("=" * 66)
for pr_, expect, note in FP:
    a, how = classify(pr_)
    print(f"  {note}\n    → 判定 {how} / agent={a}")
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
            fails.append(f"{name}: 記録なしが{len(unrec)}件あるのに警告行が出ていない")
        else:
            before = lines[:warn_idx]
            if any(("median" in l or "percentile" in l or "distribution" in l or "母集団" in l) for l in before):
                fails.append(f"{name}: 警告行より前に比較の文脈が出ている（免罪符になる）")
    else:
        if warn_idx is not None:
            fails.append(f"{name}: 記録なしがゼロなのに警告行が出ている")
    if any(w in out for w in ("better than", "ranking", "score", "grade", "より優れて")):
        fails.append(f"{name}: 優劣の表現が混入している")

print("=" * 66)
if fails:
    print("失敗:"); [print("  -", f) for f in fails]; sys.exit(1)
print(f"すべて通過（{len(CASES)}ケース）")
