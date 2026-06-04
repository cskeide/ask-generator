"""Unit tests for the pure helpers in pdf_utils."""

from __future__ import annotations

import io

from PIL import Image
from reportlab.pdfgen import canvas

from pdf_utils import (
    IMAGE_EXTS,
    fit_text,
    safe_stem,
    stem_to_label,
    to_rgb,
)


# ── safe_stem ────────────────────────────────────────────────────────────────


def test_safe_stem_spaces_to_underscores():
    assert safe_stem("stor bror") == "stor_bror"


def test_safe_stem_strips_windows_illegal_chars():
    assert safe_stem('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"


def test_safe_stem_collapses_and_trims_underscores():
    assert safe_stem("  a   b  ") == "a_b"


def test_safe_stem_empty_falls_back_to_image():
    assert safe_stem("") == "image"
    assert safe_stem("///") == "image"


def test_safe_stem_strips_control_chars():
    assert safe_stem("a\x00b\x1fc") == "a_b_c"


# ── stem_to_label ────────────────────────────────────────────────────────────


def test_stem_to_label_underscores_to_spaces():
    assert stem_to_label("stor_bror") == "stor bror"


def test_stem_to_label_strips_duplicate_counter():
    # GUI appends "__N" for duplicate drops; it must not leak into the label.
    assert stem_to_label("eple__2") == "eple"
    assert stem_to_label("stor_bror__10") == "stor bror"


def test_stem_to_label_single_underscore_not_a_counter():
    # A single underscore before digits is a normal word separator.
    assert stem_to_label("bilde_2") == "bilde 2"


# ── fit_text ─────────────────────────────────────────────────────────────────


def _canvas() -> canvas.Canvas:
    return canvas.Canvas(io.BytesIO())


def test_fit_text_returns_start_when_text_fits():
    c = _canvas()
    # Plenty of width → no shrinking needed.
    assert fit_text(c, "Helvetica-Bold", "hi", 10_000, 12) == 12


def test_fit_text_shrinks_for_long_text():
    c = _canvas()
    size = fit_text(c, "Helvetica-Bold", "a very long label indeed", 40, 12)
    assert size < 12


def test_fit_text_floors_at_4pt():
    c = _canvas()
    # Impossibly narrow width → hits the lower bound rather than going to zero.
    size = fit_text(c, "Helvetica-Bold", "wide word", 1, 12)
    assert size == 4


def test_fit_text_result_actually_fits_when_possible():
    c = _canvas()
    text, width = "label", 60
    size = fit_text(c, "Helvetica-Bold", text, width, 12)
    if size > 4:  # only guaranteed to fit when not floored
        assert c.stringWidth(text, "Helvetica-Bold", size) <= width


# ── to_rgb ───────────────────────────────────────────────────────────────────


def test_to_rgb_from_rgb_is_rgb():
    img = Image.new("RGB", (4, 4), (10, 20, 30))
    assert to_rgb(img).mode == "RGB"


def test_to_rgb_flattens_rgba_onto_white():
    # Fully transparent pixel should become white after flattening.
    img = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    out = to_rgb(img)
    assert out.mode == "RGB"
    assert out.getpixel((0, 0)) == (255, 255, 255)


def test_to_rgb_palette_with_transparency():
    img = Image.new("P", (2, 2))
    img.info["transparency"] = 0
    assert to_rgb(img).mode == "RGB"


# ── IMAGE_EXTS ───────────────────────────────────────────────────────────────


def test_image_exts_lowercase_with_dot():
    assert ".jpg" in IMAGE_EXTS
    assert ".avif" in IMAGE_EXTS
    # Stored normalised (lowercase, dotted); callers lower-case suffixes.
    assert all(e.startswith(".") and e == e.lower() for e in IMAGE_EXTS)
