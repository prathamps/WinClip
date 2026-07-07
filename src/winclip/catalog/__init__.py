"""Static snippet catalogs: emoji, kaomoji, and symbols.

Pure data, standard library only — usable from any layer. Each catalog
is an ordered mapping of category name to a list of ``(text, name)``
pairs, where ``name`` is a short lowercase description used for search.
"""

from .emoji import EMOJI
from .kaomoji import KAOMOJI
from .symbols import SYMBOLS

Catalog = dict[str, list[tuple[str, str]]]

__all__ = ["EMOJI", "KAOMOJI", "SYMBOLS", "Catalog"]
