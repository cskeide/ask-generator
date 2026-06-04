# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Python desktop tool that generates print-ready A4 PDFs for AAC/ASK (alternativ og supplerende kommunikasjon) materials in Norwegian: picture cards, lotto boards, and sign-language protocols. Single flat package — no monorepo.

## Commands

```bash
pip install -r requirements.txt                             # PySide6>=6.6, Pillow>=10.0, reportlab>=4.0
pip install -r requirements-dev.txt                        # pytest (tests only)
pip install pyinstaller                                     # only for builds

python app.py                                               # PySide6 GUI (all three tools)
python make_cards.py sessions/<name>                        # ASK cards CLI (./make_cards.sh wraps this)
python make_lotto.py lotto-sessions/<name>                  # Lotto CLI
python make_tegnprotokoll.py tegnprotokoll-sessions/<name>  # Sign protocol CLI
python arasaac.py <query>                                   # ad-hoc API client test
python tegnbanken.py <query>                                # ad-hoc API client test

python -m pytest                                            # run the test suite (tests/, no network needed)
python -m pytest tests/test_pdf_utils.py::test_safe_stem_empty_falls_back_to_image  # single test

pyinstaller app.spec                                        # build dist/ask-card-generator (onefile, GUI)
```

Tests live in `tests/` (pytest, configured in `pytest.ini`); they cover the pure helpers in `pdf_utils` and run each generator against a temp session with generated images — no network or system fonts required. There is **no linter, formatter, or type checker** — no ruff/black/mypy config exists. Don't add placeholder lint commands or assume any exist.

On Linux, PySide6 needs system Qt/XCB libs (see `.github/workflows/build.yml` for the apt-get list). CI builds onefile executables for Linux/Windows/macOS on push to `main` and tags (`v*`) create a GitHub release.

## Architecture

- **`app.py`** — GUI shell. Imports `make_cards`, `make_lotto`, `make_tegnprotokoll`, `arasaac`, `tegnbanken` as libraries; each long-running op runs in a `QThread` worker. Has its own preview-rendering constants (`_PREV_CARD`, `_PREV_COLS`, etc.) separate from the ReportLab layout constants.
- **`make_cards.py` / `make_lotto.py` / `make_tegnprotokoll.py`** — dual-mode modules: importable library *and* standalone CLI. Each defines a small set of layout constants at the top of the file — edit those to change spacing without touching drawing logic.
- **`pdf_utils.py`** — shared helpers used by all three generators and `app.py`: `IMAGE_EXTS` (frozenset), `to_rgb()`, `register_nordic_bold_font()`, `register_nordic_regular_font()`, `fit_text()`, `safe_stem()` (Windows-safe filename sanitiser), `stem_to_label()`, `open_file()` (cross-platform PDF opener).
- **`arasaac.py` / `tegnbanken.py`** — external API clients, each with a built-in CLI mode for testing.

## Conventions

- Sessions live in `sessions/`, `lotto-sessions/`, `tegnprotokoll-sessions/` (one folder per session). `output/` is auto-created; PDFs land there named after the session.
- Supported images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`. Filename stem → card label, underscores → spaces. All images are decoded by Pillow and converted to RGB PNG before reaching ReportLab.
- Tegnbanken data is cached at `~/.cache/ask-generator/tegnbanken/data.xml` (7-day TTL), not in the project dir.
- Optional `descriptions.json` sidecar in a tegnprotokoll session maps `{"stem": "description text"}`.

## Gotchas

- **ReportLab uses a bottom-left origin.** Labels are visually at the top of a card but have the *highest* `y` values in drawing code.
- **Font fallback breaks Norwegian characters.** Priority is Liberation Sans Bold → Arial Bold → DejaVu Sans Bold → Helvetica-Bold; the built-in Helvetica-Bold fallback does **not** render æ/ø/å.
- **Error-handling differs by module when run as CLI:** `make_cards.py` uses `sys.exit()`; `make_lotto.py`/`make_tegnprotokoll.py` raise `ValueError`. `app.py` accounts for this when calling them as libraries.
- **PyInstaller onefile** extracts to `sys._MEIPASS`; `app.py` explicitly copies generated PDFs out to the real `BASE_DIR/output/`.

## Reference docs

`.github/copilot-instructions.md` has the full layout-constant tables and `make_cards.py` internal call flow. `AGENTS.md` covers the same ground as this file. Check `copilot-instructions.md` before modifying rendering logic.
