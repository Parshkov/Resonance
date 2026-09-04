"""Deterministic PII scrubbing for node labels and free text.

Extraction turns text windows into labels that other people will see, so the
label layer must never carry contact details. This is a conservative
regex-only scrub: emails, URLs, phone numbers, handles, long digit runs.
Person names are left to the caller's consent flow (they are not detectable
without a model and false positives would destroy domain terms).
"""

from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
URL = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
HANDLE = re.compile(r"(?<![\w])@[\w.]{2,}")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
LONG_DIGITS = re.compile(r"\b\d{9,}\b")
SCRUB_VERSION = "resonance-pii-scrub/0.1"


def scrub(text: str, replacement: str = "[redacted]") -> str:
    out = EMAIL.sub(replacement, text)
    out = URL.sub(replacement, out)
    out = HANDLE.sub(replacement, out)
    out = PHONE.sub(replacement, out)
    out = LONG_DIGITS.sub(replacement, out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def contains_pii(text: str) -> bool:
    return any(p.search(text) for p in (EMAIL, URL, HANDLE, PHONE, LONG_DIGITS))
