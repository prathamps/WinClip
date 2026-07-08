"""Sanity checks over the static snippet catalogs."""

import pytest

from winclip.catalog import EMOJI, KAOMOJI, SYMBOLS

CATALOGS = {"emoji": EMOJI, "kaomoji": KAOMOJI, "symbols": SYMBOLS}


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_catalog_shape(name):
    catalog = CATALOGS[name]
    assert catalog, f"{name} catalog is empty"
    for category, entries in catalog.items():
        assert entries, f"{name}/{category} is empty"
        for text, description in entries:
            assert text.strip(), f"blank snippet in {name}/{category}"
            assert description.strip(), f"{text!r} has no searchable name"
            assert description == description.lower(), (
                f"{text!r} name should be lowercase for search"
            )


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_no_duplicate_snippets_within_a_catalog(name):
    seen: set[str] = set()
    duplicates = []
    for entries in CATALOGS[name].values():
        for text, _ in entries:
            if text in seen:
                duplicates.append(text)
            seen.add(text)
    assert not duplicates, f"duplicates in {name}: {duplicates}"


def test_catalogs_are_reasonably_sized():
    total = sum(len(v) for v in EMOJI.values())
    assert total >= 250, "emoji catalog unexpectedly small"
    assert sum(len(v) for v in KAOMOJI.values()) >= 50
    assert sum(len(v) for v in SYMBOLS.values()) >= 120
