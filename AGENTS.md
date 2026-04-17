# AGENTS.md

## Project overview

Python desktop tool that generates print-ready A4 PDFs for AAC/ASK picture cards, lotto boards, and sign-language protocols (Norwegian). Single flat package — no monorepo, no test suite, no linter/formatter/typecheck config.

## Running the app

```bash
python app.py                                      # PySide6 GUI (all three tools)
python make_cards.py sessions/<name>               # ASK cards CLI
./make_cards.sh sessions/<name>                    # same, via bash wrapper
python make_lotto.py lotto-sessions/<name>         # Lotto CLI
python make_tegnprotokoll.py tegnprotokoll-sessions/<name>  # Sign protocol CLI
pyinstaller app.spec                               # build standalone executable
```

## No test, lint, or type commands

There are zero tests, no pytest config, no ruff/black/mypy. Don't add placeholder test commands.

## Dependencies

```bash
pip install -r requirements.txt        # PySide6>=6.6, Pillow>=10.0, reportlab>=4.0
pip install pyinstaller                # only needed for builds
```

On Linux, PySide6 requires system Qt/XCB libs (see CI workflow for the full apt-get list).

## Architecture

- `app.py` — GUI shell; imports `make_cards`, `make_lotto`, `make_tegnprotokoll`, `arasaac`, `tegnbanken` as libraries; each long-running op runs in a `QThread` worker.
- `make_cards.py`, `make_lotto.py`, `make_tegnprotokoll.py` — dual-mode: importable library AND standalone CLI (`sys.exit()` in cards, `ValueError` in lotto/tegnprotokoll).
- `pdf_utils.py` — shared utilities used by all three make_*.py modules and app.py: `IMAGE_EXTS` (frozenset), `to_rgb()`, `register_nordic_bold_font()`, `register_nordic_regular_font()`, `fit_text()`, `safe_stem()` (Windows-safe filename sanitiser), `open_file()` (cross-platform PDF opener).
- `arasaac.py` / `tegnbanken.py` — external API clients; both have a built-in CLI mode for ad-hoc testing (`python arasaac.py <query>`).

## Session / output conventions

- Sessions live in `sessions/`, `lotto-sessions/`, `tegnprotokoll-sessions/`.
- Images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`. Filename stem → card label (underscores → spaces).
- `output/` is auto-created; PDFs land there.
- Tegnbanken data cached at `~/.cache/ask-generator/tegnbanken/data.xml` (7-day TTL), not in the project dir.
- Optional `descriptions.json` sidecar in a tegnprotokoll session: `{"stem": "description text"}`.

## Gotchas

- **ReportLab uses bottom-left origin.** Labels are visually at the top of cards but have the highest `y` values in drawing code.
- **`BORDER_WIDTH` in `make_cards.py` is `5` pt.**
- **Font fallback:** if Liberation Sans Bold / Arial Bold / DejaVu Sans Bold are missing, ReportLab falls back to Helvetica-Bold, which does **not** render Norwegian characters (æ, ø, å).
- **PyInstaller onefile:** frozen executable extracts to `sys._MEIPASS`; `app.py` explicitly copies generated PDFs out to the real `BASE_DIR/output/`.
- **`make_cards.py` uses `sys.exit()` for errors** when run as CLI; `app.py` catches `SystemExit` when calling it as a library.

## Existing instruction reference

`.github/copilot-instructions.md` has detailed layout constants, internal call flow for `make_cards.py`, and preview widget constants for `app.py`. Check it before modifying rendering logic.
