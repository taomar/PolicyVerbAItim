"""Detect text that an extractor read out of order, and report it. Never fix it.

Some documents set two columns side by side. An extractor that reads across the
page instead of down them produces a single string with the two columns' letters
alternating inside individual tokens — `O\u0631n\u062ee\u0623` is the Latin word
"One" zipped together with an Arabic one. Both texts are entirely present; only
their order is wrong.

DETECTION, NOT REPAIR
---------------------
Nothing here alters, reorders, drops or rewrites a single character. The stored
text stays exactly as the extractor produced it, and this module's whole output
is a count and a location.

That is a deliberate limit, and it is the same rule `detect_display_glyphs`
follows for the same reason: a stored value that reads oddly is a defect a
reviewer can see and weigh, while a stored value silently rewritten into
something the document does not literally contain is a defect nobody can see.
This product does not alter the words it attributes to a source. The remedy for
interleaved extraction is to correct the original PDF or DOCX and upload a new
version — which is what the diagnostic tells the reader to do.

ONE IMPLEMENTATION
------------------
The same functions answer for a document being loaded through the portal and for
a policy index being rebuilt, so the two paths cannot drift into disagreeing
about whether a given text is damaged.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

__all__ = [
    "INTERLEAVED_TEXT_CODE",
    "interleaved_tokens",
    "is_interleaved",
]

#: The stable code carried by every diagnostic this detection raises, so a
#: reader, a test and a support conversation can all name the same finding
#: without depending on wording that may be translated or reworded later.
INTERLEAVED_TEXT_CODE: Final[str] = "interleaved_text_not_reading_order"

#: A whitespace-delimited token.
_TOKEN: Final[re.Pattern[str]] = re.compile(r"\S+")

#: A token needs at least this many letters before an alternation between two
#: scripts is evidence of interleaving rather than an ordinary borrowing. Two
#: letters cannot show a pattern, and a borrowed proper noun is usually a run,
#: not an alternation.
_MIN_INTERLEAVED_LETTERS: Final[int] = 4


def _script_of(char: str) -> str | None:
    """Which writing system a character belongs to, or ``None`` if it is neither.

    Only letters carry a script for this purpose. Digits, punctuation and marks
    are shared between writing systems, so they say nothing about which strand a
    character came from and must not be allowed to look like evidence.

    Names come from the Unicode character database rather than a hand-written
    range table, so a script this module has never been shown behaves the same
    way as the ones it has. There is no language list and no direction check
    anywhere in this file, which is what keeps it a statement about codepoints
    rather than about one corpus.
    """

    if not char.isalpha():
        return None
    try:
        name = unicodedata.name(char)
    except ValueError:
        return None
    # The first word of a Unicode letter's name is its script: "ARABIC LETTER
    # BEH", "LATIN SMALL LETTER A", "CYRILLIC CAPITAL LETTER DE".
    return name.split(" ", 1)[0]


def is_interleaved(token: str) -> bool:
    """Whether one token carries letters of two scripts alternating inside it.

    A token is not damaged merely for holding two scripts — a quoted foreign
    term beside its translation is ordinary, and so is a unit symbol. What marks
    interleaving is that the scripts *alternate*: the reading order swaps back
    and forth rather than changing once at a boundary between two words.

    One switch is a boundary between two words that were run together, which is
    a different and much commoner thing. Two or more is a strand crossing
    itself, which is what reading across columns does.
    """

    scripts = [script for script in map(_script_of, token) if script is not None]
    if len(scripts) < _MIN_INTERLEAVED_LETTERS:
        return False
    if len(set(scripts)) < 2:
        return False
    switches = sum(1 for before, after in zip(scripts, scripts[1:]) if before != after)
    return switches >= 2


def interleaved_tokens(text: str) -> tuple[str, ...]:
    """Every token in ``text`` that shows the interleaving pattern.

    Empty for text that is clean, which is nearly all text, so a caller can ask
    of everything and act only where there is something to say.
    """

    return tuple(token for token in _TOKEN.findall(text) if is_interleaved(token))
