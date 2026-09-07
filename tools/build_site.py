#!/usr/bin/env python3
"""Build the findings pages of the Pages site (site/findings/...) from one source of truth.

Every page carries the canonical name, definition v1.0, schema.org Article markup and a
link back to the repository, so that each finding is a separate, quotable, indexable page.

  python3 tools/build_site.py      # writes site/findings/*/index.html and site/sitemap.xml
"""
from __future__ import annotations
import html, json, os, datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = "https://atelierfactory.github.io/agent-pr-ledger"
REPO = "https://github.com/atelierfactory/agent-pr-ledger"
TODAY = datetime.date.today().isoformat()

DEFINITION = ("<p><strong>Definition v1.0 (agent-pr-ledger).</strong> A merged pull request carries a "
              "<em>review record</em> if someone other than the PR author, and not a bot, left a review or a "
              "comment before the merge timestamp. \"No review record\" does not mean \"unreviewed\": a review "
              "inside the agent's own interface leaves no record on GitHub. The tool counts whether an auditable "
              "record exists.</p>")

CSS = """body{margin:0;background:#fff;color:#1a1a1a;font:16px/1.6 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}
main{max-width:46rem;margin:0 auto;padding:2.5rem 1.25rem}nav{font-size:.9rem;color:#666}
h1{font-size:1.6rem;margin:.5rem 0 .25rem}h2{font-size:1.15rem;margin:1.75rem 0 .5rem}
p.lead{font-size:1.05rem}table{border-collapse:collapse;width:100%;margin:.5rem 0}
td,th{border-bottom:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}
a{color:#0b57d0}footer{margin-top:2.5rem;color:#666;font-size:.9rem}aside{border-left:3px solid #ccc;padding:.25rem .75rem;color:#444;margin:1rem 0}
@media (prefers-color-scheme:dark){body{background:#111;color:#e8e8e8}td,th{border-color:#333}a{color:#8ab4f8}footer,nav{color:#999}aside{color:#bbb;border-color:#444}}"""

SCOPE = ("<aside>Data: AIDev (Hugging Face <code>hao-li/AIDev</code>), curated subset of 33,596 agent-authored pull "
         "requests, 2024-12 to 2025-07, five agents. Figures are as computed on that snapshot; the dataset has "
         "since grown. Full write-up: forthcoming.</aside>")

FINDINGS = [
    {
        "slug": "merge-rate-measures-conventions",
        "title": "Merge rate measures who presses the button, not agent quality",
        "summary": "Median time to merge is 50 seconds for OpenAI Codex and 17.7 hours for GitHub Copilot. The difference is posting identity, not quality.",
        "body": """
<p class="lead">The metric most often used to compare coding agents, the share of their pull requests that get merged, is dominated by a convention: whether the agent posts under the developer's own account or under a bot account.</p>
<table><tr><th>Agent</th><th>Median time to merge</th><th>Share reaching a human review</th><th>Posts as</th></tr>
<tr><td>OpenAI Codex</td><td>50 seconds</td><td>5.4%</td><td>developer's own account</td></tr>
<tr><td>Cursor</td><td>0.6 h</td><td>25.5%</td><td>developer's own account</td></tr>
<tr><td>Claude Code</td><td>1.5 h</td><td>24.6%</td><td>developer's own account</td></tr>
<tr><td>Devin</td><td>2.3 h</td><td>36.9%</td><td>one bot account</td></tr>
<tr><td>GitHub Copilot</td><td>17.7 h</td><td>51.2%</td><td>one bot account</td></tr></table>
<p>A Codex PR is the developer's own work: reviewed, if at all, inside Codex, then merged by the same person within a minute. A Copilot PR is an external contribution, merged by a maintainer after a median of 17.7 hours. The two "merges" are different events. Comparing their rates compares two social positions.</p>
<p>Agent composition alone explains 41.5% of between-repository variance in merge rate. A metric that agent choice explains that much of cannot be used to compare repositories either.</p>
""",
    },
    {
        "slug": "rework-rate-measures-commit-conventions",
        "title": "Rework rate measures commit conventions",
        "summary": "The share of PRs with two or more commits is 0.132 for Codex and 0.899 for Copilot. Agent mix explains 76% of between-repository variance.",
        "body": """
<p class="lead">"Rework" is often measured as the share of pull requests that needed more than one commit. Codex produces one commit per PR by design (mean 1.49); Copilot averages 4.79. The metric measures that design choice.</p>
<p>Regressing each repository's rework rate on its agent mix alone gives R² = 0.762. Three-quarters of what looks like repository-level variation is which agent the repository uses.</p>
<p>We measured this contamination for six candidate outcomes (R² on agent composition; lower is better):</p>
<table><tr><th>Outcome</th><th>R² on agent mix</th></tr>
<tr><td>Change-request rate, human-touched PRs only</td><td>0.126</td></tr>
<tr><td>Change-request rate, all PRs</td><td>0.265</td></tr>
<tr><td>Approval rate</td><td>0.390</td></tr>
<tr><td>Merge rate</td><td>0.415</td></tr>
<tr><td>Human-touched share</td><td>0.551</td></tr>
<tr><td>Rework rate</td><td>0.762</td></tr></table>
<p>Rule we adopted: before using any outcome, check how much of it agent composition already explains. If the answer is most of it, the metric is measuring the agents' habits.</p>
""",
    },
    {
        "slug": "threshold-free-self-merge-still-breaks",
        "title": "A threshold-free self-merge definition still breaks",
        "summary": "'Merger ≠ author' gives self-merge rates of 0.98 for Codex and 0.00 for Copilot, because one posts as the user and the other as a bot.",
        "body": """
<p class="lead">"The merger is not the author" needs no threshold and looks structurally clean. It measures posting identity.</p>
<table><tr><th>Agent</th><th>Self-merge rate (merger = author)</th><th>Unique author accounts</th></tr>
<tr><td>OpenAI Codex</td><td>0.980</td><td>826</td></tr>
<tr><td>Cursor</td><td>0.912</td><td>233</td></tr>
<tr><td>Claude Code</td><td>0.837</td><td>122</td></tr>
<tr><td>Devin</td><td>0.001</td><td>1</td></tr>
<tr><td>GitHub Copilot</td><td>0.000</td><td>1</td></tr></table>
<p>Copilot and Devin each post from a single bot account, so the merger is always someone else. Codex, Cursor and Claude Code post from the developer's account, so the merger is almost always the author. Nothing about review has been measured.</p>
<p>The absence of a threshold does not imply the absence of contamination. This is why agent-pr-ledger's definition asks a different question: not <em>who merged</em>, but whether <em>anyone other than the author left a record before the merge</em>.</p>
""" + DEFINITION,
    },
    {
        "slug": "definition-v1-review-record",
        "title": "Definition v1.0: a review record, not a review",
        "summary": "agent-pr-ledger counts whether an auditable record of review exists before the merge. It does not claim to know whether anyone looked.",
        "body": DEFINITION + """
<h2>Two choices that matter</h2>
<p><strong>The author is excluded.</strong> An instruction a developer leaves for the agent on their own PR is not third-party review. Counting it moves the share of repositories with no records at all from 36.0% to 27.4% at the 10-PR cut-off; the stricter definition is the one we ship.</p>
<p><strong>Only records before the merge count.</strong> Ignoring the timestamp lets post-merge comments leak into the "reviewed" side: the recorded share rises from 0.212 to 0.257.</p>
<h2>What it is not</h2>
<p>It is not a quality judgement. One comment from any third party is enough for a record, and a record says nothing about how careful the review was. It is an audit trail: the governance question is not whether someone looked, but whether looking left a trace in the repository's own history.</p>
<p>Inline review comments always hang off a review, so counting them changes no classification (zero PRs moved when we added AIDev's 26,868 review comments). The tool counts them anyway, for robustness.</p>
<p>Definitions are versioned. A change ships with a version bump and a migration note.</p>
""",
    },
    {
        "slug": "posting-identity-not-brand",
        "title": "The dividing line is posting identity, not agent brand",
        "summary": "1.7% of repositories where agent PRs arrive under a bot account have no review records at all. 63.3% of repositories where they arrive under the developer's own account do.",
        "body": """
<p class="lead">Among 490 public repositories with at least five merged agent PRs, 41.6% merged every agent PR without a review record. What separates them is not which agent they use.</p>
<table><tr><th>Cut-off (merged agent PRs)</th><th>Repositories</th><th>Median recorded share</th><th>No records at all</th></tr>
<tr><td>≥ 3</td><td>762</td><td>0.250</td><td>41.9%</td></tr>
<tr><td>≥ 5</td><td>490</td><td>0.190</td><td>41.6%</td></tr>
<tr><td>≥ 10</td><td>252</td><td>0.165</td><td>38.1%</td></tr>
<tr><td>≥ 20</td><td>130</td><td>0.087</td><td>38.5%</td></tr>
<tr><td>≥ 30</td><td>86</td><td>0.073</td><td>36.0%</td></tr></table>
<p>Assigning each repository to the identity type that accounts for more than half of its merged agent PRs (n = 490):</p>
<table><tr><th>Identity type</th><th>Repositories</th><th>Median unrecorded share</th><th>No records at all</th></tr>
<tr><td>Bot account (external contribution: Copilot, Devin)</td><td>173</td><td>0.078</td><td>1.7%</td></tr>
<tr><td>Developer's own account (own work: Codex, Cursor, Claude Code)</td><td>316</td><td>1.000</td><td>63.3%</td></tr></table>
<p>When agent PRs arrive as external contributions, a review record almost always exists. When they arrive as the developer's own work, two-thirds of repositories have none. Identity type explains 48.2% of between-repository variance (PR-weighted), 88% of what brand explains. Brand is a proxy for identity type.</p>
<p>This is why agent-pr-ledger never compares agents and always reports the identity type of the repository it is looking at.</p>
""",
    },
    {
        "slug": "same-event-two-stories",
        "title": "The same event, two opposite stories",
        "summary": "After repositories adopt an agent instruction file, merge rate falls 16 points. Decomposed, the whole fall is the disappearance of unrecorded merges; recorded merges do not move.",
        "body": """
<p class="lead">221 repositories adopted an agent instruction file (AGENTS.md, CLAUDE.md and similar) during the window; 155 never did. Repository fixed effects, agent × calendar-month fixed effects, standard errors clustered by repository, relative-month dummies with the month before adoption as reference.</p>
<table><tr><th>Relative month</th><th>−4</th><th>−3</th><th>−2</th><th>0</th><th>+1</th><th>+2</th><th>+3</th></tr>
<tr><td>Merge rate (common metric)</td><td>+0.023</td><td>−0.006</td><td>−0.022</td><td><b>−0.119</b></td><td><b>−0.165</b></td><td><b>−0.163</b></td><td>−0.162</td></tr>
<tr><td>Merged <b>without</b> review record</td><td>−0.012</td><td>−0.026</td><td>−0.020</td><td><b>−0.115</b></td><td><b>−0.159</b></td><td><b>−0.176</b></td><td><b>−0.235</b></td></tr>
<tr><td>Merged <b>with</b> review record</td><td>+0.035</td><td>+0.020</td><td>−0.002</td><td>−0.004</td><td>−0.006</td><td>+0.013</td><td>+0.073</td></tr></table>
<p>Bold: p &lt; 0.05. Pre-adoption coefficients are zero for all three outcomes (parallel trends hold for these three; not for rework rate, on which we make no causal claim).</p>
<p><strong>Under merge rate:</strong> adoption is followed by a persistent 16-point decline. Read naively, instruction files made agents worse.</p>
<p><strong>Under the decomposition:</strong> the decline is entirely the disappearance of merges without a review record, deepening from −0.115 to −0.235, while merges with a review record do not move in any period (p &gt; 0.28). The team began to manage agent intake. In the adoption month, CI configuration files are also added at 3.5 times the usual pace, and change-request rate rises in the month <em>before</em> adoption: files are added in response to friction, not ahead of it.</p>
<p>Same data, same months, same repositories. The definition decides which story you tell. This is the reason agent-pr-ledger exists.</p>
""" + DEFINITION,
    },
    {
        "slug": "readiness-scores-null-result",
        "title": "Repository 'AI-readiness' scores mostly restate size, language and agent choice",
        "summary": "24 structural features, harvested by rewinding each repository to the day before its first agent PR, add +0.005 to +0.024 AUC over what agent, task, size and language already give.",
        "body": """
<p class="lead">At least eight free tools and several commercial products score repositories on structure (instruction files, README, CI, tests). None publishes a validation against agent outcomes. We ran one.</p>
<p><strong>Method.</strong> For each of 404 repositories, rewind to the commit on the day before its first agent PR (<code>git clone --filter=tree:0 --no-checkout</code>, then checkout by date) and harvest 24 features. Using the current state would count files added <em>after</em> the PRs as causes. Outcome: change-request rate on human-touched PRs, the least agent-contaminated candidate (split-half reliability 0.798; binomial noise only 15% of variance, so the outcome is not the problem).</p>
<table><tr><th>Controls</th><th>Controls only (AUC)</th><th>+ repository features</th><th>Increment</th><th>Placebo</th><th>Real − placebo</th><th>p</th></tr>
<tr><td>Agent</td><td>0.638</td><td>0.651</td><td>+0.012</td><td>0.601</td><td>+0.050</td><td>0.005</td></tr>
<tr><td>+ size, language</td><td>0.628</td><td>0.639</td><td>+0.010</td><td>0.590</td><td>+0.048</td><td>0.004</td></tr>
<tr><td>+ task type</td><td>0.639</td><td>0.644</td><td>+0.005</td><td>0.597</td><td>+0.047</td><td>0.003</td></tr></table>
<p>Leave-repository-out cross-validation, eight fold seeds, placebo by permuting whole feature vectors across repositories. Two readings, both correct: repository features carry real information (+0.05 over placebo, stable), and the increment over free information is +0.005 to +0.024 depending on specification. A PR-level model with 24 features is jointly significant, but one feature survives false-discovery control, and it rests on a handful of repositories.</p>
<p>A score built from these features is mostly a restatement of size, language and agent choice. That is why agent-pr-ledger does not score.</p>
""",
    },
    {
        "slug": "detection-accuracy",
        "title": "How well the tool identifies agent PRs (measured 2026-09-06)",
        "summary": "355 of 355 AIDev-labelled agent PRs across six agents identified; 9 of 157 unlabelled PRs from the same repositories flagged, an upper bound of 5.7% that is mostly unlabelled Codex PRs.",
        "body": """
<p class="lead">agent-pr-ledger identifies agent PRs by three signals, in order: author account (certain), branch prefix (inferred), body signature (inferred). The output always states which one was used. We measured the rules against AIDev labels.</p>
<table><tr><th>Agent (AIDev label)</th><th>Sampled</th><th>Identified</th><th>Name matched</th><th>Signal</th></tr>
<tr><td>GitHub Copilot</td><td>60</td><td>60</td><td>60</td><td>author</td></tr>
<tr><td>Devin</td><td>60</td><td>60</td><td>60</td><td>author</td></tr>
<tr><td>Google Jules</td><td>59</td><td>59</td><td>59</td><td>author (after fix)</td></tr>
<tr><td>OpenAI Codex</td><td>60</td><td>60</td><td>60</td><td>branch</td></tr>
<tr><td>Cursor</td><td>59</td><td>59</td><td>59</td><td>branch</td></tr>
<tr><td>Claude Code</td><td>57</td><td>57</td><td>57</td><td>branch / body</td></tr></table>
<p>One PR per repository per agent, so no single account dominates. Before the fix, Jules scored 0 of 59: its bot account was missing from the name table. The fix is one line; the lesson is that a rule marked "certain" must be exercised against every agent it claims to cover.</p>
<p><strong>False positives.</strong> Of 157 PRs from the same repositories, inside AIDev's window, that AIDev does not label, 9 were flagged as agent-authored: an upper bound of 5.7%. Eight of the nine carry <code>codex/</code> branch names and are more plausibly agent PRs the dataset missed than human coincidences; one is a human PR with a Claude co-author trailer (0.6%). AIDev labels presence, not absence, so the figure is an upper bound.</p>
<p>Script: <a href="""" + REPO + """/blob/main/tools/validate_detection.py">tools/validate_detection.py</a>.</p>
""",
    },
]


def page(f: dict) -> str:
    url = f"{SITE}/findings/{f['slug']}/"
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f["title"],
        "description": f["summary"],
        "url": url,
        "datePublished": "2026-09-08",
        "dateModified": TODAY,
        "author": {"@type": "Organization", "name": "aTELiER FACTORY", "url": "https://atelierfactory.jp"},
        "publisher": {"@type": "Organization", "name": "aTELiER FACTORY"},
        "isPartOf": {"@type": "WebSite", "name": "agent-pr-ledger", "url": SITE + "/"},
        "about": {"@type": "SoftwareSourceCode", "name": "agent-pr-ledger", "codeRepository": REPO},
        "keywords": ["coding agents", "pull requests", "code review", "agent-pr-ledger", "definition v1.0"],
    }
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(f['title'])} — agent-pr-ledger</title>
<meta name="description" content="{html.escape(f['summary'])}">
<link rel="canonical" href="{url}"><meta name="robots" content="index, follow, max-snippet:-1">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style></head>
<body><main>
<nav><a href="../../">agent-pr-ledger</a> · <a href="../">findings</a></nav>
<h1>{html.escape(f['title'])}</h1>
<p><em>{html.escape(f['summary'])}</em></p>
{f['body']}
{SCOPE}
<footer>agent-pr-ledger — a ledger of agent-authored pull requests. It counts; it does not score. <a href="{REPO}">Repository</a> · <a href="{SITE}/llms.txt">llms.txt</a> · <a href="{REPO}/blob/main/CITATION.cff">Cite</a></footer>
</main></body></html>
"""


def index() -> str:
    items = "\n".join(f'<li><a href="{f["slug"]}/">{html.escape(f["title"])}</a><br><span>{html.escape(f["summary"])}</span></li>' for f in FINDINGS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Findings — agent-pr-ledger</title>
<meta name="description" content="What 33,596 agent-authored pull requests show about the metrics used to evaluate coding agents, and the definition agent-pr-ledger uses instead.">
<link rel="canonical" href="{SITE}/findings/"><meta name="robots" content="index, follow, max-snippet:-1">
<style>{CSS} li{{margin:.75rem 0}} li span{{color:#555}}</style></head>
<body><main>
<nav><a href="../">agent-pr-ledger</a></nav>
<h1>Findings</h1>
<p class="lead">What 33,596 agent-authored pull requests show about the metrics commonly used to evaluate coding agents, and the definition agent-pr-ledger uses instead. One finding per page.</p>
<ul>{items}</ul>
{DEFINITION}
<footer>agent-pr-ledger — a ledger of agent-authored pull requests. It counts; it does not score. <a href="{REPO}">Repository</a> · <a href="{SITE}/llms.txt">llms.txt</a></footer>
</main></body></html>
"""


def sitemap() -> str:
    urls = [f"{SITE}/", f"{SITE}/llms.txt", f"{SITE}/findings/"] + [f"{SITE}/findings/{f['slug']}/" for f in FINDINGS]
    body = "\n".join(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def main():
    for f in FINDINGS:
        d = os.path.join(ROOT, "site", "findings", f["slug"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(page(f))
    open(os.path.join(ROOT, "site", "findings", "index.html"), "w").write(index())
    open(os.path.join(ROOT, "site", "sitemap.xml"), "w").write(sitemap())
    print(f"built {len(FINDINGS)} findings pages + index + sitemap")
    print("\n".join(f"{SITE}/findings/{f['slug']}/" for f in FINDINGS))


if __name__ == "__main__":
    main()
