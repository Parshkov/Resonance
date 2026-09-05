"""Stemmers, stdlib-only and deterministic. No external models.

Label comparison has to be invariant to inflection, or "accumulates",
"accumulation" and "accumulating" are three different ideas. Porter (1980)
does that for English.

Russian needs its own, and needs it more: English inflects lightly and a
handful of surface forms in the lexicon would nearly cover it, while Russian
inflects heavily enough that listing forms is hopeless — "накопление,
накопления, накоплению, накоплений, накоплениями" and so on for every entry.
`stem_ru` is the Snowball Russian algorithm, and `stem` dispatches on the
script of the word, so a Cyrillic label is never fed to the English rules and
an English label is never fed to the Russian ones. The two alphabets do not
overlap, so adding one cannot change the other's result.
"""

from __future__ import annotations

from functools import lru_cache

_VOWELS = frozenset("aeiou")
RUSSIAN_VOWELS = frozenset("аеиоуыэюя")

_PERFECTIVE_GERUND_1 = ("вшись", "вшийся", "вши", "вша", "в")          # after а/я
_PERFECTIVE_GERUND_2 = ("ившись", "ывшись", "ивши", "ывши", "ив", "ыв")
_ADJECTIVE = ("ее", "ие", "ые", "ое", "ими", "ыми", "ей", "ий", "ый", "ой",
              "ем", "им", "ым", "ом", "его", "ого", "ему", "ому", "их", "ых",
              "ую", "юю", "ая", "яя", "ою", "ею")
_PARTICIPLE_1 = ("ем", "нн", "вш", "ющ", "щ")                          # after а/я
_PARTICIPLE_2 = ("ивш", "ывш", "ующ")
_REFLEXIVE = ("ся", "сь")
_VERB_1 = ("ла", "на", "ете", "йте", "ли", "й", "л", "ем", "н", "ло", "но",
           "ет", "ют", "ны", "ть", "ешь", "нно")                        # after а/я
_VERB_2 = ("ила", "ыла", "ена", "ейте", "уйте", "ите", "или", "ыли", "ей",
           "уй", "ил", "ыл", "им", "ым", "ен", "ило", "ыло", "ено", "ят",
           "ует", "уют", "ит", "ыт", "ены", "ить", "ыть", "ишь", "ую", "ю")
_NOUN = ("а", "ев", "ов", "ие", "ье", "е", "иями", "ями", "ами", "еи", "ии",
         "и", "ией", "ей", "ой", "ий", "й", "иям", "ям", "ием", "ем", "ам",
         "ом", "о", "у", "ах", "иях", "ях", "ы", "ь", "ию", "ью", "ю", "ия",
         "ья", "я")
_SUPERLATIVE = ("ейш", "ейше")
_DERIVATIONAL = ("ост", "ость")


def _regions(word: str) -> tuple[int, int, int]:
    """RV, R1, R2 start indices, per the Snowball Russian definition."""
    rv = len(word)
    for index, letter in enumerate(word):
        if letter in RUSSIAN_VOWELS:
            rv = index + 1
            break
    r1 = len(word)
    for index in range(1, len(word)):
        if word[index] not in RUSSIAN_VOWELS and word[index - 1] in RUSSIAN_VOWELS:
            r1 = index + 1
            break
    r2 = len(word)
    for index in range(r1 + 1, len(word)):
        if word[index] not in RUSSIAN_VOWELS and word[index - 1] in RUSSIAN_VOWELS:
            r2 = index + 1
            break
    return rv, r1, r2


def _cut(word: str, region: int, endings, *, preceded_by=()) -> tuple[str, bool]:
    for ending in sorted(endings, key=len, reverse=True):
        if not word.endswith(ending):
            continue
        cut_at = len(word) - len(ending)
        if cut_at < region:
            continue
        if preceded_by:
            if cut_at == 0 or word[cut_at - 1] not in preceded_by:
                continue
            return word[:cut_at - 1] + word[cut_at - 1], True  # keep the а/я
        return word[:cut_at], True
    return word, False


def stem_ru(word: str) -> str:
    w = word.lower().replace("ё", "е")
    rv, _r1, r2 = _regions(w)
    if rv >= len(w):
        return w

    # Step 1
    w2, cut = _cut(w, rv, _PERFECTIVE_GERUND_2)
    if not cut:
        w2, cut = _cut(w, rv, _PERFECTIVE_GERUND_1, preceded_by="ая")
    if cut:
        w = w2
    else:
        w, _ = _cut(w, rv, _REFLEXIVE)
        w2, cut = _cut(w, rv, _ADJECTIVE)
        if cut:
            w = w2
            w3, participle = _cut(w, rv, _PARTICIPLE_2)
            if not participle:
                w3, participle = _cut(w, rv, _PARTICIPLE_1, preceded_by="ая")
            if participle:
                w = w3
        else:
            w2, cut = _cut(w, rv, _VERB_2)
            if not cut:
                w2, cut = _cut(w, rv, _VERB_1, preceded_by="ая")
            if cut:
                w = w2
            else:
                w, _ = _cut(w, rv, _NOUN)

    # Step 2
    rv, _r1, r2 = _regions(w)
    if w.endswith("и") and len(w) - 1 >= rv:
        w = w[:-1]

    # Step 3
    rv, _r1, r2 = _regions(w)
    w, _ = _cut(w, r2, _DERIVATIONAL)

    # Step 4
    rv, _r1, _r2 = _regions(w)
    if w.endswith("нн"):
        w = w[:-1]
    else:
        w2, cut = _cut(w, rv, _SUPERLATIVE)
        if cut:
            w = w2
            if w.endswith("нн"):
                w = w[:-1]
        elif w.endswith("ь"):
            w = w[:-1]
    return w



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


def _is_cyrillic(word: str) -> bool:
    return any("\u0400" <= ch <= "\u04ff" for ch in word)


@lru_cache(maxsize=65536)
def stem(word: str) -> str:
    if _is_cyrillic(word):
        return stem_ru(word)
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
