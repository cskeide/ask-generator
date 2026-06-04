# ASK Card Generator

A single-script tool that turns folders of images into print-ready A4 PDFs of AAC/ASK picture cards (alternativ og supplerende kommunikasjon).

## Running the script

```bash
./make_cards.sh sessions/<session-name>
# e.g. ./make_cards.sh sessions/2026-03-familie
```

`make_cards.sh` is a wrapper around `make_cards.py`. Run it with no arguments or `--help` to see usage.

Output is written to `output/<session-name>.pdf`. The `output/` directory is created automatically.

## Dependencies

```bash
sudo pacman -S python-pillow python-reportlab pyside6   # Arch Linux
# or: pip install -r requirements.txt
```

`requirements.txt`: `PySide6>=6.6`, `Pillow>=10.0`, `reportlab>=4.0`

## Architecture

The project has two entry points:

- **`app.py`** — PySide6 desktop GUI; imports `make_cards` as a library and calls `make_cards.make_cards()` from a background `QThread`. Handles session management, image drag-and-drop, live page preview (rendered with Pillow), and PDF generation.
- **`make_cards.py`** — standalone CLI / importable library; resolves paths, discovers images, computes grid geometry, drives the ReportLab canvas.
- **`app.spec`** — PyInstaller spec that bundles `app.py` into a single-file executable (`dist/ask-card-generator`). Build with `pyinstaller app.spec`.

Shared helpers live in `pdf_utils.py` (used by all three generators and `app.py`): `register_nordic_bold_font()` / `register_nordic_regular_font()`, `fit_text()` (size only) and `fit_label()` (returns `(display_text, size)`, ellipsizing labels that won't fit even at the minimum size), `compute_grid()` (square-card page geometry → `Grid` namedtuple), `to_rgb()`, `safe_stem()`, `stem_to_label()`, `open_file()`.

`make_cards.py` internal flow:

1. `make_cards()` — entry point; resolves paths, discovers images, computes grid geometry via `pdf_utils.compute_grid()`, drives the ReportLab canvas
2. `_draw_card()` — draws one card: border → label → image (via Pillow → BytesIO → ReportLab). Label sizing/truncation is handled by `pdf_utils.fit_label()`
3. `_register_label_font()` — registers a Nordic-capable TTF via `pdf_utils.register_nordic_bold_font()` (Liberation Sans Bold preferred); falls back to Helvetica-Bold

(`make_lotto.py` mirrors this flow with `LOTTO_COLS`; it additionally decodes each image once and renders both the board and cut-out PDFs in `make_board_and_cutout_pdf()`.)

All layout dimensions are computed from a few constants at the top of each generator — edit those to change spacing without touching logic.

`app.py` preview constants (separate from ReportLab layout). Pixel sizes are preview-only, but the column count and column fractions are **imported from the generator modules** so the preview can't drift from the real PDF:

| Constant | Source | Effect |
|---|---|---|
| `_PREV_CARD` | `150 px` (preview-only) | Card size in preview |
| `_PREV_COLS` | `make_cards.COLS` | Columns in preview |
| `_PREV_GAP` | `6 px` (preview-only) | Gap between cards in preview |
| `_PREV_MARGIN` | `12 px` (preview-only) | Page margin in preview |

## Key conventions

**Session folders** live under `sessions/` and are named `YYYY-MM-description`. Each folder contains image files whose **filename stem becomes the card label** — underscores are replaced with spaces (`stor_bror.jpg` → "stor bror").

**Supported image formats:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`. All formats are decoded by Pillow and converted to RGB PNG before being handed to ReportLab, so ReportLab format support is irrelevant.

**ReportLab coordinate system** is bottom-left origin. The label is visually at the top of the card, which means it sits at the *highest* y value. Keep this in mind when reading `_draw_card`.

**Card geometry** — all sizes in ReportLab points (1 pt = 1/72 inch). Millimetre constants use `from reportlab.lib.units import mm` and are multiplied inline (e.g. `10 * mm`). Cards are square; `card_size` is derived at runtime from page width, `COLS`, `PAGE_MARGIN`, and `CARD_GAP`.

**Image padding** — `IMAGE_PAD` is applied equally on left, right, and bottom so the image never touches the border on those three sides. The top of the image area is bounded by the label area, not an explicit pad.

**Font priority:** Liberation Sans Bold → Arial Bold → DejaVu Sans Bold → Helvetica-Bold (built-in, no Nordic character support).

## Layout tuning constants

| Constant | Default | Effect |
|---|---|---|
| `COLS` | `3` | Cards per row |
| `PAGE_MARGIN` | `10 mm` | Page edge to first card |
| `CARD_GAP` | `5 mm` | Space between cards |
| `BORDER_WIDTH` | `5 pt` | Card border thickness |
| `LABEL_FONT_PT` | `12 pt` | Max label font size |
| `LABEL_PAD_V` | `2.5 mm` | Vertical padding inside label area |
| `IMAGE_PAD` | `2.5 mm` | Padding around image (left/right/bottom) |
