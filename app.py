#!/usr/bin/env python3
"""ASK Card Generator — desktop GUI

Dependencies: PySide6, Pillow, reportlab  (see requirements.txt)
"""

from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import make_cards
from PIL import Image, ImageDraw, ImageFont


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert any Pillow image to RGB, handling palette+transparency correctly."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# ── Paths ──────────────────────────────────────────────────────────────────────
# When frozen by PyInstaller the executable is the reference point; otherwise
# fall back to this file's directory so "python app.py" works from source.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

SESSIONS_DIR       = BASE_DIR / "sessions"
LOTTO_SESSIONS_DIR = BASE_DIR / "lotto-sessions"
OUTPUT_DIR         = BASE_DIR / "output"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}

# ── Preview rendering ──────────────────────────────────────────────────────────
_PREV_CARD = 150   # px per card in preview
_PREV_COLS = 3
_PREV_GAP = 6
_PREV_MARGIN = 12

# Lotto preview constants (4-column, label-at-bottom)
_LOTTO_PREV_CARD   = 120
_LOTTO_PREV_COLS   = 4
_LOTTO_PREV_GAP    = 5
_LOTTO_PREV_MARGIN = 12


def _preview_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _preview_cards_per_page() -> int:
    card, gap, margin, cols = _PREV_CARD, _PREV_GAP, _PREV_MARGIN, _PREV_COLS
    page_w = cols * card + (cols - 1) * gap + 2 * margin
    page_h = int(page_w * (297 / 210))
    rows_per_page = max(1, (page_h - 2 * margin + gap) // (card + gap))
    return rows_per_page * cols


def render_page_preview(images: List[Path], page_index: int = 0) -> QPixmap:
    """Render a scaled A4-proportioned preview of the given page using Pillow."""
    if not images:
        return QPixmap()

    card, gap, margin, cols = _PREV_CARD, _PREV_GAP, _PREV_MARGIN, _PREV_COLS
    page_w = cols * card + (cols - 1) * gap + 2 * margin
    page_h = int(page_w * (297 / 210))  # A4 aspect ratio

    rows_per_page = max(1, (page_h - 2 * margin + gap) // (card + gap))
    cards_per_page = rows_per_page * cols
    start = page_index * cards_per_page
    first_page = images[start : start + cards_per_page]

    label_h = max(18, card // 8)
    font_size = max(9, label_h - 6)
    font = _preview_font(font_size)

    page = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    for idx, img_path in enumerate(first_page):
        row, col = divmod(idx, cols)
        cx = margin + col * (card + gap)
        cy = margin + row * (card + gap)

        # Card border
        draw.rectangle([cx, cy, cx + card - 1, cy + card - 1],
                       outline=(0, 0, 0), width=1)

        # Label background + text
        draw.rectangle([cx, cy, cx + card - 1, cy + label_h],
                       fill=(240, 240, 240), outline=(180, 180, 180), width=1)
        label = img_path.stem.replace("_", " ")
        try:
            bbox = font.getbbox(label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = font.getsize(label)  # type: ignore[attr-defined]
        draw.text(
            (cx + max(2, (card - tw) // 2), cy + max(1, (label_h - th) // 2)),
            label, fill=(0, 0, 0), font=font,
        )

        # Thumbnail image
        pad = 3
        iw, ih = card - 2 * pad, card - label_h - pad
        try:
            thumb = _to_rgb(Image.open(img_path))
            thumb.thumbnail((iw, ih), Image.LANCZOS)
            page.paste(thumb, (
                cx + pad + (iw - thumb.width) // 2,
                cy + label_h + (ih - thumb.height) // 2,
            ))
        except Exception:
            pass

    buf = io.BytesIO()
    page.save(buf, format="PNG")
    buf.seek(0)
    return QPixmap.fromImage(QImage.fromData(buf.read()))


def _lotto_cards_per_page() -> int:
    card, gap, margin, cols = (
        _LOTTO_PREV_CARD, _LOTTO_PREV_GAP, _LOTTO_PREV_MARGIN, _LOTTO_PREV_COLS
    )
    page_w = cols * card + (cols - 1) * gap + 2 * margin
    page_h = int(page_w * (297 / 210))
    rows_per_page = max(1, (page_h - 2 * margin + gap) // (card + gap))
    return rows_per_page * cols


def render_lotto_preview(images: List[Path], page_index: int = 0) -> QPixmap:
    """Render a scaled A4-proportioned preview of a lotto page (label at bottom, 4 cols)."""
    if not images:
        return QPixmap()

    card, gap, margin, cols = (
        _LOTTO_PREV_CARD, _LOTTO_PREV_GAP, _LOTTO_PREV_MARGIN, _LOTTO_PREV_COLS
    )
    page_w = cols * card + (cols - 1) * gap + 2 * margin
    page_h = int(page_w * (297 / 210))

    rows_per_page  = max(1, (page_h - 2 * margin + gap) // (card + gap))
    cards_per_page = rows_per_page * cols
    start      = page_index * cards_per_page
    first_page = images[start : start + cards_per_page]

    label_h   = max(16, card // 8)
    font_size = max(8, label_h - 6)
    font      = _preview_font(font_size)

    page = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    for idx, img_path in enumerate(first_page):
        row, col = divmod(idx, cols)
        cx = margin + col * (card + gap)
        cy = margin + row * (card + gap)

        # Card border
        draw.rectangle([cx, cy, cx + card - 1, cy + card - 1],
                       outline=(0, 0, 0), width=1)

        # Thumbnail in the image area (above label)
        pad        = 3
        img_area_h = card - label_h - pad   # height from cy to start of label
        iw, ih     = card - 2 * pad, img_area_h
        try:
            thumb = _to_rgb(Image.open(img_path))
            thumb.thumbnail((iw, ih), Image.LANCZOS)
            page.paste(thumb, (
                cx + pad + (iw - thumb.width) // 2,
                cy + pad + (img_area_h - thumb.height) // 2,
            ))
        except Exception:
            pass

        # Label background + text at bottom of card
        draw.rectangle(
            [cx, cy + card - label_h, cx + card - 1, cy + card - 1],
            fill=(240, 240, 240), outline=(180, 180, 180), width=1,
        )
        label = img_path.stem.replace("_", " ")
        try:
            bbox = font.getbbox(label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = font.getsize(label)  # type: ignore[attr-defined]
        draw.text(
            (
                cx + max(2, (card - tw) // 2),
                cy + card - label_h + max(1, (label_h - th) // 2),
            ),
            label, fill=(0, 0, 0), font=font,
        )

    buf = io.BytesIO()
    page.save(buf, format="PNG")
    buf.seek(0)
    return QPixmap.fromImage(QImage.fromData(buf.read()))


# ── Worker threads ─────────────────────────────────────────────────────────────
class GenerateWorker(QThread):
    done = Signal(str)   # path to generated PDF
    error = Signal(str)  # error message

    def __init__(self, session_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_path = session_path

    def run(self) -> None:
        try:
            make_cards.make_cards(str(self.session_path))

            session_name = self.session_path.name
            if getattr(sys, "frozen", False):
                # In a PyInstaller onefile bundle make_cards.__file__ resolves
                # inside sys._MEIPASS (temp dir).  Move the PDF to BASE_DIR.
                meipass = Path(getattr(sys, "_MEIPASS", ""))
                src = meipass / "output" / f"{session_name}.pdf"
                dst = OUTPUT_DIR / f"{session_name}.pdf"
                if src.exists() and src != dst:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    src.unlink(missing_ok=True)
                self.done.emit(str(dst))
            else:
                self.done.emit(str(OUTPUT_DIR / f"{session_name}.pdf"))

        except SystemExit as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))


class PreviewWorker(QThread):
    ready = Signal(QPixmap)

    def __init__(self, images: List[Path], page_index: int = 0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.images = images
        self.page_index = page_index

    def run(self) -> None:
        self.ready.emit(render_page_preview(self.images, self.page_index))


class LottoPreviewWorker(QThread):
    ready = Signal(QPixmap)

    def __init__(self, images: List[Path], page_index: int = 0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.images = images
        self.page_index = page_index

    def run(self) -> None:
        self.ready.emit(render_lotto_preview(self.images, self.page_index))


class LottoSearchWorker(QThread):
    """Fetch ARASAAC search results + 300 px thumbnails for a query."""
    results = Signal(list)   # list[dict] with thumb_bytes filled in
    error   = Signal(str)

    def __init__(self, query: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.query = query

    def run(self) -> None:
        try:
            import arasaac
            from concurrent.futures import ThreadPoolExecutor
            items = arasaac.search(self.query)

            def _fetch_thumb(r: dict) -> dict:
                try:
                    r["thumb_bytes"] = arasaac.fetch_image(r["id"], resolution=300)
                except Exception:
                    r["thumb_bytes"] = None
                return r

            with ThreadPoolExecutor(max_workers=8) as pool:
                items = list(pool.map(_fetch_thumb, items))
            self.results.emit(items)
        except Exception as exc:
            self.error.emit(str(exc))


class LottoDownloadWorker(QThread):
    """Download a single pictogram PNG and save it to the session directory."""
    done  = Signal(str)   # path to saved file
    error = Signal(str)

    def __init__(
        self,
        pic_id: int,
        label: str,
        session_path: Path,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.pic_id       = pic_id
        self.label        = label
        self.session_path = session_path

    def run(self) -> None:
        try:
            import arasaac
            data = arasaac.fetch_image(self.pic_id, resolution=500)
            stem = self.label.replace(" ", "_").replace("/", "_")
            dest = self.session_path / f"{stem}.png"
            if dest.exists():
                dest = self.session_path / f"{stem}_{self.pic_id}.png"
            dest.write_bytes(data)
            self.done.emit(str(dest))
        except Exception as exc:
            self.error.emit(str(exc))


class LottoBoardWorker(QThread):
    """Generate both board and cut-out PDFs for a lotto session."""
    done  = Signal(str, str)   # (board_path, cutout_path)
    error = Signal(str)

    def __init__(self, session_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_path = session_path

    def run(self) -> None:
        try:
            import make_lotto
            board  = make_lotto.make_board_pdf(str(self.session_path), OUTPUT_DIR)
            cutout = make_lotto.make_cutout_pdf(str(self.session_path), OUTPUT_DIR)
            self.done.emit(str(board), str(cutout))
        except Exception as exc:
            self.error.emit(str(exc))


# ── Drag-and-drop image list ───────────────────────────────────────────────────
class ImageDropList(QListWidget):
    """Icon-mode list that accepts dropped image files."""

    files_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setIconSize(QSize(90, 90))
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(6)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls() and any(
            Path(u.toLocalFile()).suffix.lower() in IMAGE_EXTS
            for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = [
            Path(u.toLocalFile())
            for u in event.mimeData().urls()
            if Path(u.toLocalFile()).suffix.lower() in IMAGE_EXTS
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


# ── Lotto tab ──────────────────────────────────────────────────────────────────
class LottoTab(QWidget):
    """Tab for searching ARASAAC pictograms, building lotto sessions, and
    generating board + cut-out PDFs."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.current_lotto_session: Optional[Path] = None
        self._search_worker:          Optional[LottoSearchWorker]  = None
        self._board_worker:           Optional[LottoBoardWorker]   = None
        self._preview_worker:         Optional[LottoPreviewWorker] = None
        self._stale_preview_workers:  List[LottoPreviewWorker]     = []
        self._download_workers:       List[LottoDownloadWorker]    = []
        self._preview_images: List[Path] = []
        self._preview_page:   int = 0
        self._preview_total_pages: int = 1
        self._last_board_pdf:  Optional[str] = None
        self._last_cutout_pdf: Optional[str] = None

        LOTTO_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._build_ui()
        self._refresh_sessions()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_cards_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setSizes([300, 490, 300])

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 6, 0)

        lbl = QLabel("Sessions")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px 0;")
        layout.addWidget(lbl)

        self.lotto_session_list = QListWidget()
        self.lotto_session_list.currentItemChanged.connect(self._on_session_changed)
        layout.addWidget(self.lotto_session_list, stretch=1)

        new_btn = QPushButton("+ New session")
        new_btn.clicked.connect(self._new_session)
        layout.addWidget(new_btn)

        sep_lbl = QLabel("Search Pictograms")
        sep_lbl.setStyleSheet("font-weight: bold; font-size: 13px; padding: 8px 0 2px;")
        layout.addWidget(sep_lbl)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in English or Norwegian…")
        self.search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self.search_input, stretch=1)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.search_status)

        self.result_list = QListWidget()
        self.result_list.setIconSize(QSize(70, 70))
        self.result_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.result_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.result_list.setSpacing(4)
        self.result_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.result_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_list.customContextMenuRequested.connect(self._result_context_menu)
        layout.addWidget(self.result_list, stretch=2)

        self.add_btn = QPushButton("Add selected to session")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._add_selected)
        layout.addWidget(self.add_btn)
        return panel

    def _build_cards_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 4, 0)

        self.lotto_session_title = QLabel("Select a session")
        self.lotto_session_title.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 2px 0;"
        )
        layout.addWidget(self.lotto_session_title)

        self.lotto_image_list = QListWidget()
        self.lotto_image_list.setIconSize(QSize(90, 90))
        self.lotto_image_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.lotto_image_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lotto_image_list.setSpacing(6)
        self.lotto_image_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lotto_image_list.customContextMenuRequested.connect(self._card_context_menu)
        layout.addWidget(self.lotto_image_list, stretch=1)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(200)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 0, 0)

        lbl = QLabel("Page preview")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px 0;")
        layout.addWidget(lbl)

        self.lotto_preview_scroll = QScrollArea()
        self.lotto_preview_scroll.setWidgetResizable(True)
        self.lotto_preview_scroll.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self.lotto_preview_label = QLabel("No session selected")
        self.lotto_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lotto_preview_label.setWordWrap(True)
        self.lotto_preview_scroll.setWidget(self.lotto_preview_label)
        layout.addWidget(self.lotto_preview_scroll, stretch=1)

        nav = QHBoxLayout()
        nav.setContentsMargins(0, 2, 0, 0)
        self.lotto_prev_btn = QPushButton("← Prev")
        self.lotto_prev_btn.setEnabled(False)
        self.lotto_prev_btn.clicked.connect(self._prev_preview_page)
        nav.addWidget(self.lotto_prev_btn)
        self.lotto_page_label = QLabel("")
        self.lotto_page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.lotto_page_label, stretch=1)
        self.lotto_next_btn = QPushButton("Next →")
        self.lotto_next_btn.setEnabled(False)
        self.lotto_next_btn.clicked.connect(self._next_preview_page)
        nav.addWidget(self.lotto_next_btn)
        layout.addLayout(nav)

        self.lotto_status = QLabel("")
        self.lotto_status.setWordWrap(True)
        layout.addWidget(self.lotto_status)

        self.lotto_progress = QProgressBar()
        self.lotto_progress.setRange(0, 0)
        self.lotto_progress.setVisible(False)
        layout.addWidget(self.lotto_progress)

        self.generate_pdfs_btn = QPushButton("Generate PDFs")
        self.generate_pdfs_btn.setEnabled(False)
        self.generate_pdfs_btn.setMinimumWidth(140)
        self.generate_pdfs_btn.clicked.connect(self._generate_pdfs)
        layout.addWidget(self.generate_pdfs_btn)

        open_row = QHBoxLayout()
        self.open_board_btn = QPushButton("Open board PDF")
        self.open_board_btn.setVisible(False)
        self.open_board_btn.clicked.connect(
            lambda: self._open_pdf(self._last_board_pdf)
        )
        open_row.addWidget(self.open_board_btn)
        self.open_cutout_btn = QPushButton("Open cut-out PDF")
        self.open_cutout_btn.setVisible(False)
        self.open_cutout_btn.clicked.connect(
            lambda: self._open_pdf(self._last_cutout_pdf)
        )
        open_row.addWidget(self.open_cutout_btn)
        layout.addLayout(open_row)
        return panel

    # ── Session management ─────────────────────────────────────────────────────

    def _refresh_sessions(self) -> None:
        current_name: Optional[str] = None
        if self.lotto_session_list.currentItem():
            p: Path = self.lotto_session_list.currentItem().data(Qt.ItemDataRole.UserRole)
            current_name = p.name

        self.lotto_session_list.clear()
        if not LOTTO_SESSIONS_DIR.exists():
            return

        restore_item: Optional[QListWidgetItem] = None
        for s in sorted(p for p in LOTTO_SESSIONS_DIR.iterdir() if p.is_dir()):
            count = sum(1 for f in s.iterdir() if f.suffix.lower() in IMAGE_EXTS)
            item = QListWidgetItem(f"{s.name}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.lotto_session_list.addItem(item)
            if s.name == current_name:
                restore_item = item

        if restore_item:
            self.lotto_session_list.setCurrentItem(restore_item)

    def _on_session_changed(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            self.current_lotto_session = None
            self.lotto_session_title.setText("Select a session")
            self.lotto_image_list.clear()
            self.generate_pdfs_btn.setEnabled(False)
            self.lotto_preview_label.setText("No session selected")
            self._preview_images = []
            self._preview_page = 0
            self._preview_total_pages = 1
            self._update_nav_buttons()
            return

        self.current_lotto_session = current.data(Qt.ItemDataRole.UserRole)
        self.lotto_session_title.setText(self.current_lotto_session.name)
        self._preview_page = 0
        self._load_session_images()

    def _new_session(self) -> None:
        name, ok = QInputDialog.getText(
            self, "New lotto session", "Session name (e.g. 2026-04-lotto-animals):"
        )
        if not ok or not name.strip():
            return
        name = name.strip().replace(" ", "-")
        new_path = LOTTO_SESSIONS_DIR / name
        if new_path.exists():
            QMessageBox.warning(self, "Already exists",
                                f"Session '{name}' already exists.")
            return
        new_path.mkdir(parents=True)
        self._refresh_sessions()
        for i in range(self.lotto_session_list.count()):
            item = self.lotto_session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == new_path:
                self.lotto_session_list.setCurrentItem(item)
                break

    # ── Image / card management ────────────────────────────────────────────────

    def _load_session_images(self) -> None:
        self.lotto_image_list.clear()
        if self.current_lotto_session is None:
            return

        images = sorted(
            p for p in self.current_lotto_session.iterdir()
            if p.suffix.lower() in IMAGE_EXTS
        )
        for img_path in images:
            item = QListWidgetItem(
                QIcon(self._make_thumb(img_path)),
                img_path.stem.replace("_", " "),
            )
            item.setData(Qt.ItemDataRole.UserRole, img_path)
            item.setSizeHint(QSize(110, 120))
            self.lotto_image_list.addItem(item)

        self.generate_pdfs_btn.setEnabled(bool(images))
        self._schedule_preview(images)

    def _make_thumb(self, img_path: Path) -> QPixmap:
        try:
            img = _to_rgb(Image.open(img_path))
            img.thumbnail((96, 96), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return QPixmap.fromImage(QImage.fromData(buf.read()))
        except Exception:
            return QPixmap()

    def _card_context_menu(self, pos) -> None:
        item = self.lotto_image_list.itemAt(pos)
        if item is None:
            return
        img_path: Path = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename…")
        remove_action = menu.addAction("Remove from session")
        action = menu.exec(self.lotto_image_list.mapToGlobal(pos))
        if action == rename_action:
            current_label = img_path.stem.replace("_", " ")
            new_label, ok = QInputDialog.getText(
                self, "Rename card", "Card label:", text=current_label
            )
            if ok and new_label.strip() and new_label.strip() != current_label:
                new_stem = new_label.strip().replace(" ", "_")
                new_path = img_path.with_stem(new_stem)
                if new_path.exists():
                    QMessageBox.warning(self, "Name taken",
                                        f"'{new_path.name}' already exists.")
                else:
                    img_path.rename(new_path)
                    self._load_session_images()
        elif action == remove_action:
            if QMessageBox.question(
                self, "Remove card",
                f"Delete '{img_path.name}' from this session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                img_path.unlink(missing_ok=True)
                self._refresh_sessions()
                self._load_session_images()

    def _result_context_menu(self, pos) -> None:
        item = self.result_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        add_action = menu.addAction("Add to session")
        action = menu.exec(self.result_list.mapToGlobal(pos))
        if action == add_action:
            if self.current_lotto_session is None:
                QMessageBox.warning(self, "No session",
                                    "Please select or create a session first.")
                return
            r = item.data(Qt.ItemDataRole.UserRole)
            self._start_download(r["id"], r["label"])

    # ── Preview ────────────────────────────────────────────────────────────────

    def _schedule_preview(self, images: List[Path]) -> None:
        self._preview_images = images
        cpp = _lotto_cards_per_page()
        self._preview_total_pages = max(
            1, -(-len(images) // cpp) if images else 1
        )
        self._update_nav_buttons()
        self._update_preview()

    def _update_preview(self) -> None:
        if self._preview_worker is not None:
            try:
                self._preview_worker.ready.disconnect()
            except RuntimeError:
                pass
            # Keep the old thread alive in the stale list until it finishes
            old = self._preview_worker
            self._stale_preview_workers.append(old)
            old.finished.connect(lambda w=old: self._stale_preview_workers.remove(w))
        self.lotto_preview_label.setText("Rendering…")
        worker = LottoPreviewWorker(self._preview_images, self._preview_page)
        worker.ready.connect(self._on_preview_ready)
        self._preview_worker = worker
        worker.start()

    def _update_nav_buttons(self) -> None:
        total = self._preview_total_pages
        page  = self._preview_page
        self.lotto_prev_btn.setEnabled(page > 0)
        self.lotto_next_btn.setEnabled(page < total - 1)
        self.lotto_page_label.setText(
            f"Page {page + 1} / {total}" if self._preview_images else ""
        )

    def _prev_preview_page(self) -> None:
        if self._preview_page > 0:
            self._preview_page -= 1
            self._update_nav_buttons()
            self._update_preview()

    def _next_preview_page(self) -> None:
        if self._preview_page < self._preview_total_pages - 1:
            self._preview_page += 1
            self._update_nav_buttons()
            self._update_preview()

    def _on_preview_ready(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self.lotto_preview_label.setText("No cards in session")
            return
        max_w = max(100, self.lotto_preview_scroll.width() - 20)
        if pixmap.width() > max_w:
            pixmap = pixmap.scaledToWidth(
                max_w, Qt.TransformationMode.SmoothTransformation
            )
        self.lotto_preview_label.setPixmap(pixmap)

    # ── Search ─────────────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        query = self.search_input.text().strip()
        if not query or self._search_worker is not None:
            return
        self.search_btn.setEnabled(False)
        self.result_list.clear()
        self.add_btn.setEnabled(False)
        self.search_status.setText("Searching…")

        worker = LottoSearchWorker(query)
        worker.results.connect(self._on_search_results)
        worker.error.connect(self._on_search_error)
        worker.finished.connect(self._on_search_finished)
        worker.finished.connect(worker.deleteLater)
        self._search_worker = worker
        worker.start()

    def _on_search_finished(self) -> None:
        self._search_worker = None
        self.search_btn.setEnabled(True)

    def _on_search_results(self, results: list) -> None:
        self.result_list.clear()
        if not results:
            self.search_status.setText("No results.")
            return
        self.search_status.setText(f"{len(results)} result(s)")
        for r in results:
            item = QListWidgetItem(r["label"])
            item.setData(Qt.ItemDataRole.UserRole, r)
            if r.get("thumb_bytes"):
                pix = QPixmap()
                pix.loadFromData(r["thumb_bytes"])
                if not pix.isNull():
                    item.setIcon(QIcon(pix))
            item.setSizeHint(QSize(110, 120))
            self.result_list.addItem(item)
        self.add_btn.setEnabled(True)

    def _on_search_error(self, msg: str) -> None:
        self.search_status.setText(f"Error: {msg}")

    # ── Add cards ──────────────────────────────────────────────────────────────

    def _add_selected(self) -> None:
        if self.current_lotto_session is None:
            QMessageBox.warning(
                self, "No session",
                "Please select or create a session first.",
            )
            return
        selected = self.result_list.selectedItems()
        if not selected:
            return
        for item in selected:
            r = item.data(Qt.ItemDataRole.UserRole)
            self._start_download(r["id"], r["label"])

    def _start_download(self, pic_id: int, label: str) -> None:
        worker = LottoDownloadWorker(pic_id, label, self.current_lotto_session)
        worker.done.connect(self._on_download_done)
        worker.error.connect(self._on_download_error)
        worker.finished.connect(lambda w=worker: self._download_workers.remove(w))
        worker.finished.connect(worker.deleteLater)
        self._download_workers.append(worker)
        worker.start()

    def _on_download_done(self, _img_path: str) -> None:
        self._refresh_sessions()
        self._load_session_images()

    def _on_download_error(self, msg: str) -> None:
        self.lotto_status.setText(f"Download error: {msg}")

    # ── PDF generation ─────────────────────────────────────────────────────────

    def _generate_pdfs(self) -> None:
        if self.current_lotto_session is None or self._board_worker is not None:
            return
        self.generate_pdfs_btn.setEnabled(False)
        self.open_board_btn.setVisible(False)
        self.open_cutout_btn.setVisible(False)
        self.lotto_progress.setVisible(True)
        self.lotto_status.setText("Generating PDFs…")

        worker = LottoBoardWorker(self.current_lotto_session)
        worker.done.connect(self._on_generate_done)
        worker.error.connect(self._on_generate_error)
        worker.finished.connect(worker.deleteLater)
        self._board_worker = worker
        worker.start()

    def _on_generate_done(self, board_path: str, cutout_path: str) -> None:
        self._board_worker = None
        self.lotto_progress.setVisible(False)
        self.generate_pdfs_btn.setEnabled(bool(self._preview_images))
        self._last_board_pdf  = board_path
        self._last_cutout_pdf = cutout_path
        self.open_board_btn.setVisible(True)
        self.open_cutout_btn.setVisible(True)
        self.lotto_status.setText(
            f"Saved: {Path(board_path).name} and {Path(cutout_path).name}"
        )

    def _on_generate_error(self, msg: str) -> None:
        self._board_worker = None
        self.lotto_progress.setVisible(False)
        self.generate_pdfs_btn.setEnabled(bool(self._preview_images))
        self.lotto_status.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Generation failed", msg)

    def _open_pdf(self, path: Optional[str]) -> None:
        if not path or not Path(path).exists():
            return
        import subprocess
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# ── Main window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASK Card Generator")
        self.resize(1100, 720)

        self.current_session: Optional[Path] = None
        self._preview_worker: Optional[PreviewWorker] = None
        self._stale_preview_workers: List[PreviewWorker] = []
        self._generate_worker: Optional[GenerateWorker] = None
        self._last_pdf: Optional[str] = None
        self._preview_images: List[Path] = []
        self._preview_page: int = 0
        self._preview_total_pages: int = 1

        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._build_ui()
        self._refresh_sessions()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        tabs = QTabWidget()
        outer.addWidget(tabs, stretch=1)

        # ── Cards tab (existing layout) ────────────────────────────────────────
        cards_widget = QWidget()
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 4, 0, 0)
        cards_layout.setSpacing(6)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        cards_layout.addWidget(splitter, stretch=1)
        splitter.addWidget(self._build_session_panel())
        splitter.addWidget(self._build_image_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setSizes([180, 500, 320])
        cards_layout.addWidget(self._build_bottom_bar())
        tabs.addTab(cards_widget, "Cards")

        # ── Lotto tab ──────────────────────────────────────────────────────────
        tabs.addTab(LottoTab(), "Lotto")

    def _build_session_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(150)
        panel.setMaximumWidth(240)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 6, 0)

        lbl = QLabel("Sessions")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px 0;")
        layout.addWidget(lbl)

        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self._on_session_changed)
        layout.addWidget(self.session_list, stretch=1)

        btn = QPushButton("+ New session")
        btn.clicked.connect(self._new_session)
        layout.addWidget(btn)
        return panel

    def _build_image_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 4, 0)

        self.session_title = QLabel("Select a session")
        self.session_title.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 2px 0;"
        )
        layout.addWidget(self.session_title)

        self.image_list = ImageDropList()
        self.image_list.files_dropped.connect(self._on_images_dropped)
        self.image_list.customContextMenuRequested.connect(self._image_context_menu)
        layout.addWidget(self.image_list, stretch=1)

        add_btn = QPushButton("Add images…")
        add_btn.clicked.connect(self._add_images_dialog)
        layout.addWidget(add_btn)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(180)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 0, 0)

        lbl = QLabel("Page preview")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px 0;")
        layout.addWidget(lbl)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self.preview_label = QLabel("No session selected")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_scroll.setWidget(self.preview_label)
        layout.addWidget(self.preview_scroll, stretch=1)

        # Page navigation bar
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 2, 0, 0)
        self.prev_page_btn = QPushButton("← Prev")
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self._prev_preview_page)
        nav.addWidget(self.prev_page_btn)
        self.page_counter_label = QLabel("")
        self.page_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.page_counter_label, stretch=1)
        self.next_page_btn = QPushButton("Next →")
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self._next_preview_page)
        nav.addWidget(self.next_page_btn)
        layout.addLayout(nav)
        return panel

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 4, 0, 0)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate spinner
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(160)
        layout.addWidget(self.progress_bar)

        self.open_btn = QPushButton("Open PDF")
        self.open_btn.setVisible(False)
        self.open_btn.clicked.connect(self._open_pdf)
        layout.addWidget(self.open_btn)

        self.generate_btn = QPushButton("Generate PDF")
        self.generate_btn.setEnabled(False)
        self.generate_btn.setMinimumWidth(120)
        self.generate_btn.clicked.connect(self._generate_pdf)
        layout.addWidget(self.generate_btn)
        return bar

    # ── Session management ─────────────────────────────────────────────────────

    def _refresh_sessions(self) -> None:
        # Remember which session was selected so we can restore it.
        current_name: Optional[str] = None
        if self.session_list.currentItem():
            p: Path = self.session_list.currentItem().data(Qt.ItemDataRole.UserRole)
            current_name = p.name

        self.session_list.clear()
        if not SESSIONS_DIR.exists():
            return

        restore_item: Optional[QListWidgetItem] = None
        for s in sorted(p for p in SESSIONS_DIR.iterdir() if p.is_dir()):
            count = sum(1 for f in s.iterdir() if f.suffix.lower() in IMAGE_EXTS)
            item = QListWidgetItem(f"{s.name}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.session_list.addItem(item)
            if s.name == current_name:
                restore_item = item

        if restore_item:
            self.session_list.setCurrentItem(restore_item)

    def _on_session_changed(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            self.current_session = None
            self.session_title.setText("Select a session")
            self.image_list.clear()
            self.generate_btn.setEnabled(False)
            self.preview_label.setText("No session selected")
            self._preview_images = []
            self._preview_page = 0
            self._preview_total_pages = 1
            self._update_nav_buttons()
            return

        self.current_session = current.data(Qt.ItemDataRole.UserRole)
        self.session_title.setText(self.current_session.name)
        self._preview_page = 0
        self._load_images()

    def _new_session(self) -> None:
        name, ok = QInputDialog.getText(
            self, "New session", "Session name (e.g. 2026-04-skole):"
        )
        if not ok or not name.strip():
            return
        name = name.strip().replace(" ", "-")
        new_path = SESSIONS_DIR / name
        if new_path.exists():
            QMessageBox.warning(self, "Already exists",
                                f"Session '{name}' already exists.")
            return
        new_path.mkdir(parents=True)
        self._refresh_sessions()
        # Auto-select the new session
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == new_path:
                self.session_list.setCurrentItem(item)
                break

    # ── Image management ───────────────────────────────────────────────────────

    def _load_images(self) -> None:
        self.image_list.clear()
        if self.current_session is None:
            return

        images = sorted(
            p for p in self.current_session.iterdir()
            if p.suffix.lower() in IMAGE_EXTS
        )
        for img_path in images:
            item = QListWidgetItem(
                QIcon(self._make_thumb(img_path)),
                img_path.stem.replace("_", " "),
            )
            item.setData(Qt.ItemDataRole.UserRole, img_path)
            item.setSizeHint(QSize(110, 120))
            self.image_list.addItem(item)

        self.generate_btn.setEnabled(bool(images))
        self._schedule_preview(images)

    def _make_thumb(self, img_path: Path) -> QPixmap:
        try:
            img = Image.open(img_path).convert("RGB")
            img.thumbnail((96, 96), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return QPixmap.fromImage(QImage.fromData(buf.read()))
        except Exception:
            return QPixmap()

    def _schedule_preview(self, images: List[Path]) -> None:
        self._preview_images = images
        self._preview_total_pages = max(
            1, -(-len(images) // _preview_cards_per_page()) if images else 1
        )
        self._update_nav_buttons()
        self._update_preview()

    def _update_preview(self) -> None:
        if self._preview_worker is not None:
            try:
                self._preview_worker.ready.disconnect()
            except RuntimeError:
                pass
            # Keep the old thread alive in the stale list until it finishes
            old = self._preview_worker
            self._stale_preview_workers.append(old)
            old.finished.connect(lambda w=old: self._stale_preview_workers.remove(w))
        self.preview_label.setText("Rendering…")
        worker = PreviewWorker(self._preview_images, self._preview_page)
        worker.ready.connect(self._on_preview_ready)
        self._preview_worker = worker
        worker.start()

    def _update_nav_buttons(self) -> None:
        total = self._preview_total_pages
        page = self._preview_page
        self.prev_page_btn.setEnabled(page > 0)
        self.next_page_btn.setEnabled(page < total - 1)
        self.page_counter_label.setText(
            f"Page {page + 1} / {total}" if self._preview_images else ""
        )

    def _prev_preview_page(self) -> None:
        if self._preview_page > 0:
            self._preview_page -= 1
            self._update_nav_buttons()
            self._update_preview()

    def _next_preview_page(self) -> None:
        if self._preview_page < self._preview_total_pages - 1:
            self._preview_page += 1
            self._update_nav_buttons()
            self._update_preview()

    def _on_preview_ready(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self.preview_label.setText("No images")
            return
        max_w = max(100, self.preview_scroll.width() - 20)
        if pixmap.width() > max_w:
            pixmap = pixmap.scaledToWidth(
                max_w, Qt.TransformationMode.SmoothTransformation
            )
        self.preview_label.setPixmap(pixmap)

    def _on_images_dropped(self, paths: List[Path]) -> None:
        if self.current_session is None:
            QMessageBox.warning(self, "No session",
                                "Please select or create a session first.")
            return
        for src in paths:
            dst = self.current_session / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
        self._refresh_sessions()
        self._load_images()

    def _add_images_dialog(self) -> None:
        if self.current_session is None:
            QMessageBox.warning(self, "No session",
                                "Please select or create a session first.")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add images", str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.webp *.avif)",
        )
        if files:
            self._on_images_dropped([Path(f) for f in files])

    def _image_context_menu(self, pos) -> None:
        item = self.image_list.itemAt(pos)
        if item is None:
            return
        img_path: Path = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename…")
        remove_action = menu.addAction("Remove from session")
        action = menu.exec(self.image_list.mapToGlobal(pos))
        if action == rename_action:
            current_label = img_path.stem.replace("_", " ")
            new_label, ok = QInputDialog.getText(
                self, "Rename card", "Card label:", text=current_label
            )
            if ok and new_label.strip() and new_label.strip() != current_label:
                new_stem = new_label.strip().replace(" ", "_")
                new_path = img_path.with_stem(new_stem)
                if new_path.exists():
                    QMessageBox.warning(self, "Name taken",
                                        f"'{new_path.name}' already exists.")
                else:
                    img_path.rename(new_path)
                    self._load_images()
        elif action == remove_action:
            if QMessageBox.question(
                self, "Remove image",
                f"Delete '{img_path.name}' from this session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                img_path.unlink(missing_ok=True)
                self._refresh_sessions()
                self._load_images()

    # ── PDF generation ─────────────────────────────────────────────────────────

    def _generate_pdf(self) -> None:
        if self.current_session is None or self._generate_worker is not None:
            return
        self.generate_btn.setEnabled(False)
        self.open_btn.setVisible(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Generating PDF…")

        worker = GenerateWorker(self.current_session)
        worker.done.connect(self._on_generate_done)
        worker.error.connect(self._on_generate_error)
        worker.finished.connect(worker.deleteLater)
        self._generate_worker = worker
        worker.start()

    def _on_generate_done(self, pdf_path: str) -> None:
        self._generate_worker = None
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.status_label.setText(f"Saved: {pdf_path}")
        self._last_pdf = pdf_path
        self.open_btn.setVisible(True)

    def _on_generate_error(self, message: str) -> None:
        self._generate_worker = None
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.status_label.setText(f"Error: {message}")
        QMessageBox.critical(self, "Generation failed", message)

    def _open_pdf(self) -> None:
        if not self._last_pdf or not Path(self._last_pdf).exists():
            return
        import subprocess
        if sys.platform == "win32":
            os.startfile(self._last_pdf)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self._last_pdf])
        else:
            subprocess.Popen(["xdg-open", self._last_pdf])


# ── Entry point ────────────────────────────────────────────────────────────────
def _make_app_icon() -> QIcon:
    """Generate a simple app icon — 2×2 grid of coloured picture cards."""
    icon = QIcon()
    # Card colours: warm yellow, sky blue, soft green, coral
    colours = [(255, 190, 70), (90, 175, 255), (120, 205, 110), (255, 110, 110)]
    for size in (16, 24, 32, 48, 64, 128, 256):
        img  = Image.new("RGBA", (size, size), (245, 245, 245, 255))
        draw = ImageDraw.Draw(img, "RGBA")

        margin   = max(1, size // 10)
        gap      = max(1, size // 14)
        card_sz  = (size - 2 * margin - gap) // 2
        border_w = max(1, size // 48)

        for idx, fill in enumerate(colours):
            row, col = divmod(idx, 2)
            x = margin + col * (card_sz + gap)
            y = margin + row * (card_sz + gap)
            draw.rectangle(
                [x, y, x + card_sz - 1, y + card_sz - 1],
                fill=fill,
                outline=(60, 60, 60),
                width=border_w,
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        pix = QPixmap()
        pix.loadFromData(buf.read())
        icon.addPixmap(pix)
    return icon


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ASK Card Generator")
    icon = _make_app_icon()
    app.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
