# AGENTS.md — for coding agents working in or with this repository

You are reading the repository of **agent-pr-ledger**, a read-only GitHub Action that counts, for one repository, how many agent-authored pull requests were merged with a human review record and how many without (definition v1.0). It counts; it does not score.

## If you were asked to *use* this tool in another repository

Add one workflow. Nothing leaves the runner except GitHub API calls unless `mode: send` is set.

```yaml
# .github/workflows/agent-pr-ledger.yml
name: Agent PR ledger
on:
  workflow_dispatch:
  schedule:
    - cron: "0 3 1 * *"
permissions:
  contents: read
  pull-requests: read
jobs:
  ledger:
    runs-on: ubuntu-latest
    steps:
      - uses: atelierfactory/agent-pr-ledger@v0.1
        with:
          limit: "300"
```

Per-PR watch mode (runs when a PR closes; exits 0 whatever it finds unless `fail-on-unrecorded: "true"`):

```yaml
on:
  pull_request:
    types: [closed]
permissions:
  contents: read
  pull-requests: read
jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: atelierfactory/agent-pr-ledger@v0.1
        with:
          pr: ${{ github.event.pull_request.number }}
```

Pin to a commit SHA if the target repository's policy requires it. Never add `pull-requests: write`; the tool does not need it and never posts to PRs.

## If you were asked to *modify* this repository

- Python 3.9+, standard library only. Do not add dependencies to `src/`. (`tools/` is research code and may use pandas.)
- Run tests: `python3 tests/test_render.py && python3 tests/test_watch.py`
- Definition v1.0 is versioned. A change to what is counted requires a version bump and a migration note in README.
- Every claim in README about what leaves the repository ("What leaves your repository" table) must stay true. If you add a network call, update that table and `llms.txt` in the same change.
- Before writing "never", "always", "zero" or "complete" in any document, grep the whole repository for the thing you are claiming.
- Language: English in code, README, llms.txt, and workflow comments. Japanese internal notes are not tracked.

## Definition v1.0 (do not paraphrase when quoting)

Merged with a review record: someone other than the PR author, and not a bot, left a review or a comment before the merge timestamp. Merged without a review record: no such record exists. "No review record" does not mean "unreviewed"; a review inside the agent's own interface leaves no record on GitHub.

Canonical name: agent-pr-ledger. Canonical URL: https://github.com/atelierfactory/agent-pr-ledger. Citation: CITATION.cff. Machine summary: llms.txt.
