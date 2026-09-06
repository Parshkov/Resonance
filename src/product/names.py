"""A name for anything that only had an identifier.

A person is told what they have here by name: a pseudonym for a person, a
title for a thought or a group. Some things never had one -- a search, a
draft prepared from text, an introduction -- and an assistant read their
identifiers out loud: "ws-fe60a90cb3a2415ac6263278". An identifier is for the
next call; it means nothing to a person.

So every such thing also gets a name, derived from its identifier and
therefore stable: the same search is "Amber Harbour" every time it is
mentioned, and two searches are unlikely to collide (about 4,000 names).
Names are presentation only; the identifier still travels beside them.
"""

from __future__ import annotations

import hashlib

ADJECTIVES = (
    "amber", "quiet", "brisk", "cedar", "coral", "dusky", "early", "fleet", "gentle",
    "golden", "hazel", "ivory", "jade", "keen", "lunar", "maple", "misty", "noble",
    "olive", "pale", "plain", "rapid", "rustic", "sable", "silver", "sunny", "tender",
    "tidal", "umber", "velvet", "verdant", "wandering", "willow", "wild", "young",
    "bright", "calm", "clear", "deep", "even", "fair", "fresh", "grand", "green",
    "high", "kind", "light", "low", "mild", "near", "open", "proud", "round", "sharp",
    "slow", "soft", "still", "swift", "warm", "wide",
)
NOUNS = (
    "harbour", "lantern", "meadow", "orchard", "compass", "ledger", "beacon",
    "canyon", "delta", "estuary", "furrow", "glacier", "hollow", "island", "jetty",
    "kiln", "lagoon", "marsh", "notch", "oasis", "pier", "quarry", "ridge", "saddle",
    "terrace", "upland", "valley", "wharf", "anvil", "bridge", "channel", "dune",
    "ember", "fjord", "grove", "hearth", "inlet", "junction", "keel", "loom",
    "mill", "nook", "outpost", "pass", "quay", "reef", "spire", "trail", "vale",
    "well", "yard", "arbor", "bay", "cairn", "dell", "ford", "gate", "haven",
    "knoll", "landing",
)


def name_for(identifier: str, *, prefix: str = "") -> str:
    """A stable two-word name for an identifier, e.g. "Amber Harbour"."""
    digest = hashlib.blake2b(str(identifier).encode("utf-8"), digest_size=4).digest()
    value = int.from_bytes(digest, "big")
    adjective = ADJECTIVES[value % len(ADJECTIVES)]
    noun = NOUNS[(value // len(ADJECTIVES)) % len(NOUNS)]
    name = f"{adjective.capitalize()} {noun.capitalize()}"
    return f"{prefix} {name}".strip() if prefix else name


def thought_name(session: dict) -> str:
    """A thought's own title when it has one, otherwise a name from its id."""
    presentation = session.get("presentation") or {}
    topic = str(presentation.get("topic") or "").strip()
    if topic and topic != "Shared thought":
        return topic
    return name_for(str(session.get("session_id") or ""), prefix="Thought")
