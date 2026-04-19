# pip install Pillow reportlab

import io
import sys
from pathlib import Path
from typing import Optional

from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from pdf_utils import IMAGE_EXTS, to_rgb, register_nordic_bold_font, fit_text, stem_to_label


# ── Layout constants ───────────────────────────────────────────────────────────
COLS = 3
PAGE_MARGIN = 10 * mm  # page edge → first card
CARD_GAP = 5 * mm  # gap between cards
BORDER_WIDTH = 5  # points
LABEL_FONT_PT = 12  # points
LABEL_PAD_V = 2.5 * mm  # vertical padding above/below label text
IMAGE_PAD = 2.5 * mm  # equal padding left, right, and bottom of image

# Aliases kept for any code that still imports these names directly
_to_rgb = to_rgb


# ── Font setup ─────────────────────────────────────────────────────────────────
def _register_label_font() -> str:
    """Register a TTF font with Nordic character support; return its ReportLab name."""
    return register_nordic_bold_font("_LabelFont")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fit_label(c: canvas.Canvas, font: str, text: str, max_width: float) -> float:
    """Return the largest font size ≤ LABEL_FONT_PT at which text fits max_width."""
    return fit_text(c, font, text, max_width, LABEL_FONT_PT)


def _draw_card(
    c: canvas.Canvas,
    card_x: float,
    card_y: float,
    card_size: float,
    image_area_h: float,
    label_area_h: float,
    font: str,
    img_path: Path,
) -> None:
    label = stem_to_label(img_path.stem)

    # ── Border (square around the whole card) ──────────────────────────────────
    c.setLineWidth(BORDER_WIDTH)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(card_x, card_y, card_size, card_size)

    # ── Label (visually at top = high y in ReportLab coords) ──────────────────
    font_size = _fit_label(c, font, label, card_size - 4 * mm)
    label_area_bottom = card_y + card_size - label_area_h
    baseline = label_area_bottom + LABEL_PAD_V
    c.setFont(font, font_size)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(card_x + card_size / 2, baseline, label)

    # ── Image (equal IMAGE_PAD on left, right, and bottom) ────────────────────
    try:
        pil_img = to_rgb(Image.open(img_path))
        orig_w, orig_h = pil_img.size
        avail_w = card_size - 2 * IMAGE_PAD
        avail_h = image_area_h - IMAGE_PAD  # bottom pad; top is label area
        scale = min(avail_w / orig_w, avail_h / orig_h)
        draw_w = orig_w * scale
        draw_h = orig_h * scale
        draw_x = card_x + IMAGE_PAD + (avail_w - draw_w) / 2  # centred horizontally
        draw_y = card_y + IMAGE_PAD  # sits on bottom pad

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)

        c.saveState()
        clip = c.beginPath()
        clip.rect(card_x, card_y, card_size, image_area_h)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(ImageReader(buf), draw_x, draw_y, draw_w, draw_h)
        c.restoreState()
    except Exception as exc:
        print(f"  Warning: could not load {img_path.name}: {exc}")


# ── Main ───────────────────────────────────────────────────────────────────────
def make_cards(
    session_path_str: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Generate an ASK card PDF for *session_path_str*.

    Parameters
    ----------
    session_path_str:
        Path to the session folder.
    output_dir:
        Where to write the PDF.  Defaults to ``{project_root}/output``.

    Returns the output :class:`~pathlib.Path`.
    Raises :exc:`ValueError` on invalid input (empty session, bad path, etc.).
    """
    session_path = Path(session_path_str).resolve()
    if not session_path.is_dir():
        raise ValueError(f"'{session_path_str}' is not a directory.")

    images = sorted(p for p in session_path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        raise ValueError(f"No images found in '{session_path_str}'.")

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session_name = session_path.name
    output_path = output_dir / f"{session_name}.pdf"

    font = _register_label_font()

    page_w, page_h = A4
    card_size = (page_w - 2 * PAGE_MARGIN - (COLS - 1) * CARD_GAP) / COLS
    label_area_h = LABEL_FONT_PT + 2 * LABEL_PAD_V
    image_area_h = card_size - label_area_h
    if card_size <= 0 or image_area_h <= 0:
        raise ValueError(
            "Layout constants produce non-positive card dimensions — "
            "reduce PAGE_MARGIN, CARD_GAP, or COLS."
        )
    rows_per_page = int((page_h - 2 * PAGE_MARGIN + CARD_GAP) // (card_size + CARD_GAP))
    cards_per_page = COLS * rows_per_page
    if cards_per_page <= 0:
        raise ValueError(
            "Layout constants produce 0 cards per page — "
            "reduce PAGE_MARGIN, CARD_GAP, or COLS."
        )

    c = canvas.Canvas(str(output_path), pagesize=A4)

    for i, img_path in enumerate(images):
        page_pos = i % cards_per_page
        if page_pos == 0 and i > 0:
            c.showPage()

        row = page_pos // COLS
        col = page_pos % COLS

        x = PAGE_MARGIN + col * (card_size + CARD_GAP)
        y = page_h - PAGE_MARGIN - (row + 1) * card_size - row * CARD_GAP

        _draw_card(c, x, y, card_size, image_area_h, label_area_h, font, img_path)

    c.save()
    pages = (len(images) - 1) // cards_per_page + 1
    print(
        f"✓  {len(images)} cards across {pages} page(s)  →  {output_path}\n"
        f"   Grid: {COLS} × {rows_per_page} = {cards_per_page} cards/page"
    )
    return output_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(
            "Usage:   python make_cards.py <session_folder>\n"
            "Example: python make_cards.py sessions/2024-01-familie"
        )
    try:
        make_cards(sys.argv[1])
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
