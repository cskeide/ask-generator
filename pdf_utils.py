"""Shared utilities for ASK Card Generator PDF modules.

Centralises helpers that were previously duplicated across make_cards.py,
make_lotto.py, make_tegnprotokoll.py, and app.py.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

from PIL import Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── Constants ──────────────────────────────────────────────────────────────────

IMAGE_EXTS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp", ".avif"})

_FONT_CANDIDATES: list[str] = [
    # Linux — Liberation Sans
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    # macOS / Windows Arial
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    # DejaVu fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]

_REGULAR_FONT_CANDIDATES: list[str] = [
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]

# ── Image helpers ──────────────────────────────────────────────────────────────


def to_rgb(img: Image.Image) -> Image.Image:
    """Convert any Pillow image to RGB, handling palette+transparency correctly."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


# Keep the private alias so existing callers in this package can use either name.
_to_rgb = to_rgb


# ── Font helpers ───────────────────────────────────────────────────────────────

# Track aliases already registered in this process to avoid redundant TTFont
# construction and pdfmetrics calls when the same alias is registered repeatedly.
_registered_font_aliases: set[str] = set()


def register_nordic_bold_font(alias: str) -> str:
    """Register a TTF bold font that supports Nordic characters (æ ø å).

    Tries Liberation Sans Bold → Arial Bold → DejaVu Sans Bold.  Falls back to
    the built-in Helvetica-Bold (no Nordic support) if nothing is found.

    Parameters
    ----------
    alias:
        The ReportLab internal font name to register under (e.g. ``"_LabelFont"``).

    Returns the registered alias, or ``"Helvetica-Bold"`` on fallback.
    """
    if alias in _registered_font_aliases:
        return alias
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(alias, path))
            _registered_font_aliases.add(alias)
            return alias
    return "Helvetica-Bold"


def register_nordic_regular_font(alias: str) -> str:
    """Register a TTF regular font with Nordic character support.

    Falls back to ``"Helvetica"`` if nothing is found.
    """
    if alias in _registered_font_aliases:
        return alias
    for path in _REGULAR_FONT_CANDIDATES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(alias, path))
            _registered_font_aliases.add(alias)
            return alias
    return "Helvetica"


# ── Text helpers ───────────────────────────────────────────────────────────────


def fit_text(
    c: canvas.Canvas,
    font: str,
    text: str,
    max_width: float,
    start_pt: float,
) -> float:
    """Return the largest font size ≤ *start_pt* at which *text* fits *max_width*."""
    size = start_pt
    while size > 4:
        if c.stringWidth(text, font, size) <= max_width:
            return size
        size -= 0.5
    return size


# ── Filename sanitisation ──────────────────────────────────────────────────────

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_stem(label: str) -> str:
    """Turn an arbitrary label string into a safe filename stem.

    Replaces spaces with underscores, strips characters illegal on Windows
    (``<>:"/\\|?*`` and control characters), and collapses runs of underscores.
    """
    stem = label.replace(" ", "_")
    stem = _UNSAFE_CHARS.sub("_", stem)
    # Collapse repeated underscores that may arise from multi-char replacements
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem or "image"


_DUPLICATE_SUFFIX = re.compile(r"__\d+$")


def stem_to_label(stem: str) -> str:
    """Convert a filename stem to a human-readable card label.

    Strips any trailing ``__N`` duplicate counter added by the GUI, then
    replaces remaining underscores with spaces.
    """
    stem = _DUPLICATE_SUFFIX.sub("", stem)
    return stem.replace("_", " ")


# ── PDF opener ─────────────────────────────────────────────────────────────────


def open_file(path: str) -> None:
    """Open *path* with the platform default viewer (non-blocking)."""
    import subprocess

    if not Path(path).exists():
        return
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
