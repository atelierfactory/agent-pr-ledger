# agent-pr-ledger

**A ledger of agent-authored pull requests. It counts; it does not score.**

Counts, for one GitHub repository, how many pull requests opened by coding agents (GitHub Copilot, Devin, OpenAI Codex, Cursor, Claude Code, Google Jules) were merged **with a human review record** and how many **without** (definition v1.0). Read-only. Python standard library only. Contacts nothing but `api.github.com` unless you opt in.

```
pip install agent-pr-ledger
agent-pr-ledger OWNER/REPO 300            # ledger for the most recent 300 PRs
agent-pr-watch OWNER/REPO 1234            # one pull request
agent-pr-ledger-mcp                       # MCP server on stdio (tools: agent_pr_ledger, agent_pr_watch)
```

**Definition v1.0.** Merged with a review record: someone other than the PR author, and not a bot, left a review or a comment before the merge timestamp. Merged without a review record: no such record exists. "No review record" does not mean "unreviewed": a review inside the agent's own interface leaves no record on GitHub.

As a GitHub Action: `uses: atelierfactory/agent-pr-ledger@v0.1`.

Repository and full README: https://github.com/atelierfactory/agent-pr-ledger — machine summary: `llms.txt` — citation: `CITATION.cff`.

mcp-name: io.github.atelierfactory/agent-pr-ledger
