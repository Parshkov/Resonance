"""Client ID Metadata Documents (CIMD).

Dynamic client registration asks every client to register before it can ask for
anything, so a directory that connects thousands of people creates thousands of
registrations for what is really one client. CIMD replaces that: the client's
`client_id` *is* an https URL, and the document it serves describes the client.
Nothing is stored, nothing accumulates, and the client is identified by a name
its owner controls. Both Anthropic and OpenAI prefer it for this reason.

The cost is that the authorization server now fetches a URL chosen by whoever
is asking. That is a server-side request forgery primitive unless it is fenced
in, so this module treats the fetch as hostile by default:

- https only, and no credentials in the URL;
- every address the host resolves to must be globally routable, which keeps the
  fetch away from loopback, link-local, private ranges and cloud metadata
  endpoints;
- redirects are followed only to targets that pass the same checks, and only a
  few of them;
- the response is capped in both time and bytes, and must be JSON;
- the document's own `client_id` must equal the URL it was fetched from, so a
  document cannot claim to be a different client.

The result is cached briefly. A client that connects a hundred people in a
minute is fetched once.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import urlsplit

USER_AGENT = "resonance-oauth/1.0"
FETCH_TIMEOUT_SECONDS = 5
MAX_DOCUMENT_BYTES = 64 * 1024
MAX_REDIRECTS = 3
CACHE_TTL_SECONDS = 300
MAX_CACHE_ENTRIES = 256


class CimdError(ValueError):
    """A client_id URL did not yield a usable client metadata document."""


@dataclass(frozen=True)
class ClientMetadata:
    client_id: str
    client_name: str
    redirect_uris: tuple[str, ...]
    scope: str

    def allows(self, redirect_uri: str) -> bool:
        # Exact match only. Prefix or wildcard matching on redirect URIs is the
        # classic way authorization codes end up delivered to someone else.
        return redirect_uri in self.redirect_uris


def looks_like_cimd(client_id: str) -> bool:
    """Whether this client_id is a URL rather than a registered identifier."""
    return isinstance(client_id, str) and client_id.startswith("https://")


def _require_public_host(host: str) -> None:
    """Refuse a host that resolves anywhere but the public internet.

    Checked against *every* address the name resolves to, because a name that
    returns one public and one private address would otherwise be a way in.
    """
    if not host:
        raise CimdError("client_id URL has no host")
    try:
        resolved = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise CimdError("client_id host does not resolve") from exc
    if not resolved:
        raise CimdError("client_id host does not resolve")
    for entry in resolved:
        address = entry[4][0]
        try:
            parsed = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise CimdError("client_id host resolved to an unusable address") from exc
        if not parsed.is_global:
            raise CimdError("client_id host resolves to a non-public address")


def _validate_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise CimdError("client_id must be an https URL")
    if parts.username or parts.password:
        raise CimdError("client_id URL must not carry credentials")
    if parts.fragment:
        raise CimdError("client_id URL must not carry a fragment")
    _require_public_host(parts.hostname or "")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop urllib following redirects for us, so each hop can be checked."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _fetch_once(url: str) -> tuple[bytes | None, str | None]:
    """Return (body, redirect_target). Exactly one of the two is set."""
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }, method="GET")
    try:
        with _OPENER.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            # One byte over the cap is enough to know it is over the cap.
            body = response.read(MAX_DOCUMENT_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            target = exc.headers.get("Location") if exc.headers else None
            if not target:
                raise CimdError("client_id redirected without a target") from exc
            return None, urllib.parse.urljoin(url, target)
        raise CimdError(f"client_id URL returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise CimdError("client_id URL is unreachable") from exc
    if len(body) > MAX_DOCUMENT_BYTES:
        raise CimdError("client metadata document is too large")
    return body, None


def _read_document(client_id: str) -> dict[str, Any]:
    url = _validate_url(client_id)
    for _ in range(MAX_REDIRECTS + 1):
        body, target = _fetch_once(url)
        if body is not None:
            try:
                document = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CimdError("client metadata document is not JSON") from exc
            if not isinstance(document, dict):
                raise CimdError("client metadata document is not an object")
            return document
        url = _validate_url(target or "")
    raise CimdError("client_id URL redirected too many times")


def _parse(client_id: str, document: dict[str, Any]) -> ClientMetadata:
    declared = str(document.get("client_id") or "")
    if declared != client_id:
        # Without this a document could claim any client_id it liked, and the
        # URL would stop being the client's identity.
        raise CimdError("client metadata document declares a different client_id")
    uris = document.get("redirect_uris")
    if not isinstance(uris, list) or not uris:
        raise CimdError("client metadata document declares no redirect_uris")
    cleaned: list[str] = []
    for uri in uris:
        if not isinstance(uri, str) or not uri:
            raise CimdError("client metadata document has a malformed redirect_uri")
        cleaned.append(uri)
    name = str(document.get("client_name") or "").strip()
    return ClientMetadata(
        client_id=client_id,
        client_name=name[:120],
        redirect_uris=tuple(cleaned),
        scope=str(document.get("scope") or "").strip(),
    )


class ClientMetadataCache:
    """Short-lived cache of fetched documents, keyed by client_id URL."""

    def __init__(self, *, ttl: int = CACHE_TTL_SECONDS, clock: Any = time.time) -> None:
        self._entries: dict[str, tuple[float, ClientMetadata]] = {}
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.RLock()

    def get(self, client_id: str, *, reader: Any = None) -> ClientMetadata:
        now = self._clock()
        with self._lock:
            cached = self._entries.get(client_id)
            if cached is not None and cached[0] > now:
                return cached[1]
        metadata = _parse(client_id, (reader or _read_document)(client_id))
        with self._lock:
            if len(self._entries) >= MAX_CACHE_ENTRIES:
                # Cheap and sufficient: a full cache is dropped rather than
                # ranked, since a stampede here costs one fetch per client.
                self._entries.clear()
            self._entries[client_id] = (now + self._ttl, metadata)
        return metadata


def fetch_client_metadata(client_id: str, *, cache: ClientMetadataCache | None = None,
                          reader: Any = None) -> ClientMetadata:
    """The client this `client_id` URL describes, or raise `CimdError`."""
    if not looks_like_cimd(client_id):
        raise CimdError("client_id is not a metadata document URL")
    store = cache or ClientMetadataCache()
    return store.get(client_id, reader=reader)
