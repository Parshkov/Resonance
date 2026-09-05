"""Whose reasoning is being shared (2026-09-05).

A chat session is mostly the assistant's prose, and it is the same assistant
for everybody. Index a shape the assistant authored and this person is matched
to its habits rather than to their own — and since those habits recur in every
conversation it has, everyone eventually matches everyone. The signal the whole
product rests on is that the reasoning belongs to one person.

Nothing here can verify whose words they were: the conversation is never sent
to this service, by design. What it can do is make the claim explicit, refuse
the one that admits the assistant supplied the shape, and hand the accepted
claim back so the person sees it before they share and can say "no, that was
your idea".

This lives on its own because there is more than one way in. The MCP bridge
asks for it, and so does the browser's WebMCP surface, where an assistant
drives the page through /api/webmcp/prepare. A rule enforced on one path and
not the other is not a rule.
"""

from __future__ import annotations

from typing import Any, Mapping

ACCEPTED = {
    "their_own_words": "You said this. Your assistant copied it, it did not write it.",
    "their_words_reorganised":
        "Your claims, put in order by your assistant. Nothing was added.",
}
REFUSED = "i_proposed_it"

MISSING = ("state authorship: their_own_words, their_words_reorganised, or "
           "i_proposed_it. A chat is half your words, and only theirs can be shared.")
PROPOSED = ("A shape you proposed cannot be shared as theirs — it would introduce this "
            "person to people who match your reasoning, not to people who match them. "
            "Ask them to say it in their own words, then prepare again with those.")


class AuthorshipError(ValueError):
    """The caller did not say whose reasoning this is, or said it was its own."""


def require(arguments: Mapping[str, Any]) -> str:
    """Return the stated authorship, or raise with the reason it was refused."""
    stated = str(arguments.get("authorship") or "").strip()
    if not stated:
        raise AuthorshipError(MISSING)
    if stated == REFUSED:
        raise AuthorshipError(PROPOSED)
    if stated not in ACCEPTED:
        raise AuthorshipError(
            f"unknown authorship {stated!r}; use their_own_words or "
            "their_words_reorganised")
    return stated
