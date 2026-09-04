"""Evidence-only wrapper around ops/oauth_smoke.py.

Why: against the public origin the Railway edge lowercases response header
names (`www-authenticate`). ops/oauth_smoke.py builds `dict(r.headers)` and
looks up `WWW-Authenticate` / `Location` case-sensitively, so step 1 fails
client-side although the server DID send the header (see phase1_http.md 1b).
This wrapper only makes the header mapping case-insensitive; the smoke logic
and every assertion are untouched. Product code is not modified.
"""
import sys
sys.path.insert(0, ".")
from ops import oauth_smoke  # noqa: E402


class _CI(dict):
    def __init__(self, items):
        super().__init__((k.lower(), v) for k, v in dict(items).items())

    def get(self, key, default=None):
        return super().get(key.lower(), default)


_orig = oauth_smoke.Smoke._req


def _req(self, url, **kw):
    status, headers, body = _orig(self, url, **kw)
    return status, _CI(headers), body


oauth_smoke.Smoke._req = _req

if __name__ == "__main__":
    sys.exit(oauth_smoke.main())
