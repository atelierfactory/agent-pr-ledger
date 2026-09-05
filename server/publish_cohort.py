#!/usr/bin/env python3
"""Publish the cohort file under both a stable 'latest' URL and a versioned one.

This is where freshness works: even someone running a vendored, older copy
fetches latest and gets the current population. The version inside is displayed, so
the caller can always tell which population they were compared against.

The first edition is built from public research data (AIDev, through 2025-07). Once
submissions accumulate it is replaced in the same format, so clients need no change.
"""
from __future__ import annotations
import json, os, sys, hashlib

SOURCE = "cohort_latest.json"   # one canonical bundle, read by both client and server


def publish(local_dir: str, bucket: str | None = None, prefix: str = "v1/cohort/") -> list[str]:
    out = []
    s3 = None
    if bucket:
        import boto3
        s3 = boto3.client("s3")
    src = os.path.join(local_dir, SOURCE)
    if os.path.exists(src):
        art = json.load(open(src))
        body = json.dumps(art, indent=1).encode()
        # Never embed the hash in the file itself: doing so guarantees the published
        # artifact never matches its own digest, which looks broken to anyone verifying it.
        digest = hashlib.sha256(body).hexdigest()
        for key in (f"{prefix}cohort_{art['cohort_version']}.json",
                    f"{prefix}cohort_latest.json"):
            if s3:
                # versioned caches long, latest caches short.
                # Replacing latest delivers the new population on the next run.
                s3.put_object(Bucket=bucket, Key=key, Body=body,
                              ContentType="application/json",
                              CacheControl=("public, max-age=86400" if "latest" not in key
                                            else "public, max-age=3600, stale-if-error=2592000"))
            out.append(key)
            if s3:
                s3.put_object(Bucket=bucket, Key=key + ".sha256",
                              Body=(digest + "  " + os.path.basename(key) + "\n").encode(),
                              ContentType="text/plain")
            out.append(key + ".sha256")
    return out


def make_transparency(schema_path: str) -> dict:
    """transparency.json is generated from the very schema used for validation,

    so a hand-written description can never drift from what is actually enforced.
    """
    sch = json.load(open(schema_path))
    props = sch["properties"]

    def flat(p, pre=""):
        rows = []
        for k, v in p.items():
            if v.get("type") == "object":
                rows += flat(v.get("properties", {}), f"{pre}{k}.")
            elif v.get("type") == "array":
                rows += flat(v.get("items", {}).get("properties", {}), f"{pre}{k}[].")
            else:
                t = v.get("type") or ("const" if "const" in v else "enum")
                rows.append({"field": pre + k, "type": t,
                             "allowed": v.get("enum") or v.get("const") or v.get("pattern")})
        return rows

    return {"generated_from": sch["$id"],
            "note": "Generated from the validator itself. If this list and the validator disagree, "
                    "the validator is wrong and this file will not build.",
            "accepted_fields": flat(props),
            "never_accepted": sch["x-never-accepted"]}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "..", "data")
    keys = publish(data, os.environ.get("RECORD_BUCKET"))
    print("would publish:" if not os.environ.get("RECORD_BUCKET") else "published:")
    for k in keys:
        print("  " + k)
    t = make_transparency(os.path.join(here, "schema.json"))
    print(f"\ntransparency.json: {len(t['accepted_fields'])} accepted fields / "
          f"{len(t['never_accepted'])} never accepted")
    for r in t["accepted_fields"][:6]:
        print(f"    {r['field']:34} {r['type']}")
    print("    ...")
