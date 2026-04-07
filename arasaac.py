"""ARASAAC pictogram API client.

Searches in both Norwegian (nb) and English (en).  Labels are always returned
in Norwegian — English-only matches have their Norwegian label resolved via a
parallel API lookup before being returned.  No API key required.

License note: ARASAAC pictograms are CC BY-NC-SA 4.0.
Attribution: Sergio Palao / ARASAAC (http://www.arasaac.org),
             Government of Aragon (Spain).
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_API_BASE = "https://api.arasaac.org/v1"
_CDN_BASE = "https://static.arasaac.org/pictograms"
_TIMEOUT = 10  # seconds


def _search_lang(query: str, language: str, limit: int) -> list[dict]:
    """Search ARASAAC in *language*, return list of {id, label} dicts."""
    encoded = urllib.parse.quote(query, safe="")
    url = f"{_API_BASE}/pictograms/{language}/search/{encoded}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    results: list[dict] = []
    for item in data[:limit]:
        pic_id = item.get("_id")
        if not isinstance(pic_id, int):
            continue
        keywords = item.get("keywords") or []
        label = keywords[0]["keyword"] if keywords else str(pic_id)
        results.append({"id": pic_id, "label": label, "thumb_bytes": None})

    return results


def _nb_label(pic_id: int) -> str | None:
    """Fetch the first Norwegian (nb) keyword for *pic_id*. Returns None on failure."""
    url = f"{_API_BASE}/pictograms/nb/{pic_id}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        keywords = data.get("keywords") or []
        return keywords[0]["keyword"] if keywords else None
    except Exception:
        return None


def search(query: str, limit: int = 20) -> list[dict]:
    """Search ARASAAC in both Norwegian (nb) and English (en).

    Labels are always Norwegian — English-only matches have their Norwegian
    label resolved via a parallel API lookup.

    Returns a list of dicts::

        {"id": int, "label": str, "thumb_bytes": None}

    Returns an empty list on complete failure.
    """
    nb_results = _search_lang(query, "nb", limit)
    en_results = _search_lang(query, "en", limit)

    seen_ids: set[int] = {r["id"] for r in nb_results}
    merged:   list[dict] = list(nb_results)

    en_only = [r for r in en_results if r["id"] not in seen_ids]
    if en_only:
        with ThreadPoolExecutor(max_workers=5) as pool:
            nb_labels = list(pool.map(lambda r: _nb_label(r["id"]), en_only))
        for r, nb_lbl in zip(en_only, nb_labels):
            if nb_lbl:
                r["label"] = nb_lbl
            merged.append(r)
            seen_ids.add(r["id"])

    return merged


def fetch_image(pictogram_id: int, resolution: int = 500) -> bytes:
    """Download and return the raw PNG bytes for *pictogram_id*.

    *resolution* should be 300, 500, or 2500.
    Raises :exc:`urllib.error.URLError` or :exc:`OSError` on failure.
    """
    url = f"{_CDN_BASE}/{pictogram_id}/{pictogram_id}_{resolution}.png"
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
        return resp.read()


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "eple"
    print(f"Searching for '{query}'…")
    results = search(query)
    if not results:
        print("No results.")
    else:
        for r in results[:5]:
            print(f"  id={r['id']}  label={r['label']!r}")
        print(f"(showing first 5 of {len(results)})")
