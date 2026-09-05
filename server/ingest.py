#!/usr/bin/env python3
"""ingest Lambda — the only write path.

Does four things and nothing else:
  1. verify the GitHub OIDC token (identity comes from GitHub, not from the payload)
  2. validate the payload against schema.json as an allowlist (unknown key -> reject)
  3. look up the caller's position in a pre-computed cohort file (binary search, no scan)
  4. append the numbers as an ANONYMOUS data point, and return the context

**No repository name is ever stored.** The token proves which repository is
speaking, and that fact is used and discarded. What lands in storage is a row of
counts with no owner. For de-duplication we keep a keyed hash of the repository
name — HMAC with a server-side secret — which cannot be reversed or looked up
without that secret, and which never appears in anything we publish.

The consequence is the strongest form of the guarantee: what we do not keep
cannot leak, and cannot be turned into a list of repositories worth attacking.
Everything we do keep becomes part of a published aggregate.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, re, time, urllib.request
from datetime import datetime, timezone

BUCKET = os.environ.get("RECORD_BUCKET", "")
COHORT_PREFIX = "v1/cohort/"
POINTS_PREFIX = "internal/points/"     # anonymous points; only aggregates are published
LINKED_PREFIX = "internal/linked/"     # opted-in points, keyed by AF-ID
SALT_PARAM = os.environ.get("SALT_PARAM_PREFIX", "/ledger/dedup-salt/")
MASTER_KEY_ID = os.environ.get("AF_ID_KEY_ID", "")  # KMS key; never leaves KMS


def month_salt(ssm, month: str) -> str:
    """The salt for this month, created on first use and deleted on the 2nd of the next.

    A rotating salt only means something if the old one is gone. A scheduled job
    runs at 04:00 UTC on the 2nd and deletes every salt but the current month's;
    after that the previous month's keys cannot be recomputed by anyone, ourselves
    included. That deletion is the mechanism; rotation alone would be a promise.

    While a month's salt is alive we could still match a repository name we already
    suspect, by hashing it and looking for the key. The salt is required for
    de-duplication, so that ability cannot be designed away — only disclosed.
    """
    name = SALT_PARAM + month
    try:
        return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        value = base64.b64encode(os.urandom(32)).decode()
        try:
            ssm.put_parameter(Name=name, Value=value, Type="SecureString", Overwrite=False)
            return value
        except Exception:                       # 競合したら勝った側の値を読む
            return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


def dedup_key(salt: str, full: str) -> str:
    """De-duplication only, for submissions that did NOT opt into linking.

    The salt is this month's, and last month's is deleted. Two submissions from
    the same repository in different months therefore produce keys that nobody
    can relate — not because we decline to, but because the material is gone.

    That is a statement about identifiers, not about inference: the point itself
    carries month, type, size bucket and counts, and an unusual set of values
    could still be guessed to match across months. We close the identifier path
    and say plainly that we have not closed the other one.
    """
    return hmac.new(salt.encode(), full.encode(), hashlib.sha256).hexdigest()[:32]


def af_id(kms, namespace: str, value: str) -> str:
    """The cross-service pseudonym, for submissions that opted in.

    Derived deterministically, so the same repository lands on the same
    identifier years later and in any other aTELiER FACTORY service. No table of
    names to identifiers exists: it is recomputed each time the subject returns.

    Honest limit: this is a keyed pseudonym, not an unlinkable one. Whoever holds
    the master key can compute the identifier for a repository name they already
    suspect, and repository names are public and enumerable. What protects the
    mapping is the key, held in KMS and never exported — not the mathematics.
    """
    mac = kms.generate_mac(KeyId=MASTER_KEY_ID, MacAlgorithm="HMAC_SHA_256",
                           Message=f"{namespace}:{value}".encode())["Mac"]
    return mac.hex()[:32]
GITHUB_JWKS = "https://token.actions.githubusercontent.com/.well-known/jwks"
AUDIENCE = "agent-pr-ledger"
MAX_BODY = 64 * 1024

_schema = None
_jwks = {"fetched": 0, "keys": []}


def schema():
    global _schema
    if _schema is None:
        with open(os.path.join(os.path.dirname(__file__), "schema.json")) as f:
            _schema = json.load(f)
    return _schema


# ---- 2. allowlist validation (an unknown key rejects the request; it is never ignored)----------
def validate(obj, sch, path="") -> list[str]:
    err = []
    t = sch.get("type")
    if "const" in sch and obj != sch["const"]:
        return [f"{path or 'value'}: must be {sch['const']!r}"]
    if "enum" in sch and obj not in sch["enum"]:
        return [f"{path or 'value'}: must be one of {sch['enum']}"]
    if t == "object":
        if not isinstance(obj, dict):
            return [f"{path or 'value'}: expected object"]
        props = sch.get("properties", {})
        if sch.get("additionalProperties") is False:
            for k in obj:
                if k not in props:
                    err.append(f"{path}{k}: not accepted by this service")
        for k in sch.get("required", []):
            if k not in obj:
                err.append(f"{path}{k}: required")
        for k, v in obj.items():
            if k in props:
                err += validate(v, props[k], f"{path}{k}.")
    elif t == "array":
        if not isinstance(obj, list):
            return [f"{path}: expected array"]
        if len(obj) > sch.get("maxItems", 10 ** 9):
            err.append(f"{path}: too many items")
        for i, v in enumerate(obj):
            err += validate(v, sch.get("items", {}), f"{path}{i}.")
    elif t == "integer":
        if not isinstance(obj, int) or isinstance(obj, bool):
            return [f"{path[:-1]}: expected integer"]
        if "minimum" in sch and obj < sch["minimum"]:
            err.append(f"{path[:-1]}: below minimum")
        if "maximum" in sch and obj > sch["maximum"]:
            err.append(f"{path[:-1]}: above maximum")
    elif t == "string":
        if not isinstance(obj, str):
            return [f"{path[:-1]}: expected string"]
        if len(obj) > sch.get("maxLength", 10 ** 9):
            err.append(f"{path[:-1]}: too long")
        if "pattern" in sch and not re.fullmatch(sch["pattern"], obj):
            err.append(f"{path[:-1]}: does not match the accepted format")
    return err


# ---- 1. OIDC verification --------------------------------------------------
def b64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwks():
    if time.time() - _jwks["fetched"] > 3600:
        with urllib.request.urlopen(GITHUB_JWKS, timeout=10) as r:
            _jwks["keys"] = json.loads(r.read().decode())["keys"]
            _jwks["fetched"] = time.time()
    return _jwks["keys"]


# SHA-256 DigestInfo (DER): the fixed prefix inside a PKCS#1 v1.5 signature block.
SHA256_DER = bytes.fromhex("3031300d060960864801650304020105000420")


def rs256_verify(n: int, e: int, sig: bytes, msg: bytes) -> bool:
    """Verify RS256 using only the standard library.

    Public-key verification handles no secret, so there is no secret to leak by timing.
    It removes the dependency entirely: nothing to add to the Lambda runtime,
    and 'no crypto dependency on the server either' becomes something we can state.
    """
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return False
    em = pow(int.from_bytes(sig, "big"), e, n).to_bytes(k, "big")
    expected = b"\x00\x01" + b"\xff" * (k - 3 - len(SHA256_DER) - 32) + b"\x00" \
               + SHA256_DER + hashlib.sha256(msg).digest()
    return hmac_compare(em, expected)


def hmac_compare(a: bytes, b: bytes) -> bool:
    import hmac as _h
    return _h.compare_digest(a, b)


def verify_oidc(token: str) -> dict:
    """Verify signature, issuer, audience and expiry, then return the claims.

    This is the only source of identity. The payload carries no repository name so that
    there is no path where we trust a name the sender asserts.
    """
    h, p, s = token.split(".")
    head = json.loads(b64u(h)); claims = json.loads(b64u(p))
    key = next((k for k in jwks() if k["kid"] == head.get("kid")), None)
    if not key:
        raise ValueError("unknown signing key")
    if head.get("alg") != "RS256":
        raise ValueError("unexpected algorithm")
    n = int.from_bytes(b64u(key["n"]), "big"); e = int.from_bytes(b64u(key["e"]), "big")
    if not rs256_verify(n, e, b64u(s), f"{h}.{p}".encode()):
        raise ValueError("bad signature")
    if claims.get("iss") != "https://token.actions.githubusercontent.com":
        raise ValueError("unexpected issuer")
    if claims.get("aud") != AUDIENCE:
        raise ValueError("unexpected audience")
    now = time.time()
    if claims.get("exp", 0) < now:
        raise ValueError("token expired")
    if claims.get("nbf", 0) > now + 60:
        raise ValueError("token not yet valid")
    if claims.get("repository_visibility") != "public":
        raise ValueError("only public repositories are accepted")
    return claims


# ---- 3. cohort lookup (binary search, never a scan)-------------------------------
def lookup(s3, cohort: str, share: float) -> dict:
    # One canonical file. We read exactly what the client fetches
    # (reading a different file would let preview and send disagree).
    bundle = json.loads(s3.get_object(
        Bucket=BUCKET, Key=f"{COHORT_PREFIX}cohort_latest.json")["Body"].read())
    coh = bundle["cohorts"][cohort if cohort in bundle["cohorts"] else "all"]
    coh = {**coh, "cohort": cohort, "cohort_version": bundle.get("cohort_version"),
           "build": bundle.get("build")}
    grid, aoa = coh["grid"], coh["at_or_above"]
    lo, hi = 0, len(grid) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if grid[mid] < share - 1e-9:
            lo = mid + 1
        else:
            hi = mid
    reg = coh.get("regimes", {})
    regime = "all_unrecorded" if share >= 1 else "all_recorded" if share <= 0 else "middle"
    return {"cohort": coh["cohort"], "cohort_label": coh.get("cohort_label", ""),
            "cohort_n": coh["n"], "cohort_version": coh["cohort_version"],
            "build": coh.get("build"), "regimes": reg, "regime": regime,
            "at_or_above": aoa[lo],
            "tie_share": (coh.get("mass") or [None] * len(grid))[lo] if regime == "middle"
                         else reg.get(regime),
            "trend": coh.get("trend"), "trend_note": coh.get("trend_note"),
            "freshness": coh.get("freshness")}


# ---- handler ---------------------------------------------------------------
def handler(event, context):
    import boto3          # ships with the Lambda runtime; the only third-party code in the trust path
    s3 = boto3.client("s3")
    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode()
        if len(body) > MAX_BODY:
            return resp(413, {"error": "payload too large"})
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            return resp(400, {"error": "payload rejected", "details": [f"not valid JSON: {e.msg}"]})

        auth = (event.get("headers") or {}).get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return resp(401, {"error": "missing OIDC token"})
        claims = verify_oidc(auth.split(None, 1)[1])

        errs = validate(payload, schema())
        if errs:
            return resp(400, {"error": "payload rejected", "details": errs[:10],
                              "schema": schema()["$id"]})

        # C-2: well-typed but arithmetically impossible submissions are still rejected
        merged = payload["merged_with_review_record"] + payload["merged_without_review_record"]
        bad = []
        if merged + payload["not_merged"] != payload["agent_prs"]:
            bad.append("merged + not_merged must equal agent_prs")
        if payload["agent_prs"] > payload["scanned_prs"]:
            bad.append("agent_prs cannot exceed scanned_prs")
        det = payload["detection"]
        if sum(det.values()) < payload["agent_prs"]:
            bad.append("detection counts cannot be fewer than agent_prs")
        mo = payload.get("monthly") or []
        if sum(m["with_record"] for m in mo) > payload["merged_with_review_record"] or \
           sum(m["without_record"] for m in mo) > payload["merged_without_review_record"]:
            bad.append("monthly totals exceed the overall counts")
        if bad:
            return resp(400, {"error": "payload rejected", "details": bad})
        if merged == 0:
            return resp(200, {"note": "no merged agent PRs; nothing to compare"})
        share = payload["merged_without_review_record"] / merged
        cohort = payload["identity_type"] if payload["identity_type"] in ("bot", "self") else "all"
        ctx = lookup(s3, cohort, share)

        full = claims.get("repository") or ""
        # C-3: check the shape ourselves rather than trusting GitHub's naming rules
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", full):
            return resp(401, {"error": "token has no usable repository claim"})
        # The name proves who is speaking, and is discarded here. What we store is
        # numbers — under a monthly-rotating key by default, or under the
        # cross-service pseudonym if this submission opted in.
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        linked = bool(payload.get("link"))
        if linked:
            import boto3 as _b
            key = af_id(_b.client("kms"), "github:repo", full)
            prefix, sort_key = LINKED_PREFIX, f"{key}/{month}"
        else:
            import boto3 as _b
            salt = month_salt(_b.client("ssm"), month)
            prefix, sort_key = POINTS_PREFIX, f"{month}/{dedup_key(salt, full)}"
        point = {"month": month,
                 "identity_type": payload["identity_type"],
                 "size_bucket": payload.get("size_bucket"),
                 "agent_prs": payload["agent_prs"],
                 "merged_with_review_record": payload["merged_with_review_record"],
                 "merged_without_review_record": payload["merged_without_review_record"],
                 "not_merged": payload["not_merged"],
                 "definition_version": payload["definition_version"]}
        # キーは重複排除のためだけのもの。秘密鍵なしでは元に戻せず、公開物には現れない。
        s3.put_object(Bucket=BUCKET, Key=f"{prefix}{sort_key}.json",
                      Body=json.dumps(point).encode(), ContentType="application/json")

        ctx["stored"] = {"what": sorted(point), "repository_name": "not stored",
                         "linked": linked,
                         "note": ("Your numbers were added to the aggregate as an anonymous point. "
                                  "We did not store your repository name. Your own copy of what you "
                                  "sent and what came back is in this workflow run's log."
                                  + (" This submission is connected to your earlier ones by a "
                                     "pseudonymous identifier, because you set link: true."
                                     if linked else
                                     " The de-duplication key rotates monthly, so no identifier "
                                     "connects this submission to any other month. The stored "
                                     "values are coarse but not provably unlinkable."))}
        # C-6: Only strings we control may appear in the response.
        # They flow into the caller's Markdown output, so validate their shape first.
        for k in ("cohort", "cohort_label", "cohort_version", "build", "regime",
                  "freshness", "trend_note"):
            v = ctx.get(k)
            if isinstance(v, str) and not re.fullmatch(r"[A-Za-z0-9 ,.:/_()\-]{0,400}", v):
                ctx[k] = ""
        return resp(200, ctx)
    except ValueError as e:
        return resp(401, {"error": str(e)})
    except Exception:
        return resp(500, {"error": "internal error"})


def resp(code, body):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body)}
