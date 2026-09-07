#!/usr/bin/env python3
"""Tell search engines that pages changed (IndexNow: Bing, Yandex, Naver, Seznam, Yep; shared between them).

The key file must be live at https://<host>/<key>.txt first. No account, no token.

  python3 tools/indexnow.py https://atelierfactory.github.io/agent-pr-ledger/ https://atelierfactory.github.io/agent-pr-ledger/llms.txt
"""
import json, sys, urllib.request, urllib.parse

def main(urls):
    if not urls:
        sys.exit(__doc__)
    host = urllib.parse.urlparse(urls[0]).netloc
    key = open("site/indexnow-key.txt").read().strip()
    body = json.dumps({"host": host, "key": key, "keyLocation": f"https://{host}/agent-pr-ledger/{key}.txt"
                       if host.endswith("github.io") else f"https://{host}/{key}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("indexnow:", r.status, r.reason)

if __name__ == "__main__":
    main(sys.argv[1:])
