"""Human names for people who are not using their own.

Resonance shows one participant to another under a pseudonym, because a
structural match is not consent to know who someone is. But a pseudonym is
still how a person is met here, and `person-e44cc785bd402c06` is not a way to
meet anyone. It reads as a case number, and it makes the first thing you learn
about a stranger the least human thing about them.

So a pseudonym is two ordinary words — a quality and a figure, in the register
of folk tales and adventuring parties. "Quiet Lantern". "Amber Cartographer".
Something a person can say out loud, remember, and refer to later.

The lists below are chosen to be pleasant in any combination: no proper names,
nothing that could land as a slur or a slight, nothing that implies a gender,
an age, a nationality or a body. A pseudonym must not accidentally describe the
person it is given to.

Uniqueness is not left to luck. `generate` is told which names are already
taken and avoids them; if the pair it wants is gone it tries other pairs, and
only when the space is genuinely crowded does it fall back to an ordinal —
"Quiet Lantern the Second" — which is still a name and not a serial number.
"""

from __future__ import annotations

import secrets
from typing import Callable, Iterable

QUALITIES = (
    "Amber", "Ancient", "Autumn", "Bashful", "Bold", "Bramble", "Brass",
    "Bright", "Bronze", "Candid", "Careful", "Cedar", "Cheerful", "Cinder",
    "Clever", "Cobalt", "Copper", "Coral", "Crimson", "Curious", "Dapper",
    "Dawn", "Daring", "Distant", "Dusty", "Eager", "Early", "Ember",
    "Errant", "Fabled", "Faithful", "Fearless", "Fern", "Fleet", "Frosted",
    "Gallant", "Gentle", "Gilded", "Glass", "Golden", "Grave", "Hazel",
    "Hidden", "Honest", "Humble", "Idle", "Indigo", "Ivory", "Jade",
    "Jolly", "Keen", "Kindly", "Lantern", "Lavender", "Lazy", "Lucky",
    "Marbled", "Merry", "Midnight", "Mild", "Modest", "Mossy", "Nimble",
    "Northern", "Olive", "Opal", "Patient", "Pewter", "Placid", "Plucky",
    "Quick", "Quiet", "Rambling", "Restless", "Rowan", "Ruby", "Rustic",
    "Sable", "Saffron", "Sanguine", "Scarlet", "Secret", "Sepia", "Silent",
    "Silver", "Slate", "Solemn", "Sparrow", "Spry", "Steady", "Stormy",
    "Sudden", "Sunlit", "Tawny", "Tender", "Thorn", "Thrifty", "Tidy",
    "Timber", "Twilight", "Umber", "Unhurried", "Velvet", "Verdant",
    "Wandering", "Watchful", "Willow", "Winter", "Wistful", "Wry", "Zealous",
)

FIGURES = (
    "Alchemist", "Almanac", "Anchor", "Apothecary", "Archivist", "Astrolabe",
    "Aviator", "Beacon", "Beekeeper", "Bellringer", "Bookbinder", "Botanist",
    "Brewer", "Cairn", "Candlemaker", "Cartographer", "Chandler", "Chronicle",
    "Clockmaker", "Compass", "Cooper", "Courier", "Ferryman", "Fiddler",
    "Finch", "Fletcher", "Forager", "Fossil", "Gardener", "Glassblower",
    "Harbinger", "Harper", "Herald", "Hermit", "Innkeeper", "Ironsmith",
    "Kestrel", "Kite", "Lamplighter", "Lantern", "Lapidary", "Lexicon",
    "Librarian", "Lighthouse", "Locksmith", "Luthier", "Magpie", "Mapmaker",
    "Mariner", "Mason", "Millwright", "Minstrel", "Navigator", "Nomad",
    "Orchard", "Otter", "Outrider", "Papermaker", "Pathfinder", "Pilgrim",
    "Potter", "Prospector", "Quarry", "Quill", "Ranger", "Reveller",
    "Rookery", "Sailmaker", "Scholar", "Scribe", "Sentinel", "Shepherd",
    "Signpost", "Skylark", "Smith", "Sojourner", "Songbird", "Spindle",
    "Stargazer", "Steward", "Stonecutter", "Storyteller", "Surveyor",
    "Swallow", "Tanner", "Thimble", "Tinker", "Toolmaker", "Trailblazer",
    "Vagabond", "Vintner", "Voyager", "Wanderer", "Watchmaker", "Wayfarer",
    "Weaver", "Wheelwright", "Whittler", "Woodcutter", "Wren",
)

# "the Second" reads as a name; "#2" reads as a queue ticket. The list runs out
# deliberately — past this many collisions on one pair the space is the problem,
# not the naming.
ORDINALS = (
    "the Second", "the Third", "the Fourth", "the Fifth", "the Sixth",
    "the Seventh", "the Eighth", "the Ninth", "the Tenth", "the Eleventh",
    "the Twelfth",
)

MAX_PAIR_ATTEMPTS = 64

_QUALITIES = frozenset(QUALITIES)
_FIGURES = frozenset(FIGURES)
_ORDINALS = frozenset(ORDINALS)


def combinations() -> int:
    """How many distinct pairs exist before ordinals are needed."""
    return len(QUALITIES) * len(FIGURES)


def is_pseudonym(label: str) -> bool:
    """Whether a display label was drawn from this vocabulary.

    Used to tell a name this service gave someone from one carried in from
    somewhere else — a provider's real name, or an old `guest-…` identifier.
    """
    if not isinstance(label, str):
        return False
    parts = label.strip().split()
    if len(parts) < 2:
        return False
    if parts[0] not in _QUALITIES or parts[1] not in _FIGURES:
        return False
    if len(parts) == 2:
        return True
    return " ".join(parts[2:]) in _ORDINALS


def generate(taken: Callable[[str], bool] | Iterable[str] | None = None) -> str:
    """A pseudonym nobody else is using.

    `taken` is either a predicate or a collection of names already in use. It
    is asked, not guessed at: two people meeting under the same name in a
    service whose whole purpose is introductions would be worse than an ugly
    name.
    """
    if taken is None:
        is_taken: Callable[[str], bool] = lambda _name: False
    elif callable(taken):
        is_taken = taken
    else:
        used = {str(name) for name in taken}
        is_taken = used.__contains__

    for _ in range(MAX_PAIR_ATTEMPTS):
        candidate = f"{secrets.choice(QUALITIES)} {secrets.choice(FIGURES)}"
        if not is_taken(candidate):
            return candidate

    # Every pair we tried is spoken for. Keep the last one and number it, which
    # is still a name someone can say.
    base = f"{secrets.choice(QUALITIES)} {secrets.choice(FIGURES)}"
    for ordinal in ORDINALS:
        candidate = f"{base} {ordinal}"
        if not is_taken(candidate):
            return candidate
    raise RuntimeError("the pseudonym vocabulary is exhausted; widen the lists")
