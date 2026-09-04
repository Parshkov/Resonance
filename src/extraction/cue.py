"""Cue-grounded Thought Graph extraction (v0.2).

Deterministic, dependency-free, no LLM. Every relation is licensed by an
explicit lexical connective in the text ("because", "leads to", "prevents",
"depends on", ...); implicit causation is abstained, never guessed.

v0.2 replaces the 12-pattern v0.1 window extractor with:

* sentence and clause segmentation with character offsets;
* ~90 connectives in seven relation types, each with a direction (whether the
  source argument sits left or right of the cue) and a confidence;
* argument extraction that strips determiners, auxiliaries, pronoun subjects
  and adverbs, keeps up to six content tokens, and resolves a bare pronoun
  subject ("this", "it", "which") to the previous relation's target;
* node unification by stem set (equality or containment) and span overlap;
* role assignment from the deterministic lexicon first, then from the node's
  position in the extracted graph (sources of causal chains are problems,
  sinks are outcomes, sources of `prevents` are methods, ...);
* clause-scoped negation and modality;
* PII scrubbing of labels (spans stay grounded to the raw text and are dropped
  by the product on share).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from src.graph import Node, Relation, ThoughtGraph, make_node_id, make_relation_id, make_thought_id, validate_thought
from src.interfaces import ConfigRef, ExtractionResult
from src.semantics import role_hint as _role_hint, scrub as _scrub, stems as _stems

EXTRACTOR_ID = "resonance-cue-extractor"
EXTRACTOR_VERSION = "0.2.0"
DROP_THRESHOLD = 0.35
IOU_MERGE = 0.5
MAX_ARG_TOKENS = 6
FROZEN_EXTRACTION_RUNS = Path(__file__).resolve().parents[2] / "benchmark" / "r0-v0.1" / "extraction_runs.jsonl"

# (pattern, relation type, direction, confidence). direction "fwd": left arg is
# the source; "rev": right arg is the source. Longer/more specific cues first.
_CUE_TABLE: tuple[tuple[str, str, str, float], ...] = (
    # ---- causes, reversed (effect ... cue ... cause) --------------------
    (r"is caused by|are caused by|was caused by|were caused by|caused by", "causes", "rev", 0.88),
    (r"is driven by|are driven by|driven by|is triggered by|triggered by|is fuelled by|is fueled by|fueled by|fuelled by", "causes", "rev", 0.84),
    (r"results from|result from|resulted from|stems from|stem from|stemmed from|arises from|arise from|arose from|comes from|come from|came from|originates from|is a consequence of|is a result of|as a consequence of|as a result of", "causes", "rev", 0.82),
    (r"because of|owing to|due to|thanks to|on account of", "causes", "rev", 0.8),
    (r"because|since", "causes", "rev", 0.72),
    # ---- causes, forward --------------------------------------------------
    (r"leads to|lead to|led to|leading to|results in|result in|resulted in|resulting in|gives rise to|gave rise to|brings about|brought about|sets off|set off|ends up in|ended up in", "causes", "fwd", 0.86),
    (r"causes|caused|causing|cause", "causes", "fwd", 0.9),
    (r"triggers|triggered|trigger|drives|drove|driving|drive|induces|induced|induce|produces|produced|produce|generates|generated|generate|creates|created|create|spawns|spawned|forces|forced|force", "causes", "fwd", 0.8),
    (r"increases|increased|increase|raises|raised|raise|boosts|boosted|amplifies|amplified|amplify|worsens|worsened|worsen|exacerbates|exacerbated|accelerates|accelerated|accelerate|escalates|escalated|inflates|inflated|fuels|fuelled|fueled|feeds|fed", "causes", "fwd", 0.74),
    (r"makes|made|make|turns into|turned into|translates into|translated into", "causes", "fwd", 0.6),
    # clause-level consequence markers: previous clause causes this clause
    (r"therefore|hence|thus|consequently|as a result|so that|which means|which is why|and so|and then|so", "causes", "fwd", 0.7),
    # conditionals: "if X then Y" / "when X, Y" -> X causes Y (conditional)
    (r"if|whenever|when|once|unless", "causes", "cond", 0.62),
    # ---- prevents ------------------------------------------------------------
    (r"is prevented by|prevented by|is blocked by|blocked by|is mitigated by|mitigated by|is reduced by|reduced by|is avoided by|avoided by|is suppressed by|suppressed by|is countered by|countered by|is offset by|offset by", "prevents", "rev", 0.84),
    (r"prevents|prevented|preventing|prevent|avoids|avoided|avoid|averts|averted|avert|blocks|blocked|block|stops|stopped|stop|halts|halted|halt|eliminates|eliminated|eliminate", "prevents", "fwd", 0.88),
    (r"reduces|reduced|reduce|lowers|lowered|lower|decreases|decreased|decrease|mitigates|mitigated|mitigate|suppresses|suppressed|suppress|dampens|dampened|dampen|counteracts|counteracted|counteract|inhibits|inhibited|inhibit|curbs|curbed|curb|offsets|offset|alleviates|alleviated|alleviate|relieves|relieved|relieve|protects against|protect against|protected against|guards against|guard against|guarded against|defends against|shields from|shield from|keeps .{1,30}? from|kept .{1,30}? from|depletes|depleted|deplete|drains|drained|drain|exhausts|exhausted|exhaust|erodes|eroded|erode|consumes|consumed|slows|slowed|slows down|slow down|delays|delayed|stalls|stalled|hampers|hampered|hinders|hindered|impedes|impeded|weakens|weakened|weaken|degrades|degraded|degrade", "prevents", "fwd", 0.76),
    # ---- requires --------------------------------------------------------------
    (r"is required for|required for|is needed for|needed for|is necessary for|necessary for|is a prerequisite for|prerequisite for|is essential for|essential for|enables|enabled|enable|allows|allowed|allow|permits|permitted|permit|makes possible|made possible|unlocks|unlocked|unlock", "requires", "rev", 0.74),
    (r"requires|required|require|requiring|needs|needed|need|depends on|depend on|depended on|dependent on|relies on|rely on|relied on|reliant on|hinges on|hinged on|is contingent on|contingent on|presupposes|presuppose|calls for|called for|demands|demanded|demand|cannot happen without|can't happen without|is impossible without|impossible without", "requires", "fwd", 0.86),
    # ---- part_of -----------------------------------------------------------------
    (r"is part of|are part of|part of|is a part of|belongs to|belong to|belonged to|is a component of|is one component of|component of|is a piece of|is a subset of|subset of|is a member of|is an element of|falls under|falls within|sits inside|sits within", "part_of", "fwd", 0.84),
    (r"consists of|consist of|consisted of|is made up of|made up of|is composed of|composed of|comprises|comprised|comprise|includes|included|include|contains|contained|contain|encompasses|encompass|is built from|built from", "part_of", "rev", 0.78),
    # ---- constrains --------------------------------------------------------------
    (r"is limited by|limited by|is constrained by|constrained by|is restricted by|restricted by|is bounded by|bounded by|is capped by|capped by|is bound by|bound by|is governed by|governed by", "constrains", "rev", 0.82),
    (r"constrains|constrained|constraining|constrain|limits|limited|limit|restricts|restricted|restrict|caps|capped|bounds|bounded|throttles|throttled|throttle|governs|governed|govern|rate-limits|rate limits|puts a ceiling on|puts a cap on|sets a limit on|sets an upper bound on", "constrains", "fwd", 0.84),
    # ---- supports ------------------------------------------------------------------
    (r"is supported by|supported by|is shown by|shown by|is confirmed by|confirmed by|is backed by|backed by|is evidenced by|evidenced by|is corroborated by|corroborated by|is demonstrated by|demonstrated by|is suggested by|suggested by|is indicated by|indicated by|according to", "supports", "rev", 0.74),
    (r"supports|supported|supporting|support|suggests|suggested|suggest|indicates|indicated|indicate|shows|showed|shown|show|confirms|confirmed|confirm|demonstrates|demonstrated|demonstrate|proves|proved|prove|is evidence for|is evidence of|evidence for|evidence of|evidence that|is consistent with|consistent with|backs up|backs|backed|corroborates|corroborated|corroborate|points to|pointed to|point to|reveals|revealed|reveal|hints that|hints at|implies|implied|imply|argues for|argue for|substantiates|validates|validated|validate|verifies|verified", "supports", "fwd", 0.72),
    # ---- contradicts -----------------------------------------------------------------
    (r"is contradicted by|contradicted by|is refuted by|refuted by|is undermined by|undermined by|is disproved by|disproved by", "contradicts", "rev", 0.76),
    (r"contradicts|contradicted|contradict|conflicts with|conflict with|conflicted with|is inconsistent with|inconsistent with|is incompatible with|incompatible with|undermines|undermined|undermine|refutes|refuted|refute|disproves|disproved|disprove|rules out|ruled out|rule out|argues against|argue against|argued against|is at odds with|at odds with|clashes with|clash with|clashed with|casts doubt on|cast doubt on|challenges|challenged|challenge|goes against|went against|runs counter to|ran counter to|counters|countered|counter", "contradicts", "fwd", 0.78),
)
CUES: tuple[tuple[re.Pattern[str], str, str, float], ...] = tuple(
    (re.compile(r"\b(?:" + pattern + r")\b", re.I), rel_type, direction, conf)
    for pattern, rel_type, direction, conf in _CUE_TABLE
)
# Public v0.1-compatible view (pattern text, type, confidence, reverse flag).
CUE_COUNT = sum(len(p.split("|")) for p, _t, _d, _c in _CUE_TABLE)

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])|\n{2,}")
CLAUSE_BOUNDARY = re.compile(
    r"[,;:!?]|\.(?=\s|$)|\((?:.*?)\)|\s--\s|\s-\s|—|\b(?:and|but|or|nor|yet|while|whereas|although|though|even though|"
    r"however|meanwhile|then|which|who|whom|where|whether|after|before|until|till|so|because|since|if|when|"
    r"whenever|once|unless|that)\b",
    re.I,
)
AUX_AFTER_THAT = re.compile(
    r"\s+(?:is|are|was|were|has|have|had|will|would|can|could|may|might|should|must|do|does|did|"
    r"cannot|never|not)\b",
    re.I,
)
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-/]*")
LEADING_DROP = frozenset(
    "the a an this that these those our their its my his her your it they we there here you i he she "
    "some any every each all both few many most much such no not also often usually eventually then now "
    "still already just even only really very quite rather too as of in on at by for with from to into "
    "about over under through during is are was were be been being am has have had do does did will would "
    "can could may might should must shall ought seems seem seemed appears appear appeared tends tend tended "
    "keeps keep kept gets get got became become becomes getting becoming being going went go goes".split()
)
TRAILING_DROP = frozenset(
    "too again also anyway though however as well over time at all in turn itself themselves him her them it "
    "is are was were be been being has have had do does did will would can could may might should must shall "
    "of in on at by for with from to into about over under through during a an the which who that whom "
    "not never no longer cannot probably possibly likely perhaps maybe potentially eventually still then often "
    "usually always sometimes rarely hardly seldom now already just even only really very quite rather "
    "gradually slowly quickly rapidly increasingly".split()
)
PRONOUN_ONLY = frozenset("this that it which they these those such he she we one".split())
NEGATORS = re.compile(
    r"(?:\bdo\s+not|\bdoes\s+not|\bdid\s+not|\bcannot|\bcan(?:no)?'?t|\bwill\s+not|\bwon'?t|\bwould\s+not|"
    r"\bwouldn'?t|\bnever|\bnot|\bno\s+longer|\bfails?\s+to|\bfailed\s+to|\bdoesn'?t|\bdon'?t|\bdidn'?t|\bisn'?t|"
    r"\baren'?t|\bwasn'?t|\bweren'?t|\bhardly|\brarely|\bneither|\bnor)\s+(?:\w+\s+){0,2}$",
    re.I,
)
POSSIBLE = re.compile(r"\b(?:may|might|could|possibly|perhaps|probably|likely|maybe|potentially|can|appears? to|seems? to|tends? to)\b", re.I)
CONDITIONAL = re.compile(r"\b(?:if|unless|would|whenever|in case|provided that|assuming)\b", re.I)
GENERIC_ROLE_WORDS = frozenset("problem mechanism state outcome constraint method evidence resource agent".split())
# Cue words that are also common nouns; read as verbs only in verb position.
NOUN_VERB_CUES = frozenset(
    "limit limits cause causes support supports need needs block blocks demand demands drive drives force forces "
    "trigger triggers increase increases decrease decreases cap caps bound bounds counter counters challenge challenges "
    "offset offsets halt halts stop stops result results".split()
)
NOUN_LEFT = frozenset("the a an this that these those its their our my his her your of no any some each every "
                      "upper lower hard soft root main key primary one another such".split())
COMPOUND_LEFT = frozenset("rate speed time size weight age height credit spending hiring headcount staffing memory "
                          "cpu budget storage traffic load power current voltage".split())
COMPOUND_CUES = frozenset("limit limits cap caps bound bounds".split())
NOUN_RIGHT = frozenset("of on for from to in at is was are were and or but . , ; :".split())
VERB_SUBJECT_HINTS = frozenset("we they you i he she it who which that can could will would may might should must "
                               "to not also often never always do does did didn't doesn't don't won't cannot can't "
                               "and or but then still usually sometimes rarely probably possibly likely perhaps "
                               "maybe potentially eventually clearly definitely already now generally typically".split())
SUBJECT_SHARE_BOUNDARY = re.compile(r"\b(?:and|but|or|yet|nor)\s*$", re.I)
RELATIVE_BOUNDARY = re.compile(r"\b(?:which|who|that|whom)\s*$", re.I)
COORDINATED_OBJECT = re.compile(r"^\s*,?\s*(?:and|as well as|plus)\s+(?:eventually|then|later|ultimately|finally|also|even)?\s*", re.I)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(text: str, start: int, end: int) -> dict[str, object]:
    return {"start": start, "end": end, "text": text[start:end]}


def _iou(a: Mapping[str, object], b: Mapping[str, object]) -> float:
    left, right = max(int(a["start"]), int(b["start"])), min(int(a["end"]), int(b["end"]))
    inter = max(0, right - left)
    union = int(a["end"]) - int(a["start"]) + int(b["end"]) - int(b["start"]) - inter
    return inter / union if union else 0.0


def _require_drop_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("drop_threshold must be a finite number in [0, 1]")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("drop_threshold must be a finite number in [0, 1]")
    return number


# ---- segmentation -------------------------------------------------------------

def sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) offsets of sentences."""
    out: list[tuple[int, int]] = []
    start = 0
    for m in SENTENCE_END.finditer(text):
        out.append((start, m.start()))
        start = m.end()
    out.append((start, len(text)))
    return [(s, e) for s, e in out if text[s:e].strip()]


def _is_boundary(text: str, m: re.Match) -> bool:
    """'that' is a boundary only as a relative pronoun: followed by an auxiliary or a cue verb."""
    if m.group().lower() != "that":
        return True
    if AUX_AFTER_THAT.match(text, m.end()):
        return True
    nxt = WORD.search(text, m.end())
    if nxt is None:
        return False
    return any(p.fullmatch(nxt.group()) for p, _t, _d, _c in CUES)


def _boundaries(text: str, start: int, end: int):
    for m in CLAUSE_BOUNDARY.finditer(text, start, end):
        if _is_boundary(text, m):
            yield m


def _next_boundary(text: str, start: int, end: int) -> int:
    for m in _boundaries(text, start, end):
        return m.start()
    return end


def _clause_bounds(text: str, s_start: int, s_end: int, cue_start: int, cue_end: int) -> tuple[int, int, int, int]:
    """Left argument region [l0, cue_start) and right region [cue_end, r1) inside the sentence."""
    l0 = s_start
    for m in _boundaries(text, s_start, cue_start):
        l0 = m.end()
    r1 = _next_boundary(text, cue_end, s_end)
    return l0, cue_start, cue_end, r1


def _argument(text: str, start: int, end: int, *, side: str) -> dict[str, object] | None:
    tokens = [(m.start() + start, m.end() + start, m.group()) for m in WORD.finditer(text[start:end])]
    while tokens and tokens[0][2].lower().strip("'’") in LEADING_DROP:
        tokens.pop(0)
    while tokens and tokens[-1][2].lower().strip("'’") in TRAILING_DROP:
        tokens.pop()
    if not tokens:
        return None
    if side == "left":
        tokens = tokens[-MAX_ARG_TOKENS:]
    else:
        tokens = tokens[:MAX_ARG_TOKENS]
    while tokens and tokens[0][2].lower().strip("'’") in LEADING_DROP:
        tokens.pop(0)
    if not tokens:
        return None
    return _span(text, tokens[0][0], tokens[-1][1])


def _verb_position(text: str, start: int, end: int) -> bool:
    """False when an ambiguous noun/verb cue is clearly a noun ("the speed limit")."""
    word = text[start:end].lower()
    if word not in NOUN_VERB_CUES:
        return True
    before = WORD.findall(text[max(0, start - 24):start])
    after = WORD.findall(text[end:end + 24])
    prev = before[-1].lower() if before else ""
    if prev in NOUN_LEFT:
        return False
    if word in COMPOUND_CUES and prev in COMPOUND_LEFT:
        return False
    # subject/verb agreement: a bare form ("limit", "cause") needs a plural or
    # pronoun/modal subject; an -s form needs a singular one.
    if prev and prev not in VERB_SUBJECT_HINTS:
        plural_subject = prev.endswith("s") and not prev.endswith("ss")
        if not word.endswith("s") and not plural_subject:
            return False
        if word.endswith("s") and plural_subject and prev not in ("this", "thus"):
            return False
    tail = text[end:end + 3]
    if tail[:1] in ".,;:" or (after and after[0].lower() in NOUN_RIGHT):
        return False
    if after and any(p.fullmatch(after[0]) for p, _t, _d, _c in CUES):
        return False                       # "demand depletes": the verb is the next word
    return True


def _nearest_preceding_node(nodes: dict[str, dict[str, object]], position: int, floor: int) -> str | None:
    best: tuple[int, str] | None = None
    for nid, nd in nodes.items():
        for sp in nd["spans"]:
            end = int(sp["end"])
            if floor <= end <= position and (best is None or end > best[0]):
                best = (end, nid)
    return best[1] if best else None


def _is_pronoun_only(label: str) -> bool:
    words = [w.lower() for w in WORD.findall(label)]
    return bool(words) and all(w in PRONOUN_ONLY for w in words)


def _assertion(text: str, cue_start: int, region_start: int) -> str:
    prefix = text[max(region_start, cue_start - 40): cue_start]
    return "negated" if NEGATORS.search(prefix) else "asserted"


def _modality(clause: str, direction: str) -> str:
    if direction == "cond" or CONDITIONAL.search(clause):
        return "conditional"
    if POSSIBLE.search(clause):
        return "possible"
    return "actual"


# ---- roles ----------------------------------------------------------------------

def _positional_role(node_id: str, relations: list[dict[str, object]]) -> str | None:
    out_types = [r["type"] for r in relations if r["source"] == node_id]
    in_types = [r["type"] for r in relations if r["target"] == node_id]
    if "prevents" in out_types:
        return "method"
    if "supports" in out_types:
        return "evidence"
    if "constrains" in out_types:
        return "constraint"
    if "requires" in in_types and "causes" not in out_types:
        return "resource"
    if "causes" in out_types and "causes" not in in_types and not in_types:
        return "problem"
    if "causes" in in_types and not out_types:
        return "outcome"
    if "causes" in in_types and "causes" in out_types:
        return "mechanism"
    if "part_of" in out_types:
        return "resource"
    return None


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "concept"


# ---- extractor ------------------------------------------------------------------

@dataclass(frozen=True)
class CueExtractor:
    drop_threshold: float = DROP_THRESHOLD

    def __post_init__(self) -> None:
        object.__setattr__(self, "drop_threshold", _require_drop_threshold(self.drop_threshold))

    def extract(self, context: str, *, source_id: str | None = None) -> ExtractionResult:
        if not isinstance(context, str) or not context.strip():
            raise ValueError("context must be a non-empty string")
        warnings: list[str] = []
        abstentions: list[str] = []
        scrubbed = _scrub(context)
        if scrubbed != context:
            warnings.append("contact details were removed from the context before extraction")
            context = scrubbed
        thought_id = make_thought_id(context, namespace=source_id or "")
        nodes: dict[str, dict[str, object]] = {}
        relations: list[dict[str, object]] = []
        stem_index: dict[tuple[str, ...], str] = {}

        def add_node(span: dict[str, object]) -> str | None:
            raw_label = str(span["text"]).strip()
            label = _scrub(raw_label)
            if label != raw_label:
                warnings.append("contact details removed from a node label")
            if not label or label == "[redacted]":
                abstentions.append("argument was only contact details; dropped")
                return None
            st = tuple(sorted(set(_stems(label))))
            if not st:
                abstentions.append(f"dropped node {label!r}: no content words")
                return None
            # 1) exact stem set  2) span overlap  3) containment (short in long)
            existing_id = stem_index.get(st)
            if existing_id is None:
                for nid, existing in nodes.items():
                    if any(_iou(span, item) >= IOU_MERGE for item in existing["spans"]):
                        existing_id = nid
                        break
            if existing_id is None:
                for key, nid in stem_index.items():
                    small, big = (st, key) if len(st) <= len(key) else (key, st)
                    if len(small) >= 1 and set(small) <= set(big) and len(big) - len(small) <= 1:
                        existing_id = nid
                        break
            if existing_id is not None:
                existing = nodes[existing_id]
                spans = list(existing["spans"])
                if span not in spans:
                    spans.append(span)
                    existing["spans"] = sorted(spans, key=lambda item: (int(item["start"]), int(item["end"])))
                stem_index.setdefault(st, existing_id)
                return existing_id
            node_id = make_node_id("state", spans=[span], namespace=thought_id)
            nodes[node_id] = {
                "id": node_id, "label": label, "role": "state", "spans": [span], "extract_conf": 0.55,
                "atomic": True, "assertion": "asserted", "modality": "actual",
            }
            stem_index[st] = node_id
            return node_id

        for s_start, s_end in sentences(context):
            consumed: list[tuple[int, int]] = []
            sentence_sources: list[str] = []
            sentence_rels: list[tuple[str, str, str]] = []   # (direction, src, dst)
            for pattern, rel_type, direction, conf in CUES:
                for match in pattern.finditer(context, s_start, s_end):
                    if any(a <= match.start() < b or a < match.end() <= b for a, b in consumed):
                        continue
                    if not _verb_position(context, match.start(), match.end()):
                        continue
                    if conf < self.drop_threshold:
                        abstentions.append(f"dropped {rel_type} cue {match.group(0)!r}")
                        continue
                    l0, l1, r0, r1 = _clause_bounds(context, s_start, s_end, match.start(), match.end())
                    if direction == "cond":
                        cond_end = r1
                        rest = context[cond_end:s_end]
                        cons = re.match(r"[,;:]?\s*(?:then\s+)?", rest)
                        c_start = cond_end + (cons.end() if cons else 0)
                        left = _argument(context, r0, cond_end, side="right")
                        right = _argument(context, c_start, _next_boundary(context, c_start, s_end), side="right")
                        if left is None or right is None or c_start >= s_end:
                            abstentions.append(f"incomplete conditional around {match.group(0)!r}")
                            continue
                        src = add_node(left)
                        dst = add_node(right)
                        if src is None or dst is None or src == dst:
                            abstentions.append(f"could not ground both ends of {match.group(0)!r}")
                            continue
                        self._emit(context, thought_id, relations, src, dst, rel_type, conf, match, l0, s_end, direction)
                        consumed.append((match.start(), match.end()))
                        sentence_sources.append(src)
                        continue
                    left = _argument(context, l0, l1, side="left")
                    right = _argument(context, r0, r1, side="right")
                    if right is None:
                        abstentions.append(f"incomplete arguments for cue {match.group(0)!r}")
                        continue
                    # subject resolution: relative clause / pronoun -> nearest preceding
                    # node; coordinated predicate ("X supports A and contradicts B") ->
                    # the previous relation's source in this sentence.
                    left_id: str | None = None
                    if left is None and direction == "rev" and not context[s_start:match.start()].strip():
                        # "Because X, Y." -> X causes Y: effect is the clause after the cause.
                        effect_start = r1
                        m_sep = re.match(r"[,;:]?\s*", context[effect_start:s_end])
                        e0 = effect_start + (m_sep.end() if m_sep else 0)
                        effect = _argument(context, e0, _next_boundary(context, e0, s_end), side="right")
                        if effect is None:
                            abstentions.append(f"incomplete arguments for cue {match.group(0)!r}")
                            continue
                        src = add_node(right)
                        dst = add_node(effect)
                        if src is None or dst is None or src == dst:
                            abstentions.append(f"could not ground both ends of {match.group(0)!r}")
                            continue
                        self._emit(context, thought_id, relations, src, dst, rel_type, conf, match, s_start, s_end, direction)
                        consumed.append((match.start(), match.end()))
                        sentence_sources.append(src)
                        sentence_rels.append((direction, src, dst))
                        continue
                    if left is None or _is_pronoun_only(str(left["text"])):
                        coordinated = bool(SUBJECT_SHARE_BOUNDARY.search(context[max(s_start, l1 - 8):l1]))
                        relative = bool(RELATIVE_BOUNDARY.search(context[max(s_start, l1 - 8):l1]))
                        if left is None and not coordinated and not relative and l0 == s_start:
                            # sentence-initial cue word with no subject: a participle or
                            # adjective ("Eroded trust ..."), not a predicate.
                            if direction == "fwd" and not context[s_start:match.start()].strip():
                                continue
                        if sentence_rels and sentence_rels[-1][0] == "rev" and (relative or left is not None or coordinated):
                            # "X because Y, which/and it leads to Z": the antecedent is
                            # the main-clause event X, i.e. the reversed relation's target.
                            left_id = sentence_rels[-1][2]
                        elif left is None and coordinated and sentence_sources:
                            left_id = sentence_sources[-1]
                        elif left is None and l0 > s_start and not sentence_sources:
                            # "Sleep debt accumulates and causes X" / "X is split, so Y":
                            # the subject is the sentence-initial clause.
                            head = _argument(context, s_start, _next_boundary(context, s_start, l0), side="right")
                            left_id = add_node(head) if head is not None else None
                        if left_id is None:
                            left_id = _nearest_preceding_node(nodes, match.start(), 0)
                        if left_id is None and left is None:
                            abstentions.append(f"incomplete arguments for cue {match.group(0)!r}")
                            continue
                    if left_id is not None:
                        other = add_node(right)
                        if other is None or other == left_id:
                            abstentions.append(f"could not ground {match.group(0)!r}")
                            continue
                        src, dst = (left_id, other) if direction == "fwd" else (other, left_id)
                    else:
                        src_span, dst_span = (left, right) if direction == "fwd" else (right, left)
                        src = add_node(src_span)
                        dst = add_node(dst_span)
                        if src is None or dst is None or src == dst:
                            abstentions.append(f"could not ground both ends of {match.group(0)!r}")
                            continue
                    self._emit(context, thought_id, relations, src, dst, rel_type, conf, match, l0, s_end, direction)
                    consumed.append((match.start(), match.end()))
                    sentence_sources.append(src)
                    sentence_rels.append((direction, src, dst))
                    # coordinated object: "leads to A and eventually B" / "consists of A and B"
                    if direction in ("fwd", "rev"):
                        tail = context[int(right["end"]):s_end]
                        coord = COORDINATED_OBJECT.match(tail)
                        if coord:
                            c0 = int(right["end"]) + coord.end()
                            c_bound = CLAUSE_BOUNDARY.search(context, c0, s_end)
                            c1 = c_bound.start() if c_bound else s_end
                            if not any(p.search(context[c0:c1]) for p, _t, _d, _c in CUES):
                                extra = _argument(context, c0, c1, side="right")
                                if extra is not None:
                                    extra_id = add_node(extra)
                                    if extra_id is not None and extra_id not in (src, dst):
                                        e_src, e_dst = (src, extra_id) if direction == "fwd" else (extra_id, dst)
                                        self._emit(context, thought_id, relations, e_src, e_dst, rel_type,
                                                   round(conf * 0.9, 3), match, l0, s_end, direction)

        # roles: lexicon first, position second, default third
        for nid, nd in nodes.items():
            hint = _role_hint(str(nd["label"]))
            positional = _positional_role(nid, relations)
            if hint:
                nd["role"], nd["extract_conf"] = hint, 0.8
            elif positional:
                nd["role"], nd["extract_conf"] = positional, 0.65
            else:
                nd["role"], nd["extract_conf"] = "state", 0.55
            if float(nd["extract_conf"]) < self.drop_threshold:
                abstentions.append(f"dropped node {nd['label']!r} below threshold")
        kept_ids = {nid for nid, nd in nodes.items() if float(nd["extract_conf"]) >= self.drop_threshold}
        relations = [r for r in relations if r["source"] in kept_ids and r["target"] in kept_ids]
        node_list = [nd for nid, nd in nodes.items() if nid in kept_ids]
        # node ids are derived from spans + role; recompute now that roles are final
        rename: dict[str, str] = {}
        for nd in node_list:
            new_id = make_node_id(str(nd["role"]), spans=list(nd["spans"]), namespace=thought_id)
            rename[str(nd["id"])] = new_id
            nd["id"] = new_id
        for r in relations:
            r["source"], r["target"] = rename[str(r["source"])], rename[str(r["target"])]
            r["id"] = make_relation_id(str(r["source"]), str(r["target"]), str(r["type"]), spans=list(r["spans"]),
                                       assertion=str(r["assertion"]), modality=str(r["modality"]), namespace=thought_id)
        # dedupe identical relations (same endpoints/type/assertion/modality)
        seen: set[tuple] = set()
        deduped = []
        for r in relations:
            key = (r["source"], r["target"], r["type"], r["assertion"], r["modality"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        relations = deduped
        for r in relations:
            if r["type"] == "requires":
                dst_node = next(nd for nd in node_list if nd["id"] == r["target"])
                src_node = next(nd for nd in node_list if nd["id"] == r["source"])
                ref = f"local:{_slug(str(dst_node['label']))}"
                dst_node.setdefault("knowledge", {"about": [], "requires": []})
                if not any(x["id"] == ref for x in dst_node["knowledge"]["about"]):
                    dst_node["knowledge"]["about"].append({"id": ref, "conf": max(float(r["extract_conf"]), 0.5), "via": "extractor"})
                src_node.setdefault("knowledge", {"about": [], "requires": []})
                if not any(x["id"] == ref for x in src_node["knowledge"]["requires"]):
                    src_node["knowledge"]["requires"].append({"id": ref, "conf": max(float(r["extract_conf"]), 0.5), "via": "extractor"})
        if not relations:
            abstentions.append("no explicit relation cues; implicit structure not emitted")

        raw = {
            "schema_version": "thought-dna/0.1",
            "thought_id": thought_id,
            "source": {"text": context, "sha256": _sha256(context)},
            "provenance": {"kind": "extracted", "extractor": {"id": EXTRACTOR_ID, "version": EXTRACTOR_VERSION}},
            "nodes": node_list,
            "relations": relations,
        }
        graph = ThoughtGraph.from_dict(raw)
        config = ConfigRef(
            component="extraction",
            component_version=EXTRACTOR_VERSION,
            config_hash=_sha256(f"{EXTRACTOR_ID}:{EXTRACTOR_VERSION}:{self.drop_threshold}"),
        )
        return ExtractionResult(graph=graph, config=config, warnings=tuple(warnings), abstentions=tuple(abstentions))

    @staticmethod
    def _emit(context, thought_id, relations, src, dst, rel_type, conf, match, region_start, s_end, direction):
        cue = _span(context, match.start(), match.end())
        assertion = _assertion(context, match.start(), region_start)
        clause = context[region_start:s_end]
        modality = _modality(clause, direction)
        relations.append({
            "id": "pending", "source": src, "target": dst, "type": rel_type, "extract_conf": conf,
            "spans": [cue], "cue": cue, "assertion": assertion, "modality": modality,
        })


class ManualIngest:
    """Non-LLM bypass: the same validator/model, extractor=null."""

    def ingest(self, payload: dict) -> ThoughtGraph:
        data = dict(payload)
        provenance = dict(data.get("provenance") or {})
        provenance.setdefault("kind", "manual")
        provenance["extractor"] = None
        data["provenance"] = provenance
        graph = ThoughtGraph.from_dict(data)
        validate_thought(graph.to_dict())
        return graph


# ---- evaluation helpers (unchanged contract) ---------------------------------------

def _node_signature(node: Node) -> tuple[object, ...]:
    spans = tuple(sorted((span.start, span.end, span.text) for span in node.spans))
    return (node.role, spans, node.assertion, node.modality)


def _edge_signature(graph: ThoughtGraph, relation: Relation) -> tuple[object, ...] | None:
    by_id = {node.id: node for node in graph.nodes}
    source = by_id.get(relation.source)
    target = by_id.get(relation.target)
    if source is None or target is None:
        return None
    return (_node_signature(source), relation.type, _node_signature(target), relation.assertion, relation.modality)


def _f1(predicted: set[object], gold: set[object]) -> float:
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0
    overlap = len(predicted & gold)
    precision = overlap / len(predicted)
    recall = overlap / len(gold)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def repeat_extraction_f1(first: ThoughtGraph, second: ThoughtGraph) -> dict[str, float]:
    """Node/edge F1 after span/role/assertion/modality alignment, not local IDs."""
    a_nodes = {_node_signature(node) for node in first.nodes}
    b_nodes = {_node_signature(node) for node in second.nodes}
    a_edges = {sig for rel in first.relations if (sig := _edge_signature(first, rel)) is not None}
    b_edges = {sig for rel in second.relations if (sig := _edge_signature(second, rel)) is not None}
    return {"node_f1": _f1(a_nodes, b_nodes), "edge_f1": _f1(a_edges, b_edges)}


def frozen_v0_1_predictions(extractor: CueExtractor | None = None, *, path: Path = FROZEN_EXTRACTION_RUNS) -> list[dict[str, object]]:
    """Adapter: CueExtractor over the frozen 16 extraction observations."""
    extractor = extractor or CueExtractor()
    predictions: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        case_id = str(record["extraction_case_id"])
        text = str(record["input"]["text"])
        graph = extractor.extract(text, source_id=case_id).graph
        predictions.append({"extraction_case_id": case_id, "thought_dna": graph.to_dict()})
    return predictions


def frozen_v0_1_coverage(predictions: list[dict[str, object]]) -> dict[str, float | int]:
    """Honest coverage for cue-only extraction. Empty graphs are not hidden."""
    node_counts = [len(item["thought_dna"]["nodes"]) for item in predictions]
    rel_counts = [len(item["thought_dna"]["relations"]) for item in predictions]
    n = len(predictions) or 1
    nonempty = sum(1 for nodes, rels in zip(node_counts, rel_counts) if nodes or rels)
    return {
        "n_records": len(predictions),
        "mean_nodes": sum(node_counts) / n,
        "mean_relations": sum(rel_counts) / n,
        "nonempty_graph_rate": nonempty / n,
        "total_nodes": sum(node_counts),
        "total_relations": sum(rel_counts),
    }
