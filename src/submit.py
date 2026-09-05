#!/usr/bin/env python3
"""Optional exchange: send your aggregate counts, get your position back.

Nothing is sent unless you pass --send. The default is a dry run that prints
the exact payload and stops.

What leaves your repository is numbers only. No code, no file names, no commit
messages, no author names, no email addresses, no tokens. The repository
identity is not in the payload at all — the server reads it from the GitHub
OIDC token, so we cannot receive a name you did not authorise GitHub to assert.
"""
from __future__ import annotations
import json, os, re, sys, urllib.request, urllib.error, urllib.parse
from collections import Counter

BASE = os.environ.get("LEDGER_BASE", "https://ledger.atelierfactory.jp")
ENDPOINT = os.environ.get("LEDGER_ENDPOINT", BASE + "/v1/submit")
PAYLOAD_VERSION = "1.0"

# This is every key we send. It mirrors the server's JSON Schema allowlist;
# anything absent here is rejected outright by the server, not silently ignored.
ALLOWED = {
    "payload_version", "definition_version", "tool_version",
    "scanned_prs", "agent_prs",
    "merged_with_review_record", "merged_without_review_record", "not_merged",
    "identity_type", "detection", "monthly", "size_bucket", "link",
}


def dominant_type(rows: list) -> tuple[str, dict]:
    """Decide the posting-identity type by the same rule the cohorts were built with.

    The type holding more than 50% wins; otherwise, mixed.
    Not 'only if there is a single type' — real repositories usually mix them,
    and that rule would send almost everyone to the combined cohort.
    """
    c = Counter(r["identity_type"] for r in rows)
    total = sum(c.values())
    if not total:
        return "none", {}
    top, k = c.most_common(1)[0]
    share = {t: round(v / total, 4) for t, v in c.items()}
    return (top if k / total > 0.5 else "mixed"), share


def size_bucket(n: int) -> str:
    for edge, name in ((10, "1-9"), (50, "10-49"), (200, "50-199"), (1000, "200-999")):
        if n < edge:
            return name
    return "1000+"


def build_payload(led: dict, tool_version: str, link: bool = False) -> dict:
    rows = led["rows"]
    c = Counter(r["outcome"] for r in rows)
    monthly = {}
    for r in rows:
        k = r["created_at"][:7]
        a, b = monthly.get(k, (0, 0))
        monthly[k] = (a + (r["outcome"] == "recorded"), b + (r["outcome"] == "unrecorded"))
    p = {
        "payload_version": PAYLOAD_VERSION,
        "definition_version": led["definition_version"],
        "tool_version": tool_version,
        "scanned_prs": led["scanned_prs"],
        "agent_prs": len(rows),
        "merged_with_review_record": c["recorded"],
        "merged_without_review_record": c["unrecorded"],
        "not_merged": c["not_merged"],
        "identity_type": dominant_type(rows)[0],
        "detection": led["coverage"],
        "monthly": [{"month": k, "with_record": v[0], "without_record": v[1]}
                    for k, v in sorted(monthly.items())],
        "size_bucket": size_bucket(len(rows)),
    }
    if link:
        p["link"] = True
    extra = set(p) - ALLOWED
    if extra:                       # self-check: never let our own mistake widen what we send
        raise RuntimeError(f"payload contains keys outside the allowlist: {sorted(extra)}")
    return p


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not follow redirects. Checking after the fact is too late:

    by then the Authorization header has already been sent. This is the same hole
    we fixed in ledger.py, repeated here.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = None


def _open(req, timeout=30):
    global _opener
    if _opener is None:
        _opener = urllib.request.build_opener(_NoRedirect())
    return _opener.open(req, timeout=timeout)


def oidc_token(audience: str = "agent-pr-ledger") -> str | None:
    """GitHub Actions OIDC token. Requires `id-token: write`."""
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    tok = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not (url and tok):
        return None
    req = urllib.request.Request(f"{url}&audience={urllib.parse.quote(audience)}",
                                 headers={"Authorization": f"Bearer {tok}"})
    with _open(req, 20) as r:
        return json.loads(r.read().decode()).get("value")


def send(payload: dict, token: str, endpoint: str = ENDPOINT) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "agent-pr-ledger",
    })
    with _open(req, 30) as r:          # do not follow redirects (refused up front)
        return json.loads(r.read().decode())


def fetch_cohorts(base: str = BASE) -> dict | None:
    """Fetch one cohort file. Only ever called when --preview is given.

    All cohorts ship in one file, so the URL is identical for every caller.
    Not one bit of caller-derived information rides on the request. A per-type URL
    would leak 'this repository is the human-authored type' in the path.
    Cohort selection happens locally, after the fetch.
    """
    url = f"{base}/v1/cohort/cohort_latest.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agent-pr-ledger"})
        with _open(req, 20) as r:      # redirects are refused before they are followed
            return json.loads(r.read().decode())
    except Exception:
        return None            # everything except the preview still works without it


def pick_cohort(bundle: dict, itype: str) -> dict | None:
    """Pick our own cohort locally, from the bundle we fetched."""
    if not bundle:
        return None
    c = bundle.get("cohorts", {})
    a = c.get(itype if itype in ("bot", "self") else "all")
    if a is None:
        return None
    return {**a, "cohort_version": bundle.get("cohort_version"),
            "build": bundle.get("build")}


def preview_from_cohort(payload: dict, coh: dict) -> dict:
    """Reconstruct, locally, the response a submission would return."""
    merged = payload["merged_with_review_record"] + payload["merged_without_review_record"]
    if not merged or not coh:
        return {}
    share = payload["merged_without_review_record"] / merged
    grid, aoa = coh.get("grid", []), coh.get("at_or_above", [])
    at = next((v for x, v in zip(grid, aoa) if x >= share - 1e-9), aoa[-1] if aoa else None)
    reg = coh.get("regimes", {})
    regime = "all_unrecorded" if share == 1 else "all_recorded" if share == 0 else "middle"
    tie = None
    if regime == "middle":
        mass = coh.get("mass") or []
        if mass and grid:
            i = min(range(len(grid)), key=lambda j: abs(grid[j] - share))
            tie = mass[i] if i < len(mass) else None
    return {"cohort_label": coh.get("cohort_label"), "cohort_n": coh.get("n"),
            "cohort_version": coh.get("cohort_version"), "regimes": reg, "regime": regime,
            "at_or_above": at, "tie_share": tie, "trend": coh.get("trend"),
            "trend_note": coh.get("trend_note"), "freshness": coh.get("freshness")}


def dry_run_text(payload: dict, endpoint: str = ENDPOINT, preview: bool = False) -> str:
    link = bool(payload.get("link"))
    L = ["─" * 68,
         "  DRY RUN — nothing left this runner." if not preview
         else "  PREVIEW — one public file was fetched; nothing about you was sent.",
         "",
         "  If you set `send: true` in your workflow, this JSON would be POSTed",
         f"  to {endpoint}:", "",
         json.dumps(payload, indent=2), "",
         "  Sent alongside it: a GitHub-signed OIDC token, used as the Bearer",
         "  credential. That token also carries the workflow context GitHub puts",
         "  in it — including the actor's username, the workflow path and the ref.",
         "  The server reads only `repository` from it, to check the request is real,",
         "  and does not store it. It also checks the repository is public; private ones",
         "  are refused. It is not a payload we choose; it is what GitHub signs.",
         "",
         "  Also unavoidable: your runner's IP address is visible to the network,",
         "  as with any HTTPS request. It is not logged (access logging on the",
         "  endpoint is off) but 'not logged' is not 'not seen'.",
         "",
         "  Never sent: code, diffs, file names, paths, commit messages, branch",
         "  names, PR titles or bodies, email addresses, free text of any kind.",
         "",
         ("  What happens to it: the numbers are stored under a pseudonymous identifier"
          if link else
          "  What happens to it: the numbers join an aggregate as an anonymous point."),

         ("  that connects this repository's submissions over time and across aTELiER"
          if link else
          "  Your repository name is NOT stored. It is used to check that the token is"),
         ("  FACTORY services. The identifier is derived from your repository name with a"
          if link else
          "  genuine, and then discarded. Only aggregates are ever published, so there"),
         ("  key we hold; the name itself is not stored and no table maps one to the other."
          if link else
          "  is no page anywhere carrying your repository's name and these figures."),
         ("  Honest limit: whoever holds that key can compute the identifier for a"
          if link else ""),
         ("  repository name they already suspect. What protects the mapping is the key,"
          if link else ""),
         ("  kept in AWS KMS and never exported — not the mathematics. Remove `link` and"
          if link else ""),
         ("  later submissions are no longer connected."
          if link else ""),
         "" if link else "",
         ("  Without `link`, no identifier connects submissions from different months:"
          if not link else ""),
         ("  the de-duplication key rotates monthly, by design. The stored point itself"
          if not link else ""),
         ("  (month, type, size bucket, counts) is coarse — but we will not claim that"
          if not link else ""),
         ("  unusual values could never be guessed to match across months."
          if not link else ""),
         "",
         "  Your own copy is this workflow log. It sits in your repository's Actions",
         "  history, next to the `send: true` line that authorised it.",
         "─" * 68]
    out, prev_blank = [], False
    for l in L:                       # 分岐で生じた空行の連続を畳む
        blank = (l.strip() == "")
        if not (blank and prev_blank):
            out.append(l)
        prev_blank = blank
    return "\n".join(out)


def dry_run_note(lang: str = "en") -> list[str]:
    if lang == "ja":
        return ["", "  ↑ これは送信した場合に返るものの下見です。まだ何も送っていません。",
                "    （公開されている母集団ファイルを取得しただけで、あなたに関する情報は送っていません）",
                "    送るには、ワークフローに send: true を書き足してください。"]
    return ["", "  ↑ Preview of what you would get back. Nothing has been sent.",
            "    (This fetched the public cohort file only; nothing about you left this runner.)",
            "    To send, add `send: true` to your workflow."]


def position_text(resp: dict, lang: str = "en") -> list[str]:
    """What you get back for submitting: four parts.

    Rank is not the headline. The population is bimodal, with 60% at the extremes,
    so a rank is empty information for most callers. What regime they are in
    leads instead; rank is a footnote for the middle band.

    Callers must place this after the unrecorded-share line, so it cannot read as absolution.
    """
    if not resp:
        return []
    # Strings we receive end up in our output (the job summary's Markdown).
    # The server validates them too; this closes the path if that host is ever compromised.
    safe = re.compile(r"[A-Za-z0-9 ,.:/_()\-]{0,400}")

    def clean(v):
        if isinstance(v, str):
            return v if safe.fullmatch(v) else ""
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        return v

    resp = clean(resp)
    ja = lang == "ja"
    bul = "  ・" if ja else "  - "          # 記号も言語ごとに。英語出力に和文約物を混ぜない
    col = "：" if ja else ": "
    ob, cb, sl = ("（", "）", "／") if ja else (" (", ")", " / ")
    coh = resp.get("cohort_label", "all repositories")
    n, ver = resp.get("cohort_n", "?"), resp.get("cohort_version", "?")
    L = ["", ("  同じ届き方をするリポジトリの中での文脈" if ja
              else "  Context among repositories where agent PRs arrive the same way")]

    # 1. 1. which regime
    reg = resp.get("regimes") or {}
    mine = resp.get("regime")
    if reg and mine:
        if mine == "all_unrecorded":
            L.append(bul + f"{'あなたと同じく、マージがすべて審査記録なしのリポジトリ' if ja else 'Like yours, repositories where every merge lacks a review record'}" + col + f"{reg.get('all_unrecorded',0)*100:.0f}%")
            L.append(bul + f"{'一つでも記録があるリポジトリ' if ja else 'Repositories with at least one record'}"
                     + col + f"{reg.get('some_record',0)*100:.0f}%")
        elif mine == "all_recorded":
            L.append(bul + f"{'あなたと同じく、すべてのマージに記録があるリポジトリ' if ja else 'Like yours, repositories where every merge has a record'}"
                     + col + f"{reg.get('all_recorded',0)*100:.0f}%")
        else:
            a = resp.get("at_or_above")
            if a is not None:
                L.append(bul + f"{'あなたと同じかそれ以上に記録なしの割合が高いリポジトリ' if ja else 'Repositories at or above your share of unrecorded merges'}"
                         + col + f"{a*100:.0f}%")

    # 2. 2. ties, stated plainly
    tie = resp.get("tie_share")
    if tie and tie >= 0.05 and mine == "middle":
        L.append(bul + f"{'ちょうど同じ値のリポジトリ' if ja else 'Repositories at exactly your value'}" + col + f"{tie*100:.0f}%"
                 f"（{'分布が二峰性なので、順位はあまり意味を持ちません' if ja else 'bimodal distribution — rank carries little information'}）")

    # 3. 3. how the cohort is moving
    tr = resp.get("trend") or []
    if len(tr) >= 2:
        a0, a1 = tr[0], tr[-1]
        L.append(bul + f"{'この母集団の記録なし率' if ja else 'Unrecorded share across this cohort'}" + col + f"{a0['month']} {a0['without_record']*100:.0f}% → {a1['month']} {a1['without_record']*100:.0f}%")
    elif resp.get("trend_note"):
        L.append(bul + f"{'推移は構成効果のため非公開（型をまたぐ構成が動いているため）' if ja else 'Trend withheld for this cohort: the movement is a composition shift'}")

    # 4. your own receipt — this run's log, in your repository
    if resp.get("stored"):
        L.append(bul + ("送信は無名の集計データ点になりました。リポジトリ名は保存されていません" if ja
                        else "Your numbers joined the aggregate as an anonymous point; "
                             "your repository name was not stored"))
        L.append(bul + ("控えはこの実行ログです（あなたのリポジトリのActions履歴に残ります）" if ja
                        else "Your receipt is this workflow log, in your own repository's "
                             "Actions history"))

    if not resp.get("stored", {}).get("linked"):
        L.append("")
        L.append("  " + ("`link` を有効にすると、以後の送信がパネルになります。「リポジトリを直すと"
                        "本当に効くのか」に答えられるのはこの形のデータだけで、公開データでは答えが"
                        "出ませんでした。" if ja else
                        "If you enable `link`, your future submissions form a panel — the kind of "
                        "data that can answer whether changing a repository actually helps. Public "
                        "data could not answer that question. Linked submissions are how the answer "
                        "gets built."))
    sep = "・" if ja else ", "
    L.append(f" {ob}{coh}{sep}n={n}{sep}{'母集団の版' if ja else 'cohort version'} {ver}"
             f"{sl}{'記述統計であり、良し悪しの判定ではありません' if ja else 'descriptive only, not a judgement'}{cb}")
    if resp.get("freshness"):
        L.append(f" {ob}{resp['freshness']}{cb}")
    return L
