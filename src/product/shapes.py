"""One shape, many names (2026-09-05).

The whole product rests on one assumption: that the shape it indexes is one
person's reasoning. `authorship.py` makes the assistant say so before a share,
and refuses the answer that admits otherwise. But that is a self-report, and
nothing checks it. A chat is mostly the assistant's prose, and it is the same
assistant for everybody. If it has a favourite framing -- pressure, a skipped
step, a bad outcome, a fix that prevents it -- and proposes it to fifty people,
fifty structurally identical thoughts arrive here under fifty names, and the
service starts introducing strangers to each other on the strength of a
language model's habits. Nobody in that room is a match for anyone.

This module is the check the self-report cannot give. It cannot see the
conversation, by design, so it cannot tell whose words a thought was. What it
can see is the corpus: when one exact shape arrives from many unrelated
accounts, that is not many people having the same thought, it is one author
with many names, and matches that rest on that shape alone are set aside.

What "the same shape" means here
--------------------------------
Exactly the same label-free skeleton: the same roles, the same relation types,
the same assertions and modalities, wired the same way. Labels, spans and
confidences never enter it, because two people using the same words about
their own reasoning are exactly who this product is for, and must not be
punished for it. Nothing looser than exact was considered acceptable: a
looser notion (shared sub-skeleton, similar-enough structure) starts deleting
genuine partial analogies, and the failure this guards against *is* exact
repetition -- a template produces the template.

What makes it a signature rather than a coincidence
---------------------------------------------------
Three conditions, all of which must hold before a match is touched:

* the shape has at least MIN_RELATIONS relations. A one- or two-relation chain
  is what almost every short input becomes (the cue extractor abstains on
  anything implicit), the space of such shapes is tiny, and whether such a
  pair is a resonance is already decided by the semantic layer, not the
  skeleton. Judging them would mostly delete real matches;

* at least MIN_ACCOUNTS distinct accounts hold it. Below that, coincidence
  among true ideas is entirely plausible -- people who come here self-select
  for thinking causally about systems, and small graphs have few shapes. The
  floor was set by measurement: the R7 demo corpus that ships with the
  product, which is 23 personas written from templates by one author, tops
  out at 7 accounts on one exact ten-relation shape. That is the one-author
  phenomenon in miniature, and it is also the demo; anything that fires at 7
  deletes the demo's own matches, and `ops/populate_local.py`'s three people
  after it. Twelve sits clearly above what a curated template corpus reaches
  and well above anything a small pilot reaches by chance;

* those accounts are at least MIN_SHARE of every account with a discoverable
  thought. A popular true idea is not a defect: in a corpus of thousands, a
  hundred people carrying the same feedback-loop skeleton is the product
  working, and they stay a small fraction. The failure is concentration --
  fifty of sixty. When one in four people on the whole service carry the
  identical skeleton, the skeleton is no longer evidence of anything about
  any one of them, so setting aside the matches that rest on it costs little
  even where a few were real.

The strict direction is the dangerous one. A real match wrongly deleted is
invisible: nobody is ever shown what they did not see. So every threshold
here errs permissive, the check never runs where it cannot measure (no store,
no census: nothing is dropped), and it only ever touches a row whose shape is
*exactly* the query's -- a match found through partial structure and shared
meaning is left alone. The known gap this leaves is a habit that is common in
absolute terms but a small share of a large corpus; the census exists so that
gap can be measured on a real corpus before anyone tightens the numbers.

What the person is told
-----------------------
One sentence, about the shape and not about them: that some of what matched
was set aside because its shape is one this service sees from many unrelated
people. No count, no names, no identifiers. "Many" is only ever said once at
least MIN_ACCOUNTS accounts hold the shape, so the sentence is itself
k-anonymous at a level far above the heat-map aggregation minimum, and it
reveals nothing about any one stranger the engine had not already put in
front of the viewer.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.graph import ThoughtGraph

SHAPE_SIGNATURE_VERSION = "resonance-shape-signature/0.1"

# See the module prose for why each of these is where it is.
MIN_RELATIONS = 3
MIN_ACCOUNTS = 12
MIN_SHARE = 0.25

# The four things a census can say about one shape.
TOO_SMALL = "too_small_to_judge"      # fewer than MIN_RELATIONS relations
COINCIDENCE = "coincidence"           # fewer than MIN_ACCOUNTS hold it
POPULAR = "popular"                   # many hold it, but a minority: not a defect
SIGNATURE = "signature"               # one author, many names

SAME_SHAPE_NOTE = (
    "Some of what matched was set aside: its shape is one this service sees from "
    "many unrelated people, so on its own it is not a sign of anyone in "
    "particular. This is about the shape, not about you or your thought."
)


def _h(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:16]


def shape_signature(graph: ThoughtGraph) -> str:
    """The label-free skeleton of one thought, as a stable string.

    Weisfeiler-Lehman colouring over (role, assertion, modality) nodes and
    (type, assertion, modality, direction) edges, iterated once per node so
    every part of the graph has had time to reach every other part, then
    hashed as a sorted multiset of node colours and coloured edges. Node ids,
    relation ids, labels, spans, confidences and the knowledge references
    derived from labels are all absent, so renaming, re-extracting or
    reordering a thought cannot change its signature, and two thoughts with
    the same wiring in different words share one.

    WL colouring is an invariant, not a canonical form: two differently wired
    graphs can in principle share a signature. For the sparse, role-typed
    graphs Thought DNA holds this is vanishingly rare, and its only effect
    would be to over-count one shape in the census by a little -- which the
    account floor absorbs.
    """
    colour = {node.id: _h("n", node.role, node.assertion, node.modality)
              for node in graph.nodes}
    edges = [(rel.source, rel.target, _h("e", rel.type, rel.assertion, rel.modality))
             for rel in graph.relations]
    for _ in range(max(1, len(colour))):
        refreshed: dict[str, str] = {}
        for node_id, own in colour.items():
            out = sorted(f"+{kind}:{colour.get(target, '?')}"
                         for source, target, kind in edges if source == node_id)
            inc = sorted(f"-{kind}:{colour.get(source, '?')}"
                         for source, target, kind in edges if target == node_id)
            refreshed[node_id] = _h("wl", own, *out, *inc)
        colour = refreshed
    parts = sorted(colour.values()) + sorted(
        f"{colour.get(source, '?')}>{kind}>{colour.get(target, '?')}"
        for source, target, kind in edges)
    return _h(SHAPE_SIGNATURE_VERSION, *parts)


def shape_of(thought_dna: Mapping[str, Any]) -> tuple[str, int, int] | None:
    """(signature, node count, relation count) for stored DNA, or None when it
    does not parse. A stored row that fails to parse is somebody else's problem
    (the persistence layer validates on the way in); here it is simply not
    counted, which is the permissive direction."""
    try:
        graph = ThoughtGraph.from_dict(dict(thought_dna))
    except Exception:  # noqa: BLE001 - unparseable rows are not counted
        return None
    return shape_signature(graph), len(graph.nodes), len(graph.relations)


@dataclass(frozen=True)
class ShapeCount:
    signature: str
    nodes: int
    relations: int
    accounts: int
    thoughts: int


@dataclass(frozen=True)
class ShapeCensus:
    """How many unrelated accounts hold each exact shape, right now.

    Built from every discoverable thought the engine searches over -- the
    people, the seeded personas, all of it -- because that is the population
    whose concentration decides whether a shape still means anything.
    """
    accounts: int
    thoughts: int
    counts: Mapping[str, ShapeCount]

    @classmethod
    def of(cls, rows: Iterable[tuple[str, Mapping[str, Any]]]) -> "ShapeCensus":
        """``rows`` are (account id, thought DNA) pairs for discoverable thoughts."""
        holders: dict[str, set[str]] = defaultdict(set)
        thoughts: dict[str, int] = defaultdict(int)
        sizes: dict[str, tuple[int, int]] = {}
        everyone: set[str] = set()
        total = 0
        for account, dna in rows:
            shape = shape_of(dna)
            if shape is None:
                continue
            signature, nodes, relations = shape
            holders[signature].add(account)
            thoughts[signature] += 1
            sizes[signature] = (nodes, relations)
            everyone.add(account)
            total += 1
        counts = {
            signature: ShapeCount(signature, sizes[signature][0], sizes[signature][1],
                                  len(owners), thoughts[signature])
            for signature, owners in holders.items()
        }
        return cls(accounts=len(everyone), thoughts=total, counts=counts)

    def verdict(self, signature: str) -> str:
        count = self.counts.get(signature)
        if count is None:
            return COINCIDENCE
        if count.relations < MIN_RELATIONS:
            return TOO_SMALL
        if count.accounts < MIN_ACCOUNTS:
            return COINCIDENCE
        if self.accounts and count.accounts / self.accounts < MIN_SHARE:
            return POPULAR
        return SIGNATURE

    def is_signature(self, signature: str) -> bool:
        return self.verdict(signature) == SIGNATURE

    def summary(self, *, minimum: int = 3) -> dict[str, Any]:
        """The measurement, with nothing in it that names a person or a row.

        Shapes held by fewer than ``minimum`` accounts are folded into a count
        rather than listed, the same anti-inference rule the heat map uses, so
        the summary cannot be used to work out that some one person's thought
        is the odd one out. Shares are rounded to two decimals because that is
        the most precision anyone reading this needs.
        """
        listed = []
        folded = 0
        for count in sorted(self.counts.values(),
                            key=lambda c: (-c.accounts, -c.thoughts, c.signature)):
            if count.accounts < minimum:
                folded += 1
                continue
            listed.append({
                "held_by_accounts": count.accounts,
                "thoughts": count.thoughts,
                "nodes": count.nodes,
                "relations": count.relations,
                "share_of_accounts": round(count.accounts / self.accounts, 2)
                if self.accounts else 0.0,
                "verdict": self.verdict(count.signature),
            })
        return {
            "signature_version": SHAPE_SIGNATURE_VERSION,
            "accounts_with_a_discoverable_thought": self.accounts,
            "discoverable_thoughts": self.thoughts,
            "distinct_shapes": len(self.counts),
            "shapes_held_by_fewer_than_minimum": folded,
            "thresholds": {"min_relations": MIN_RELATIONS,
                           "min_accounts": MIN_ACCOUNTS,
                           "min_share_of_accounts": MIN_SHARE},
            "shapes": listed,
        }


def census_of_repository(repo: Any) -> ShapeCensus:
    """The census over the people this is a claim about: real participants.

    Discoverable rows of accounts that are not hidden, mirroring the
    persistence layer's own notion of a visible session -- and only rows a
    person actually shared. A store that cannot answer is an empty census, and
    an empty census never condemns anything.

    Seeded demo personas are excluded, and not as a convenience. The whole
    finding this module reports is "one author wrote many of these", and a
    template corpus IS one author writing many of them: counting it proves
    itself, and then deletes the demo's own matches to say so. The same
    `record_kind == "volunteer"` line is what the standing search uses to
    decide whom it may tell about whom, for the same reason -- a fixture is
    not somebody.
    """
    rows: list[tuple[str, Mapping[str, Any]]] = []
    try:
        for session in repo.list_discoverable_sessions():
            user = repo.get_user(session.user_id)
            if user is None or getattr(user, "hidden", False):
                continue
            kind = str(getattr(session, "record_kind", "") or "")
            if kind and kind != "volunteer":
                continue
            rows.append((str(session.user_id), session.thought_dna))
    except Exception:  # noqa: BLE001 - cannot measure: must not delete
        return ShapeCensus(accounts=0, thoughts=0, counts={})
    return ShapeCensus.of(rows)
