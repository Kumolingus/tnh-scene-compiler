"""Regex fragments shared by the per-character extractors."""

from __future__ import annotations

import re

_TAG = r"[A-Z][A-Za-z0-9]+"


def character_attribute(attribute: str, flat: str | None = None) -> str:
    """A regex fragment matching a character's ``define`` target, in either TNH layout.

    TNH 0.9c.beta.28 keeps a character's data in its named store
    (``define CHARACTERS.Rogue.faces["smile"]``); earlier builds, and a mod
    written against them, in a default-store name
    (``define Rogue_faces["smile"]``).

    attribute -- the attribute of the named store (``faces``)
    flat      -- the suffix of the default-store name, when it differs
                 (``all_Clothes`` for ``clothes``); ``attribute`` otherwise

    Returns a non-capturing group that captures the character tag in
    ``namespaced`` or ``flat``; :func:`character_of` reads whichever matched.
    """
    return (
        rf"(?:CHARACTERS\.(?P<namespaced>{_TAG})\.{re.escape(attribute)}"
        rf"|(?P<flat>{_TAG})_{re.escape(flat or attribute)})"
    )


def character_of(match: re.Match[str]) -> str:
    """The character tag a :func:`character_attribute` fragment captured."""
    groups = match.groupdict()
    return groups.get("namespaced") or groups["flat"]
