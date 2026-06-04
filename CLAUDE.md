# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Python desktop tool that generates print-ready A4 PDFs for AAC/ASK (alternativ og supplerende kommunikasjon) materials in Norwegian: picture cards, lotto boards, and sign-language protocols. Single flat package — no monorepo.

## Commands

```bash
pip install -r requirements.txt                             # PySide6, Pillow, reportlab (capped <next-major)
pip install -r requirements-dev.txt                        # pytest + ruff (dev only)
pip install pyinstaller                                     # only for builds

python app.py                                               # PySide6 GUI (all three tools)
python make_cards.py sessions/<name>                        # ASK cards CLI (./make_cards.sh wraps this)
python make_lotto.py lotto-sessions/<name>                  # Lotto CLI
python make_tegnprotokoll.py tegnprotokoll-sessions/<name>  # Sign protocol CLI
python arasaac.py <query>                                   # ad-hoc API client test
python tegnbanken.py <query>                                # ad-hoc API client test

python -m pytest                                            # run the test suite (tests/, no network needed)
python -m pytest tests/test_pdf_utils.py::test_safe_stem_empty_falls_back_to_image  # single test
ruff check .                                                # lint (config in ruff.toml)

pyinstaller app.spec                                        # build dist/ask-card-generator (onefile, GUI)
```

Tests live in `tests/` (pytest, configured in `pytest.ini`); they cover the pure helpers in `pdf_utils`, run each generator against a temp session of generated images, and exercise the API clients with monkeypatched network calls — no real network or system fonts required. Ruff is configured **lint-only** (`ruff.toml`, rules E/F/W; import-sorting and E402 deliberately disabled — there is no formatter and the import layout is intentional). No type checker is configured. Don't add placeholder commands or assume other tooling exists.

On Linux, PySide6 needs system Qt/XCB libs (see `.github/workflows/build.yml` for the apt-get list). CI builds onefile executables for Linux/Windows/macOS on push to `main` and tags (`v*`) create a GitHub release.

## Architecture

- **`app.py`** — GUI shell. Imports `make_cards`, `make_lotto`, `make_tegnprotokoll`, `arasaac`, `tegnbanken` as libraries; each long-running op runs in a `QThread` worker. Preview rendering uses its own pixel constants, but **column counts and column fractions are imported from the generator modules** (`make_cards.COLS`, `make_lotto.LOTTO_COLS`, `make_tegnprotokoll.COL_FRACS`) so the preview can't drift from the real PDF layout.
- **`make_cards.py` / `make_lotto.py` / `make_tegnprotokoll.py`** — dual-mode modules: importable library *and* standalone CLI. Each defines a small set of layout constants at the top of the file — edit those to change spacing without touching drawing logic. `make_lotto` exposes `make_board_pdf`, `make_cutout_pdf`, and `make_board_and_cutout_pdf` (the last decodes each image once and renders both PDFs — used by the CLI and GUI).
- **`pdf_utils.py`** — shared helpers used by all three generators and `app.py`: `IMAGE_EXTS` (frozenset), `to_rgb()`, `register_nordic_bold_font()`, `register_nordic_regular_font()`, `fit_text()` (returns a font size), `fit_label()` (returns `(display_text, size)`, ellipsizing labels that can't fit even at the minimum size), `compute_grid()` (shared square-card page geometry → `Grid` namedtuple, raises `ValueError` on impossible layouts), `safe_stem()` (Windows-safe filename sanitiser), `stem_to_label()` (stem → label; strips the GUI's `__N` duplicate counter), `open_file()` (cross-platform PDF opener).
- **`arasaac.py` / `tegnbanken.py`** — external API clients, each with a built-in CLI mode for testing. `search()` returns `[]` when the server is reachable but finds nothing, and raises `SearchError` on a genuine network/server failure (tegnbanken still falls back to a stale cache first). The GUI search workers surface `SearchError` as an error message rather than a misleading "No results".

## Conventions

- Sessions live in `sessions/`, `lotto-sessions/`, `tegnprotokoll-sessions/` (one folder per session). `output/` is auto-created; PDFs land there named after the session.
- Supported images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`. Filename stem → card label via `stem_to_label()` (underscores → spaces, `__N` duplicate counter stripped) — used uniformly by all three generators and the GUI previews/lists, so labels match everywhere. All images are decoded by Pillow and converted to RGB PNG before reaching ReportLab.
- Tegnbanken data is cached at `~/.cache/ask-generator/tegnbanken/data.xml` (7-day TTL), not in the project dir.
- Optional `descriptions.json` sidecar in a tegnprotokoll session maps `{"stem": "description text"}`.

## Gotchas

- **ReportLab uses a bottom-left origin.** Labels are visually at the top of a card but have the *highest* `y` values in drawing code.
- **Font fallback breaks Norwegian characters.** Priority is Liberation Sans Bold → Arial Bold → DejaVu Sans Bold → Helvetica-Bold; the built-in Helvetica-Bold fallback does **not** render æ/ø/å.
- **Error-handling differs by module when run as CLI:** `make_cards.py` uses `sys.exit()`; `make_lotto.py`/`make_tegnprotokoll.py` raise `ValueError`. `app.py` accounts for this when calling them as libraries.
- **PyInstaller onefile** extracts to `sys._MEIPASS`; `app.py` explicitly copies generated PDFs out to the real `BASE_DIR/output/`.

## Reference docs

`.github/copilot-instructions.md` has the full layout-constant tables and `make_cards.py` internal call flow. `AGENTS.md` covers the same ground as this file. Check `copilot-instructions.md` before modifying rendering logic.
