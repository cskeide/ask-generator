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

from pdf_utils import IMAGE_EXTS, to_rgb, register_nordic_bold_font, fit_text

# Alias kept for any external callers
_to_rgb = to_rgb

# ── Layout constants ───────────────────────────────────────────────────────────
LOTTO_COLS = 4
PAGE_MARGIN = 8 * mm  # page edge → first card
CARD_GAP = 4 * mm  # gap between cards
BORDER_WIDTH = 2.5  # points
LABEL_FONT_PT = 10  # points
LABEL_PAD_V = 2 * mm  # vertical padding above label text baseline
IMAGE_PAD = 2 * mm  # padding around image on all four sides within image area


# ── Font setup ─────────────────────────────────────────────────────────────────
def _register_label_font() -> str:
    """Register a TTF with Nordic character support and return its name."""
    return register_nordic_bold_font("_LottoFont")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fit_label(c: canvas.Canvas, font: str, text: str, max_width: float) -> float:
    """Return the largest font size ≤ LABEL_FONT_PT at which *text* fits *max_width*."""
    return fit_text(c, font, text, max_width, LABEL_FONT_PT)


def _draw_lotto_card(
    c: canvas.Canvas,
    card_x: float,
    card_y: float,
    card_size: float,
    image_area_h: float,
    label_area_h: float,
    font: str,
    img_path: Path,
    cutout_mode: bool = False,
) -> None:
    """Draw one lotto card with the label at the bottom.

    *card_y* is the bottom-left corner in ReportLab coordinates (y increases
    upward).  *cutout_mode* replaces the solid border with a dashed cut-line.
    """
    label = img_path.stem.replace("_", " ")

    # ── Border ─────────────────────────────────────────────────────────────────
    c.setLineWidth(BORDER_WIDTH)
    c.setStrokeColorRGB(0, 0, 0)
    if cutout_mode:
        c.setDash([4, 4])
    c.rect(card_x, card_y, card_size, card_size)
    if cutout_mode:
        c.setDash([])  # reset to solid for everything else

    # ── Label at bottom (card_y → card_y + label_area_h) ──────────────────────
    font_size = _fit_label(c, font, label, card_size - 4 * mm)
    baseline = card_y + LABEL_PAD_V
    c.setFont(font, font_size)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(card_x + card_size / 2, baseline, label)

    # ── Image (above label area, IMAGE_PAD on all four sides) ─────────────────
    # Image area in ReportLab: bottom = card_y + label_area_h, height = image_area_h
    try:
        pil_img = to_rgb(Image.open(img_path))
        orig_w, orig_h = pil_img.size
        avail_w = card_size - 2 * IMAGE_PAD
        avail_h = image_area_h - 2 * IMAGE_PAD
        scale = min(avail_w / orig_w, avail_h / orig_h)
        draw_w = orig_w * scale
        draw_h = orig_h * scale

        img_area_bottom = card_y + label_area_h
        draw_x = card_x + IMAGE_PAD + (avail_w - draw_w) / 2
        draw_y = img_area_bottom + IMAGE_PAD + (avail_h - draw_h) / 2

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)

        c.saveState()
        clip = c.beginPath()
        clip.rect(card_x, img_area_bottom, card_size, image_area_h)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(ImageReader(buf), draw_x, draw_y, draw_w, draw_h)
        c.restoreState()
    except Exception as exc:
        print(f"  Warning: could not load {img_path.name}: {exc}")


# ── Internal PDF builder ───────────────────────────────────────────────────────
def _make_pdf(
    session_path_str: str,
    output_dir: Optional[Path],
    cutout_mode: bool,
) -> Path:
    session_path = Path(session_path_str).resolve()
    if not session_path.is_dir():
        raise ValueError(f"'{session_path_str}' is not a directory.")

    images = sorted(p for p in session_path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        raise ValueError(f"No images found in '{session_path_str}'.")

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    session_name = session_path.name
    suffix = "_cutout" if cutout_mode else "_board"
    output_path = output_dir / f"{session_name}{suffix}.pdf"

    font = _register_label_font()

    page_w, page_h = A4
    card_size = (page_w - 2 * PAGE_MARGIN - (LOTTO_COLS - 1) * CARD_GAP) / LOTTO_COLS
    label_area_h = LABEL_FONT_PT + 2 * LABEL_PAD_V
    image_area_h = card_size - label_area_h
    if card_size <= 0 or image_area_h <= 0:
        raise ValueError(
            "Layout produces non-positive card dimensions — reduce PAGE_MARGIN, CARD_GAP, or LOTTO_COLS."
        )
    rows_per_page = int((page_h - 2 * PAGE_MARGIN + CARD_GAP) // (card_size + CARD_GAP))
    cards_per_page = LOTTO_COLS * rows_per_page

    if cards_per_page <= 0:
        raise ValueError(
            "Layout produces 0 cards per page — reduce PAGE_MARGIN, CARD_GAP, or LOTTO_COLS."
        )

    c = canvas.Canvas(str(output_path), pagesize=A4)

    for i, img_path in enumerate(images):
        page_pos = i % cards_per_page
        if page_pos == 0 and i > 0:
            c.showPage()

        row = page_pos // LOTTO_COLS
        col = page_pos % LOTTO_COLS

        x = PAGE_MARGIN + col * (card_size + CARD_GAP)
        y = page_h - PAGE_MARGIN - (row + 1) * card_size - row * CARD_GAP

        _draw_lotto_card(
            c, x, y, card_size, image_area_h, label_area_h, font, img_path, cutout_mode
        )

    c.save()
    pages = (len(images) - 1) // cards_per_page + 1
    mode = "cut-out" if cutout_mode else "board"
    print(
        f"✓  {len(images)} lotto cards ({mode}) across {pages} page(s)  →  {output_path}\n"
        f"   Grid: {LOTTO_COLS} × {rows_per_page} = {cards_per_page} cards/page"
    )
    return output_path


# ── Public API ─────────────────────────────────────────────────────────────────
def make_board_pdf(
    session_path_str: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Generate a lotto board PDF (solid borders) for *session_path_str*."""
    return _make_pdf(session_path_str, output_dir, cutout_mode=False)


def make_cutout_pdf(
    session_path_str: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Generate a lotto cut-out PDF (dashed borders) for *session_path_str*."""
    return _make_pdf(session_path_str, output_dir, cutout_mode=True)


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(
            "Usage:   python make_lotto.py <session_folder>\n"
            "Example: python make_lotto.py lotto-sessions/2026-04-test"
        )
    board = make_board_pdf(sys.argv[1])
    cutout = make_cutout_pdf(sys.argv[1])
    print(f"Board:  {board}")
    print(f"Cutout: {cutout}")
