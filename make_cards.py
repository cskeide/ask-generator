# pip install Pillow reportlab

import io
import sys
import os
from pathlib import Path

from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert any Pillow image to RGB, handling palette+transparency correctly."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")

# ── Layout constants ───────────────────────────────────────────────────────────
COLS           = 3
PAGE_MARGIN    = 10 * mm   # page edge → first card
CARD_GAP       = 5  * mm   # gap between cards
BORDER_WIDTH   = 5              # points
LABEL_FONT_PT  = 12         # points
LABEL_PAD_V    = 2.5 * mm   # vertical padding above/below label text
IMAGE_PAD      = 2.5 * mm   # equal padding left, right, and bottom of image


# ── Font setup ─────────────────────────────────────────────────────────────────
def _register_label_font() -> str:
    """
    Register a TTF font that supports Nordic characters (æ ø å).
    Preference order: Liberation Sans Bold → Arial Bold → DejaVu Sans Bold.
    Falls back to the built-in Helvetica-Bold if nothing is found.
    """
    candidates = [
        # Linux
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        # macOS / Windows Arial
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        # DejaVu fallback
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("_LabelFont", path))
            return "_LabelFont"
    return "Helvetica-Bold"


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fit_label(c: canvas.Canvas, font: str, text: str, max_width: float) -> float:
    """Return the largest font size ≤ LABEL_FONT_PT at which text fits max_width."""
    size = LABEL_FONT_PT
    while size > 4:
        if c.stringWidth(text, font, size) <= max_width:
            return size
        size -= 0.5
    return size


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
    label = img_path.stem.replace("_", " ")

    # ── Border (square around the whole card) ──────────────────────────────────
    c.setLineWidth(BORDER_WIDTH)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(card_x, card_y, card_size, card_size)

    # ── Label (visually at top = high y in ReportLab coords) ──────────────────
    font_size   = _fit_label(c, font, label, card_size - 4 * mm)
    label_area_bottom = card_y + card_size - label_area_h
    baseline    = label_area_bottom + LABEL_PAD_V
    c.setFont(font, font_size)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(card_x + card_size / 2, baseline, label)

    # ── Image (equal IMAGE_PAD on left, right, and bottom) ────────────────────
    try:
        pil_img        = _to_rgb(Image.open(img_path))
        orig_w, orig_h = pil_img.size
        avail_w = card_size - 2 * IMAGE_PAD
        avail_h = image_area_h - IMAGE_PAD        # bottom pad; top is label area
        scale   = min(avail_w / orig_w, avail_h / orig_h)
        draw_w  = orig_w * scale
        draw_h  = orig_h * scale
        draw_x  = card_x + IMAGE_PAD + (avail_w - draw_w) / 2   # centred horizontally
        draw_y  = card_y + IMAGE_PAD                              # sits on bottom pad

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
def make_cards(session_path_str: str) -> None:
    session_path = Path(session_path_str).resolve()
    if not session_path.is_dir():
        sys.exit(f"Error: '{session_path_str}' is not a directory.")

    images = sorted(
        p for p in session_path.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".avif"}
    )
    if not images:
        sys.exit(f"No jpg/png images found in '{session_path_str}'.")

    session_name = session_path.name
    output_dir   = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path  = output_dir / f"{session_name}.pdf"

    font = _register_label_font()

    page_w, page_h = A4
    card_size     = (page_w - 2 * PAGE_MARGIN - (COLS - 1) * CARD_GAP) / COLS
    label_area_h  = LABEL_FONT_PT + 2 * LABEL_PAD_V
    image_area_h  = card_size - label_area_h
    if card_size <= 0 or image_area_h <= 0:
        sys.exit("Error: layout constants produce non-positive card dimensions — reduce PAGE_MARGIN, CARD_GAP, or COLS.")
    rows_per_page = int((page_h - 2 * PAGE_MARGIN + CARD_GAP) // (card_size + CARD_GAP))
    cards_per_page = COLS * rows_per_page
    if cards_per_page <= 0:
        sys.exit("Error: layout constants produce 0 cards per page — reduce PAGE_MARGIN, CARD_GAP, or COLS.")

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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(
            "Usage:   python make_cards.py <session_folder>\n"
            "Example: python make_cards.py sessions/2024-01-familie"
        )
    make_cards(sys.argv[1])
