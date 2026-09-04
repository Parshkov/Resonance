"""Porter stemmer (1980 algorithm), stdlib-only and deterministic.

Used to make label comparison invariant to inflection ("accumulates",
"accumulation", "accumulating" -> "accumul"). No external models.
"""

from __future__ import annotations

from functools import lru_cache

_VOWELS = frozenset("aeiou")


def _is_consonant(word: str, i: int) -> bool:
    ch = word[i]
    if ch in _VOWELS:
        return False
    if ch == "y":
        return i == 0 or not _is_consonant(word, i - 1)
    return True


def _measure(stem: str) -> int:
    """Count VC sequences: [C](VC){m}[V]."""
    m = 0
    i = 0
    n = len(stem)
    while i < n and _is_consonant(stem, i):
        i += 1
    while i < n:
        while i < n and not _is_consonant(stem, i):
            i += 1
        if i >= n:
            break
        while i < n and _is_consonant(stem, i):
            i += 1
        m += 1
    return m


def _contains_vowel(stem: str) -> bool:
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _ends_double_consonant(word: str) -> bool:
    return len(word) >= 2 and word[-1] == word[-2] and _is_consonant(word, len(word) - 1)


def _cvc(word: str) -> bool:
    if len(word) < 3:
        return False
    n = len(word)
    if not (_is_consonant(word, n - 1) and not _is_consonant(word, n - 2) and _is_consonant(word, n - 3)):
        return False
    return word[-1] not in "wxy"


def _replace(word: str, suffix: str, repl: str, condition) -> tuple[str, bool]:
    if not word.endswith(suffix):
        return word, False
    stem = word[: len(word) - len(suffix)]
    if condition(stem):
        return stem + repl, True
    return word, True


@lru_cache(maxsize=65536)
def stem(word: str) -> str:
    w = word.lower()
    if len(w) <= 2:
        return w

    # Step 1a
    if w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ies"):
        w = w[:-2]
    elif w.endswith("ss"):
        pass
    elif w.endswith("s"):
        w = w[:-1]

    # Step 1b
    done = False
    if w.endswith("eed"):
        stem_ = w[:-3]
        if _measure(stem_) > 0:
            w = w[:-1]
        done = True
    if not done:
        for suffix in ("ed", "ing"):
            if w.endswith(suffix):
                stem_ = w[: -len(suffix)]
                if _contains_vowel(stem_):
                    w = stem_
                    if w.endswith(("at", "bl", "iz")):
                        w += "e"
                    elif _ends_double_consonant(w) and w[-1] not in "lsz":
                        w = w[:-1]
                    elif _measure(w) == 1 and _cvc(w):
                        w += "e"
                break

    # Step 1c
    if w.endswith("y") and _contains_vowel(w[:-1]):
        w = w[:-1] + "i"

    # Step 2
    step2 = (
        ("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"),
        ("izer", "ize"), ("abli", "able"), ("alli", "al"), ("entli", "ent"),
        ("eli", "e"), ("ousli", "ous"), ("ization", "ize"), ("ation", "ate"),
        ("ator", "ate"), ("alism", "al"), ("iveness", "ive"), ("fulness", "ful"),
        ("ousness", "ous"), ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"),
    )
    for suffix, repl in step2:
        if w.endswith(suffix):
            stem_ = w[: -len(suffix)]
            if _measure(stem_) > 0:
                w = stem_ + repl
            break

    # Step 3
    step3 = (
        ("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"),
        ("ical", "ic"), ("ful", ""), ("ness", ""),
    )
    for suffix, repl in step3:
        if w.endswith(suffix):
            stem_ = w[: -len(suffix)]
            if _measure(stem_) > 0:
                w = stem_ + repl
            break

    # Step 4
    step4 = (
        "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement", "ment",
        "ent", "ion", "ou", "ism", "ate", "iti", "ous", "ive", "ize",
    )
    for suffix in step4:
        if w.endswith(suffix):
            stem_ = w[: -len(suffix)]
            if _measure(stem_) > 1:
                if suffix == "ion":
                    if stem_ and stem_[-1] in "st":
                        w = stem_
                else:
                    w = stem_
            break

    # Step 5a
    if w.endswith("e"):
        stem_ = w[:-1]
        m = _measure(stem_)
        if m > 1 or (m == 1 and not _cvc(stem_)):
            w = stem_
    # Step 5b
    if _measure(w) > 1 and _ends_double_consonant(w) and w.endswith("l"):
        w = w[:-1]
    return w
