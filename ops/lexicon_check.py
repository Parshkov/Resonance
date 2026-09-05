"""Prove a lexicon change is additive, and measure what it bought.

The lexicon is versioned because changing it changes fingerprint and config
hashes, which changes every score in the product. So a change to it is only
safe if it can be shown to leave existing behaviour exactly where it was.

Adding terms in an alphabet the existing terms do not use should be provably
inert for them: a Cyrillic token can never match an English stem, and vice
versa. This asserts that rather than assuming it, and then reports what the
new terms actually made possible.

    python3 ops/lexicon_check.py            # check English is untouched
    python3 ops/lexicon_check.py --russian  # also report Russian coverage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.semantics import CONCEPTS  # noqa: E402
from src.semantics.lexicon import DOMAIN_PREFIX  # noqa: E402
from src.semantics.similarity import abstract_concepts, concepts  # noqa: E402

# Labels drawn from the frozen benchmark's vocabulary and the product's own
# examples: if the concepts these resolve to ever move, English scoring moved.
ENGLISH_PROBES = (
    "delivery pressure", "skipped review", "rework", "protected slack week",
    "retry storm", "delivery queue", "panic buying", "shortage rumour",
    "empty shelves", "salt accumulation", "root damage", "fallow season",
    "synchronized retries", "partial outage", "amplified load", "backlog",
    "thermal runaway", "heat buildup", "cooling failure", "battery",
    "trust erosion", "technical debt", "attention fatigue", "feedback loop",
)

RUSSIAN_PROBES = {
    "накопление соли": "ACCUMULATION",
    "истощение почвы": "DEPLETION",
    "давление сроков": "STRESS",
    "узкое место": "BOTTLENECK",
    "задержка поставки": "DELAY",
    "перегрузка очереди": "LOAD",
    "каскадный отказ": "CASCADE",
    "потеря доверия": "TRUST",
    "технический долг": "DEBT",
    "повторные попытки": "RETRY",
    "нехватка ресурсов": "SCARCITY",
    "обратная связь": "FEEDBACK",
    "выгорание команды": "FATIGUE",
    "ограничение пропускной способности": "CAPACITY",
    "ухудшение качества": "DEGRADATION",
}


def is_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def check_alphabets_do_not_mix() -> list[str]:
    """No concept may be reachable from both alphabets by the same term."""
    problems = []
    for name, (_hint, terms) in CONCEPTS.items():
        for term in terms:
            letters = [ch for ch in term if ch.isalpha()]
            if letters and any(is_cyrillic(ch) for ch in letters) and \
                    any(not is_cyrillic(ch) for ch in letters):
                problems.append(f"{name}: mixed-alphabet term {term!r}")
    return problems


def english_signature() -> dict[str, tuple[str, ...]]:
    return {label: tuple(sorted(concepts(label))) for label in ENGLISH_PROBES}


def report_russian() -> tuple[int, list[str]]:
    missing = []
    for label, wanted in RUSSIAN_PROBES.items():
        found = abstract_concepts(label)
        if wanted not in found:
            missing.append(f"{label!r} -> {sorted(found) or 'nothing'} (wanted {wanted})")
    return len(RUSSIAN_PROBES) - len(missing), missing


DEFAULT_BASELINE = Path(__file__).resolve().parent / "english_lexicon.baseline"
"""The English signature as it stood before any other language was added.

Without it, "English is unchanged" is a claim rather than a check: the run
prints a healthy line and verifies nothing. It is recorded from the commit
before the Russian work began, so a regression in either direction shows up
as a diff and not as a silence.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--russian", action="store_true",
                        help="report which Russian probes resolve")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE,
                        help="a signature file written by --write-baseline")
    parser.add_argument("--write-baseline", type=Path,
                        help="record the current English signature and exit")
    args = parser.parse_args()

    signature = english_signature()
    if args.write_baseline:
        args.write_baseline.write_text(
            "\n".join(f"{k}\t{','.join(v)}" for k, v in sorted(signature.items())),
            encoding="utf-8")
        print(f"baseline written to {args.write_baseline}")
        return 0

    failures = check_alphabets_do_not_mix()
    for problem in failures:
        print(f"MIXED ALPHABET: {problem}")

    if args.baseline and not args.baseline.exists():
        failures.append(f"no baseline at {args.baseline}; English cannot be checked")
        print(f"MISSING BASELINE: {args.baseline}")
    elif args.baseline:
        recorded = {}
        for line in args.baseline.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                label, joined = line.split("\t", 1)
                recorded[label] = tuple(x for x in joined.split(",") if x)
        for label, before in sorted(recorded.items()):
            after = signature.get(label, ())
            if before != after:
                failures.append(f"ENGLISH MOVED: {label!r}\n    was {before}\n    now {after}")
                print(failures[-1])
        if not failures:
            print(f"English unchanged across {len(recorded)} probes.")

    abstract = [k for k in CONCEPTS if not k.startswith(DOMAIN_PREFIX)]
    cyrillic_terms = sum(1 for _n, (_h, terms) in CONCEPTS.items()
                         for t in terms if is_cyrillic(t))
    covered = sum(1 for name in abstract
                  if any(is_cyrillic(t) for t in CONCEPTS[name][1]))
    print(f"abstract classes: {len(abstract)}  with Russian terms: {covered}  "
          f"Cyrillic terms: {cyrillic_terms}")

    if args.russian:
        resolved, missing = report_russian()
        print(f"Russian probes resolving: {resolved}/{len(RUSSIAN_PROBES)}")
        for line in missing:
            print(f"  MISSING {line}")
        if missing:
            failures.append("russian probes unresolved")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
