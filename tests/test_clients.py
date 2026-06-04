"""Tests for the API clients' network-vs-empty distinction.

No real network calls are made: urllib / the record loader are monkeypatched so
that "server reachable but no matches" yields an empty list while "unreachable"
raises SearchError.
"""

from __future__ import annotations

import urllib.error

import pytest

import arasaac
import tegnbanken


# ── arasaac ──────────────────────────────────────────────────────────────────


def test_arasaac_raises_when_both_languages_fail(monkeypatch):
    def boom(query, language, limit):
        raise arasaac.SearchError("offline")

    monkeypatch.setattr(arasaac, "_search_lang", boom)
    with pytest.raises(arasaac.SearchError):
        arasaac.search("eple")


def test_arasaac_empty_when_reachable_but_no_matches(monkeypatch):
    monkeypatch.setattr(arasaac, "_search_lang", lambda q, lang, limit: [])
    assert arasaac.search("zzznotaword") == []


def test_arasaac_partial_outage_returns_what_it_found(monkeypatch):
    def one_lang(query, language, limit):
        if language == "nb":
            return [{"id": 1, "label": "eple", "thumb_bytes": None}]
        raise arasaac.SearchError("en endpoint down")

    monkeypatch.setattr(arasaac, "_search_lang", one_lang)
    results = arasaac.search("eple")
    assert [r["id"] for r in results] == [1]


def test_arasaac_404_is_treated_as_no_matches(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(arasaac.urllib.request, "urlopen", fake_urlopen)
    # 404 from both languages → empty list, not an error.
    assert arasaac.search("eple") == []


def test_arasaac_network_error_raises(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(arasaac.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(arasaac.SearchError):
        arasaac.search("eple")


# ── tegnbanken ───────────────────────────────────────────────────────────────


def test_tegnbanken_search_propagates_load_error(monkeypatch):
    def boom():
        raise tegnbanken.SearchError("offline, no cache")

    monkeypatch.setattr(tegnbanken, "_load_records", boom)
    with pytest.raises(tegnbanken.SearchError):
        tegnbanken.search("bade")


def test_tegnbanken_search_filters_and_prefix_boosts(monkeypatch):
    records = [
        {"word": "badebukse", "foto": "a.jpg", "la_hend": ""},
        {"word": "morgenbad", "foto": "b.jpg", "la_hend": ""},
        {"word": "sove", "foto": "c.jpg", "la_hend": ""},
    ]
    monkeypatch.setattr(tegnbanken, "_load_records", lambda: records)
    results = tegnbanken.search("bad")
    words = [r["word"] for r in results]
    assert words == ["badebukse", "morgenbad"]  # prefix match first, "sove" excluded


def test_tegnbanken_empty_when_no_match(monkeypatch):
    monkeypatch.setattr(tegnbanken, "_load_records", lambda: [])
    assert tegnbanken.search("bade") == []
