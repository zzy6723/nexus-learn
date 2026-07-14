#!/usr/bin/env python3
"""Shared conservative label matching for Knowledge Object evaluation."""

from __future__ import annotations

import re
import unicodedata


NAME_MATCHING_NORMALIZATION_VERSION = "predicted_ko_name_matching_v0_1"

DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
})
APOSTROPHE_TRANSLATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201b": "'",
    "`": "'",
    "\u00b4": "'",
})


def name_matching_key(value: str) -> str:
    """Return the Entity evaluator's conservative comparison key."""

    if not isinstance(value, str):
        raise TypeError("name matching input must be a string")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.translate(APOSTROPHE_TRANSLATION)
    normalized = normalized.translate(DASH_TRANSLATION)
    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized.casefold()
