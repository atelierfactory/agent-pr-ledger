# agent-pr-ledger (v0)

**A ledger of agent-authored pull requests. It counts; it does not score.**

It answers one question about your own repository: of the pull requests opened by coding agents, how many were merged with a **review record** — a review or comment from someone other than the author, before the merge — and how many without?

**What it measures is whether a review record exists** — an auditable trace in the repository's own history. Not whether a review happened, and not how good it was. Those are different questions, and only the first can be answered from outside.

If your team needs to answer a governance or compliance question about agent-authored code — *how much of it entered the default branch without a recorded human review?* — this counts it.

It does not rank repositories. It does not compare agents. It does not tell you what to fix.

---

## Definition v1.0

| Outcome | Condition |
|---|---|
| **Merged with a review record** | Someone **other than the PR author**, and not a bot, left a review or a comment **before the merge timestamp** |
| **Merged without a review record** | No such record exists |
| **Not merged** | — |

A comment the author leaves on their own PR — an instruction to the agent, a note to themselves — is not third-party review, so it does not count. A human comment on a **bot-authored** PR does count: the bot is the author, so the human is a third party.

"Review record" means the review is visible in the repository's own history, and therefore auditable. If you reviewed the diff inside the agent's interface and merged, that review happened — it simply left no record here.

Definitions are versioned. Any change ships with a version bump and a migration note.

---

## How agent PRs are identified

Three signals, in order. **The output always states which one was used.**

| Signal | Example | Certainty |
|---|---|---|
| Author account | `Copilot`, `devin-ai-integration[bot]` | Certain |
| Branch prefix | `codex/…`, `cursor/…`, `claude/…`, `jules/…`, `devin/…` | Inferred |
| Body signature | `Generated with Claude Code` | Inferred |

Two further outcomes are reported separately and **excluded from the counts**:

- **`trace`** — an agent-ish signal we could not attribute to a specific agent
- **`none`** — no agent trace at all. Treated as a human PR, out of scope

Agents posting under a bot account are identified reliably. Agents posting under **your own account** can only be inferred, and **that inference has not been measured yet.** See Limitations.

---

## Permissions and network

```yaml
permissions:
  contents: read
  pull-requests: read
```

That is the whole declaration. The default output goes to the job summary; this tool posts nothing you did not ask for.

**No dependencies — Python standard library only. It talks to the GitHub API and nothing else.** No telemetry, no model download, no external host.

v0 is not a Marketplace Action. You copy one readable script and a workflow into your own repository and pin them yourself. That is deliberate: a tool asking for your trust should not also ask you to run code you cannot read, from a supply chain you do not control.

---

## Usage

```bash
python3 src/ledger.py OWNER/REPO 300 --lang en
```

- `300` — how many of the most recent PRs to scan. The scan window is printed in the output
- `--lang en|ja` — output language (default `en`)
- `--month YYYY-MM` — restrict to one month
- `--json` — machine-readable output (schema below). Honours `--month`; the `detection` block is always for the full scan, not the month
- A non-numeric or non-positive limit exits with an error. This tool does not silently return different results

Requires Python 3.9+. With `GITHUB_TOKEN` set the API allows 5,000 requests/hour; without it, 60.

As a workflow, see [`.github/workflows/ledger.yml`](.github/workflows/ledger.yml).

### Output

*The example below is generated from synthetic data. It will be replaced with a real run before v0.1.*

```
📒 Agent PR ledger
  scanned: the 50 most recent PRs (2025-05-02 to 2025-07-28)

  Agent PRs in this repository  42   (percentages below are of these)
    ├ merged with a review record  11 (26%)
    ├ merged without a review record  24 (57%)
    └ not merged  7 (17%)

  69% of merged agent PRs have no review record.

  (This is a count, not a judgement — definition v1.0)
  Comparison with other repositories is not shown in v0.

  "No review record" does not mean nobody looked. If the diff was reviewed
  inside the agent's own interface, that review leaves no record on GitHub.
  This counts whether a review record exists — not whether a review happened.

  Classified as: posted under your own account (your own work)
  By agent (conventions differ — do not compare across)
    OpenAI_Codex    42  no record 69%

  Recent months  (rates are of merged PRs)
    2025-05   14 PRs  (12 merged)  no record 67%
    2025-06   14 PRs  (12 merged)  no record 67%
    2025-07   14 PRs  (11 merged)  no record 73%

  Detection: 0 certain (author) / 42 inferred (branch) / 0 inferred (body)
  ⚠ 2 PR(s) show an agent trace we could not attribute — excluded from the ledger.
  (6 PR(s) with no agent trace are treated as human PRs and are out of scope.)
```

### JSON schema (`--json`)

```json
{
  "schema": "agent-pr-ledger/v1",
  "definition_version": "1.0",
  "repo": "owner/name",
  "scanned_prs": 50,
  "span": ["2025-05-15", "2025-07-15"],
  "counts": {
    "agent_prs": 42,
    "merged_with_review_record": 11,
    "merged_without_review_record": 24,
    "not_merged": 7
  },
  "detection": {"author": 0, "branch": 42, "body": 0, "trace": 2, "none": 6},
  "detection_scope": "all scanned PRs (not filtered by --month)",
  "monthly": [{"month": "2025-07", "agent_prs": 14, "with_record": 3, "without_record": 8}],
  "prs": [{"number": 1, "agent": "OpenAI_Codex", "identity_type": "self",
           "detected_by": "branch", "created_at": "…", "merged_at": "…",
           "outcome": "unrecorded"}]
}
```

`outcome` is one of `recorded`, `unrecorded`, `not_merged`. All five `detection` keys are always present, zero-filled. `span` is `null` when nothing was scanned.

---

## Limitations

This is v0. These are real, and we would rather you know them.

1. **Detection precision is unmeasured** for agents posting under a human account. A single `Co-Authored-By: Claude` trailer on an otherwise human PR is counted as agent-authored; so is a human who names a branch `codex/…`.
2. **A review record can be produced trivially.** One comment from any third party before the merge is enough. This counts whether the record exists — it cannot tell you whether the review was serious. Treat it as an audit trail, not as evidence of diligence.
3. **"No record" is not "unreviewed."** See Definition.
4. **Only the most recent N PRs are scanned**, and reviews, issue comments and inline review comments are each read up to 1,000 per PR (3,000 combined). Long histories are truncated; the scan window is always printed.
5. **Bot reviews are excluded**, so an automated review that genuinely caught something is not counted as a record.
6. **No comparison is shown.** A population distribution needs a definition both sides can compute; that work is unfinished.

---

## What this tool will never do

- Score or grade your repository
- Rank agents against each other. A bot-authored contribution and a developer's own tool-assisted work are not the same social act, and putting them on one scale produces nonsense
- Tell you that a number is good or bad. That judgement belongs to your team

---

## Background

These definitions came out of an empirical study of 33,596 agent-authored pull requests. In short: commonly used metrics — merge rate, rework rate, self-merge rate — largely measure **agent conventions** rather than outcomes. Median time-to-merge for agent PRs ranges from 50 seconds to 17.7 hours depending on which agent opened them. Whether a review record exists depends far more on **how the agent posts** — as a bot, or as you — than on which agent it is.

The full study, with data and reproduction code, will be published separately.

---

## License

MIT. See [LICENSE](LICENSE).
