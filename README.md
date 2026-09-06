# agent-pr-ledger (v0)

**A ledger of agent-authored pull requests. It counts; it does not score.**

It answers one question about your own repository: of the pull requests opened by coding agents, how many were merged with a **review record** — a review or comment from someone other than the author, before the merge — and how many without?

**What it measures is whether a review record exists** — an auditable trace in the repository's own history. Not whether a review happened, and not how good it was. Those are different questions, and only the first can be answered from outside.

If your team needs to answer a governance or compliance question about agent-authored code — *how much of it entered the default branch without a recorded human review?* — this counts it.

It does not rank repositories. It does not compare agents. It does not tell you what to fix.

By default it sends nothing anywhere. There is an optional exchange — your counts for a place in the population — and it is off until you turn it on. See **What leaves your repository**.

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
| Author account | `Copilot`, `devin-ai-integration[bot]`, `google-labs-jules[bot]` | Certain |
| Branch prefix | `codex/…`, `cursor/…`, `claude/…`, `jules/…`, `devin/…` | Inferred |
| Body signature | `Generated with Claude Code` | Inferred |

Two further outcomes are reported separately and **excluded from the counts**:

- **`trace`** — an agent-ish signal we could not attribute to a specific agent
- **`none`** — no agent trace at all. Treated as a human PR, out of scope

Agents posting under a bot account are identified by name. Agents posting under **your own account** can only be inferred. Both paths were checked against a labelled sample on 2026-09-06 (355 labelled agent PRs, 157 unlabelled PRs from the same repositories); see Limitations for the figures and what they do not prove.

---

## What leaves your repository

**This is the part to read before anything else.** The tool has three modes, and they differ in exactly one respect: what crosses the network.

| Mode | Talks to GitHub API | Fetches our public file | Sends anything about you |
|---|---|---|---|
| **no flag** (plain ledger) | yes — your own repository | no | **no** |
| `--dry-run` | yes | no | **no. Nothing leaves the runner (the GitHub API is still contacted)** |
| `--preview` | yes | **one GET**, same URL for everyone | **no payload. Your IP is visible, as with any HTTPS request** |
| `--send` | yes | no | **yes — see below** |

Running the tool with no exchange flag just prints the ledger; it never contacts anything but the GitHub API. `--dry-run` adds the payload preview and stays offline. `--preview` fetches one public static file so you can see what you would get back — the URL is identical for every user, so the request carries nothing about you, though your IP is of course visible to the network. Only `--send` transmits.

The three flags are **mutually exclusive**; passing two exits with an error rather than silently choosing one.

### What `--send` transmits

1. **The JSON payload** — aggregate counts, a per-month breakdown of those counts, how each agent PR was detected, and two categorical fields (`identity_type`, `size_bucket`). The dry run prints it in full. It is printed in full by the dry run before you ever enable sending, and the server rejects any key outside [`server/schema.json`](server/schema.json).
2. **A GitHub-signed OIDC token**, as the Bearer credential. **Only public repositories are accepted** — the server checks the token's `repository_visibility` claim and rejects anything else, so a private repository's figures cannot reach us even by mistake. This is how the server learns which repository is speaking, without you having an account with us. **That token also carries the workflow context GitHub puts in it — the actor's username, the workflow path, the ref.** We do not choose its contents; GitHub signs them. The server reads `repository` — and `repository_visibility`, because only public repositories are accepted — to check who is speaking. It stores none of it.
3. **Your IP address is visible to the network**, as with any HTTPS request. Access logging on the endpoint is switched off, so it is not recorded — but "not logged" is not "not seen", and we will not claim otherwise.

### What sending means

> **Your repository's name is not stored.**
>
> The OIDC token proves which repository is speaking. That fact is used to check the request is genuine, and then discarded. What lands in storage is a row of counts with no owner: the numbers, your posting-identity type, a size bucket, the month, and which definition version produced them.
>
> Only aggregates are ever published. **There is no page anywhere that carries your repository's name next to these figures.** What we could and could not reconstruct internally is set out under *Why this is free* — it differs by mode and by month, and we would rather write it out than compress it into a slogan here.
>
> For de-duplication we keep a keyed hash of the repository name (HMAC with a server-side secret). It cannot be reversed or looked up without that secret, and it never appears in anything we publish.

**Your receipt is this workflow's log.** What you sent and what came back are printed in full in the run, which lives in your repository's Actions history — in the same place as the `send: true` line that authorised it. The record of the exchange is on your side, not ours.

**What we do not keep cannot leak.** Everything we keep becomes part of a published aggregate. That is the whole of it.

### Two ways to send

| Your question | default (`send` only) | `link: true` |
|---|---|---|
| Will my submissions be connected over time? | No — there is nothing to connect them by. The de-duplication key rotates monthly | **Yes. That is what the option is for** — it is how we can show you your own change since last time |
| What protects my name? | Nothing to protect: we do not store it. Each month has its own salt, deleted on the 2nd of the next month — after which earlier keys cannot be recomputed by anyone. **While the current month's salt is alive, we could still match a name we already suspect** | **A key held in AWS KMS.** Not mathematics: whoever holds that key can check a repository name they already suspect |
| What do I get back | Where you sit in the population now | The same, **plus your own movement** |

Neither row is the safe one. The default keeps less and returns less; `link` returns more and depends on us keeping a key well. **Connection is not a risk we tolerate under `link` — it is the thing the option buys.**

One honest caveat on the default: no *identifier* joins two months, by design. The stored point (month, type, size bucket, counts) is coarse, but we will not claim that an unusual set of values could never be guessed to match across months.

### How consent is recorded

Sending requires `send: true` in your own workflow file. That line lives in your repository, goes through your review, and stays in your git history. **The record of your consent is in your hands, not ours.**

Adding a field to the schema requires a major version of this tool. An update will never start sending something you did not agree to send.

## Permissions and network

```yaml
permissions:
  contents: read
  pull-requests: read
  # id-token: write   # only if you set send: true
```

`pull-requests: write` is never needed — this tool posts nothing to your PRs or issues. Output goes to the job summary.

**No dependencies — Python standard library only.** On the server side, the OIDC signature check is also written against the standard library rather than a crypto package; the one third-party import is `boto3`, which the Lambda runtime ships. So the trust path is: your Python, our Python, and AWS's own SDK.

Hosts contacted: `api.github.com` always; the Actions token endpoint (`ACTIONS_ID_TOKEN_REQUEST_URL`, a `pipelines*.actions.githubusercontent.com` host) in `--send`, to mint the OIDC token; `ledger.atelierfactory.jp` in `--preview` and `--send`. The server, separately, fetches GitHub's public keys from `token.actions.githubusercontent.com` to check the signature. Redirects away from those hosts are refused before the request is followed, so credentials cannot be forwarded elsewhere.

v0 is not a Marketplace Action. You copy a few readable scripts and a workflow into your own repository and pin them yourself. That is deliberate: a tool asking for your trust should not also ask you to run code you cannot read, from a supply chain you do not control.

## Usage

```bash
python3 src/ledger.py OWNER/REPO 300 --lang en
```

- `300` — how many of the most recent PRs to scan. The scan window is printed in the output
- `--lang en|ja` — output language for the ledger (default `en`). The dry-run disclosure block is always in English, so that what you are agreeing to send reads the same for every reviewer
- `--month YYYY-MM` — restrict to one month
- `--json` — machine-readable output (schema below). Honours `--month`; the `detection` block is always for the full scan, not the month
- `--dry-run` (default when the exchange is configured) — print the payload and stop. Offline
- `--preview` — as above, plus one GET of the public cohort file to show what you would get back
- `--link` — with `--send`, store under the cross-service pseudonym. Off unless you ask
- `--send` — transmit. **Only works inside GitHub Actions**, because it needs an OIDC token that only the Actions runner can mint. The workflow turns `send: "true"` into this flag; running it locally exits with an error. See **What leaves your repository**
- A non-numeric or non-positive limit exits with an error. This tool does not silently return different results

Requires Python 3.9+. With `GITHUB_TOKEN` set the API allows 5,000 requests/hour; without it, 60. Limit defaults to 100 when omitted.

`LEDGER_BASE` and `LEDGER_ENDPOINT` override where `--preview` and `--send` connect. They exist for testing; **setting them sends your data somewhere else**, so treat them as you would any endpoint override.

As a workflow, see [`.github/workflows/ledger.yml`](.github/workflows/ledger.yml).

### Watch mode — one PR, at the moment it closes

The ledger looks back once a month. Watch mode applies the same definition to a **single pull request** when it closes, so the answer is in the job summary while the merge is still fresh:

```bash
python3 src/watch.py OWNER/REPO PR_NUMBER [--lang en|ja] [--json] [--fail-on-unrecorded]
```

```
📒 Agent PR watch — microsoft/vscode#334224
  Agent: Copilot  (detected by author, certain; posts as a bot account (external contribution))
  Merged WITH a review record: someone other than the author left a review or comment before the merge.
  "No record" does not mean nobody looked; a review inside the agent's own interface leaves no record here.
  (This is a count, not a judgement — definition v1.0)
```

A PR with no agent trace is reported as out of scope and nothing else happens. Watch mode contacts nothing but the GitHub API, posts nothing to the PR, and **exits 0 whatever it finds**. `--fail-on-unrecorded` makes it exit 1 on a merge without a review record; that turns a count into a gate, which is a policy decision for your repository, so it is off unless you write it into your workflow. There is no exchange in watch mode: nothing is ever sent from it.

As a workflow, see [`.github/workflows/watch.yml`](.github/workflows/watch.yml) (`pull_request: closed`, read-only permissions).

### Output

*Real run: `python3 src/ledger.py microsoft/vscode 300 --lang en`, default mode (nothing sent), executed 2026-09-06.*

```
📒 Agent PR ledger
  scanned: the 300 most recent PRs (2026-09-02 to 2026-09-06)

  Agent PRs in this repository  19   (percentages below are of these)
    ├ merged with a review record  6 (32%)
    ├ merged without a review record  0 (0%)
    └ not merged  13 (68%)

  All 6 merged agent PRs have a review record.

  (This is a count, not a judgement — definition v1.0)
  Comparison with other repositories is shown only if you opt in to sending your counts.

  "No review record" does not mean nobody looked. If the diff was reviewed
  inside the agent's own interface, that review leaves no record on GitHub.
  This counts whether a review record exists — not whether a review happened.

  Classified as: posted under a bot account (external contribution) (bot 74%, self 26%)
  By agent (conventions differ — do not compare across)
    Copilot         14  no record 0%
    Claude_Code      5  no record 0%

  Detection: 14 certain (author) / 2 inferred (branch) / 3 inferred (body)
  ⚠ 3 PR(s) show an agent trace we could not attribute — excluded from the ledger.
  (278 PR(s) with no agent trace are treated as human PRs and are out of scope.)
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
  "month": null,
  "context": null,
  "monthly": [{"month": "2025-07", "agent_prs": 14, "with_record": 3, "without_record": 8}],
  "prs": [{"number": 1, "agent": "OpenAI_Codex", "identity_type": "self",
           "detected_by": "branch", "created_at": "…", "merged_at": "…",
           "outcome": "unrecorded"}]
}
```

`span` and `scanned_prs` always describe the **whole scan**, not the month selected by `--month`. `context_status` is `not_opted_in`, `sent`, or `failed` — so a null `context` after `--send` is distinguishable from never having asked.

`outcome` is one of `recorded`, `unrecorded`, `not_merged`. All five `detection` keys are always present, zero-filled. `span` is `null` when nothing was scanned. `month` echoes `--month`. `context` is `null` unless you used `--send`; with it, it carries the population context — the same four parts the text output shows.

`--dry-run` and `--preview` take precedence over `--json`: they print the payload and exit, so you can always read what would be sent before machine-parsing anything. With `--month`, both `monthly` and the counts are filtered to that month; `detection` is not.

With `--send`, `context` carries what came back:

```json
{
  "cohort": "self",
  "cohort_label": "repositories where agent PRs arrive under a human account",
  "cohort_n": 316,
  "cohort_version": "2026-08",
  "build": "2026-08-13a",
  "regime": "all_unrecorded",
  "regimes": {"all_unrecorded": 0.633, "some_record": 0.367, "all_recorded": 0.067},
  "at_or_above": 0.633,
  "tie_share": 0.633,
  "trend": [{"month": "2025-07", "prs": 5210, "without_record": 0.95}],
  "trend_note": "…",
  "freshness": "…",
  "stored": {"what": ["agent_prs", "…"], "repository_name": "not stored", "note": "…"}
}
```

`regime` is one of `all_unrecorded`, `all_recorded`, `middle`. `trend` is empty for the combined cohort, where movement would be a composition artifact; `trend_note` says so.

---

## Limitations

This is v0. These are real, and we would rather you know them.

1. **Detection precision, measured on 2026-09-06.** Against 355 pull requests with published agent labels (AIDev; one PR per repository per agent, six agents), every one was identified and the agent name matched in every case — *after* a fix made during that measurement: Jules posts as `google-labs-jules[bot]` with free-form branch names, and that account was missing from the table, so 0 of 59 Jules PRs were found before the fix. Against 157 pull requests from the same repositories, inside AIDev's window, that AIDev does not label, 9 were classified as agent-authored — an upper bound of 5.7% on false positives.

   That upper bound is soft, and probably very loose. **AIDev labels the presence of an agent, not its absence**: 8 of the 9 carry the standard `Generated with Claude Code` trailer or a Devin run link and a `devin/` branch, which makes them agent PRs the dataset missed rather than human coincidences. The remaining one says its commits were "generated with Claude Code assistance" and then reviewed by the author — a human-owned PR with agent-written commits, which this tool counts as agent-authored. Read as "PRs a human would not call agent-authored", the bound is 1 of 157 (0.6%). We report 5.7% anyway, because we cannot prove the other 8 from outside. The 22 PRs from `dependabot[bot]`, `renovate[bot]` and similar were all correctly left out.

   A `Co-Authored-By: Claude` trailer on an otherwise human PR would still be counted as agent-authored. The measurement scripts are in [`tools/`](tools/); the labelled data is public.
2. **A review record can be produced trivially.** One comment from any third party before the merge is enough. This counts whether the record exists — it cannot tell you whether the review was serious. Treat it as an audit trail, not as evidence of diligence.
3. **"No record" is not "unreviewed."** See Definition.
4. **Only the most recent N PRs are scanned**, and reviews, issue comments and inline review comments are each read up to 1,000 per PR (3,000 combined). Long histories are truncated; the scan window is always printed.
5. **Bot reviews are excluded**, so an automated review that genuinely caught something is not counted as a record.
6. **Comparison requires opting in.** Without `send`, the tool shows your own numbers only. The cohort files it compares against are built from submissions and from public research data, and both are published.

---

## Why this is free, and what we get

**Your use of this tool helps our marketing.** Saying only "it is free" while keeping that quiet would be dishonest, so we are saying it first.

Here is the whole of it. We are a one-person company that intends to work on how software gets measured in the age of coding agents. To do that credibly we need two things: for people to have heard of us, and for the definitions we publish to be used. A tool that is genuinely useful, given away, is how both happen. If you find this useful and say so, that is the return we are hoping for.

We also learn from the aggregate — but only from submissions people chose to send, only as numbers, and everything we learn is published back as the cohort files this tool reads. There is a private store: the individual points, salted or pseudonymous, that the aggregates are computed from. **No row in it carries a repository name.**

What we are **not** doing: selling your data, selling placement, charging later for what is free now, or keeping a list of repositories to approach.

The first three are choices we are making. The fourth needs splitting, and then splitting again.

- **With `link`**: the pseudonyms are stable, and whoever holds the KMS key could enumerate public repository names against them. What stops it is the key and how we keep it — not the mathematics.
- **Without `link`, for the current month**: the same is true while that month's salt exists. The salt has to exist for de-duplication to work, so this ability cannot be designed away. We are telling you it is there.
- **Without `link`, for any earlier month**: the salt was deleted on the 2nd of the following month. After that, nobody can recompute those keys — including us.

One sentence would have covered all three and been wrong about two of them.

**Being asked and then admitting it is disclosure. Saying it before you ask is honesty. We prefer the second.**

## Why link?

Two reasons, and we will not invent a third.

1. **You get your own movement**, set against the cohort's — not just where you sit today.
2. **Linked submissions build a panel**, and a panel is the only kind of data that can answer *"does changing a repository actually make agents work better?"*

The second is the real one, so it deserves the full story. We tried to answer that question from public data — 33,596 agent pull requests, every repository rewound to the state it was in before the agents arrived. **We could not answer it.** The effects we could measure were dominated by which agent was used and how large the repository was; what could be detected was limited to effects larger than a third to two-thirds of the base rate. The honest summary was: not proven either way, and public data cannot settle it.

Same-repository time series would settle it. That data does not exist anywhere, because nobody keeps it. **`link` is how it comes to exist** — and every cohort file built from it is published back to everyone, including the people who never linked.

That is the pitch. There is no version of it where we know something and are not telling you.

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
