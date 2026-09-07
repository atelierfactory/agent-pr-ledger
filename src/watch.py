#!/usr/bin/env python3
"""Watch mode: one pull request, at the moment it closes (definition v1.0).

Same rules as ledger.py, applied to a single PR. Meant to run from a
`pull_request: closed` workflow, so the answer to "did this agent PR enter the
default branch with a review record?" is in the job summary while it is still
fresh — not a month later.

It contacts nothing but the GitHub API. It posts nothing to the PR. It exits 0
whatever it finds, unless you pass --fail-on-unrecorded, which is a policy
choice that belongs to your repository, not to this tool.

  python3 src/watch.py OWNER/REPO PR_NUMBER [--lang en|ja] [--json] [--fail-on-unrecorded]
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from ledger import (GitHub, classify, classify_merge, DEFINITION_VERSION, IDENTITY_TYPE)  # noqa: E402

TEXT = {
    "en": {
        "title": "📒 Agent PR watch — {repo}#{num}",
        "not_agent": "  No agent trace: treated as a human PR, out of scope. Nothing to record.",
        "trace": "  An agent-ish trace that could not be attributed to a specific agent — excluded from the ledger.",
        "agent": "  Agent: {agent}  (detected by {basis}, {certainty}; posts as {itype})",
        "not_merged": "  Closed without merge.",
        "recorded": "  Merged WITH a review record: someone other than the author left a review or comment before the merge.",
        "unrecorded": "  Merged WITHOUT a review record: no review or comment from a third party exists before the merge timestamp.",
        "note": "  \"No record\" does not mean nobody looked; a review inside the agent's own interface leaves no record here.\n  (This is a count, not a judgement — definition v{ver})",
        "certain": "certain", "inferred": "inferred",
        "bot": "a bot account (external contribution)", "self": "the author's own account (own work)",
    },
    "ja": {
        "title": "📒 エージェントPRの見張り — {repo}#{num}",
        "not_agent": "  エージェントの痕跡なし：人のPRとして対象外。記録するものはありません。",
        "trace": "  エージェントらしい痕跡はあるが、どのエージェントか特定できません。台帳からは除外します。",
        "agent": "  エージェント: {agent}  （根拠: {basis}、{certainty}。名義: {itype}）",
        "not_merged": "  マージせずに閉じられました。",
        "recorded": "  審査記録ありでマージ：作成者以外の人が、マージより前にレビューかコメントを残しています。",
        "unrecorded": "  審査記録なしでマージ：マージ時刻より前に、第三者のレビューもコメントもありません。",
        "note": "  「記録なし」は「誰も見ていない」ではありません。エージェントの画面の中での確認は、ここに記録が残りません。\n  （これは数えただけで、判定ではありません — 定義 v{ver}）",
        "certain": "確実", "inferred": "推定",
        "bot": "ボット名義（外部からの寄稿）", "self": "本人名義（自分の作業）",
    },
}


def watch(repo: str, num: int, token: str | None = None) -> dict:
    gh = GitHub(token)
    pr = gh.get(f"/repos/{repo}/pulls/{num}")
    agent, basis = classify(pr)
    out = {"schema": "agent-pr-ledger/watch-v1", "definition_version": DEFINITION_VERSION,
           "repo": repo, "number": num, "agent": agent, "detected_by": basis,
           "identity_type": IDENTITY_TYPE.get(agent) if agent else None,
           "merged_at": pr.get("merged_at"), "outcome": None}
    if agent:
        out["outcome"] = classify_merge(pr, gh.reviews(repo, num), gh.comments(repo, num),
                                        gh.review_comments(repo, num))
    return out


def render(w: dict, lang: str = "en") -> str:
    t = TEXT[lang]
    lines = [t["title"].format(repo=w["repo"], num=w["number"])]
    if not w["agent"]:
        lines.append(t["trace"] if w["detected_by"] == "trace" else t["not_agent"])
        return "\n".join(lines)
    lines.append(t["agent"].format(agent=w["agent"], basis=w["detected_by"],
                                   certainty=t["certain"] if w["detected_by"] == "author" else t["inferred"],
                                   itype=t[w["identity_type"]]))
    lines.append(t[w["outcome"]])
    lines.append(t["note"].format(ver=w["definition_version"]))
    return "\n".join(lines)


def main(argv):
    if len(argv) < 3 or not argv[2].isdigit():
        print("usage: watch.py OWNER/REPO PR_NUMBER [--lang en|ja] [--json] [--fail-on-unrecorded]",
              file=sys.stderr)
        return 2
    KNOWN = {"--lang", "--json", "--fail-on-unrecorded"}
    bad = [a for a in argv[3:] if a.startswith("--") and a not in KNOWN]
    if bad:
        print(f"error: unknown option {bad[0]}", file=sys.stderr); return 2
    lang = "en"
    if "--lang" in argv:
        i = argv.index("--lang") + 1
        if i >= len(argv) or argv[i] not in TEXT:
            print(f"error: --lang must be one of {sorted(TEXT)}", file=sys.stderr); return 2
        lang = argv[i]
    w = watch(argv[1], int(argv[2]))
    print(json.dumps(w, indent=1) if "--json" in argv else render(w, lang))
    if "--fail-on-unrecorded" in argv and w["outcome"] == "unrecorded":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))


def cli():
    """Console-script entry point."""
    sys.exit(main(sys.argv))
