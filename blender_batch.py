import sys
import os
import json
import subprocess
import re
import tempfile

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QScrollArea,
    QFrame, QFileDialog, QTabWidget, QSpinBox, QProgressBar,
    QCheckBox, QMessageBox, QStackedWidget, QSizePolicy, QSplitter,
    QDoubleSpinBox, QMenu
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRectF, QSettings
from PySide6.QtGui import QColor, QPalette, QDragEnterEvent, QDropEvent, QAction, QIcon, QPixmap, QPainter, QPen, QBrush, QImage
from PySide6.QtSvg import QSvgRenderer

import blender_utils as bu

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ── Palette ────────────────────────────────────────────────────
BG_DARK    = "#1a1a1a"
BG_MID     = "#222222"
BG_CARD    = "#2a2a2a"
BG_INPUT   = "#1e1e1e"
ACCENT     = "#e87d0d"
ACCENT_DIM = "#b35c00"
TEXT_PRI   = "#ffffff"
TEXT_SEC   = "#aaaaaa"
TEXT_DIM   = "#555555"
BORDER     = "#333333"
SUCCESS    = "#4caf50"
ERROR_C    = "#f44336"
QUEUED     = "#555555"

# ── Translations Loader ───────────────────────────────────
LANGUAGES = {}
CUR_LANG_DATA = {}

def load_all_languages():
    global LANGUAGES
    base_path = resource_path("languages")
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    found = {}
    for f in os.listdir(base_path):
        if f.endswith(".json"):
            try:
                with open(os.path.join(base_path, f), "r", encoding="utf-8") as file:
                    found[f[:-5]] = json.load(file)
            except Exception: pass
    LANGUAGES = found
    return found

# Initial load for global access (default to en_US)
load_all_languages()

def get_txt(key, default=""):
    return CUR_LANG_DATA.get(key, default or key)

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRI};
    font-family: 'Segoe UI', Arial;
    font-size: 15px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-top: 1px solid {BG_MID};
    background: {BG_DARK};
}}
QTabWidget {{
    background: {BG_DARK};
}}
QTabBar::tab {{
    background: {BG_MID};
    color: {TEXT_SEC};
    padding: 8px 22px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
    background: {BG_DARK};
}}
QTabBar::tab:hover {{ color: {TEXT_PRI}; }}
QComboBox {{
    background: {BG_INPUT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 6px 10px; color: {TEXT_PRI}; min-height: 28px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {ACCENT}; margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; color: {TEXT_PRI}; outline: none;
}}
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {BG_INPUT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 6px 10px; color: {TEXT_PRI}; min-height: 28px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ background: {BG_CARD}; border: none; width: 22px; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("icons/up.svg");
    width: 10px; height: 10px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("icons/down.svg");
    width: 10px; height: 10px;
}}
QProgressBar {{
    background: {BG_DARK}; border: 1px solid {BORDER}; border-radius: 3px; text-align: center;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: {BG_MID}; width: 6px; border-radius: 3px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QPushButton {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 4px; color: {TEXT_PRI}; padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT_DIM}; }}
QCheckBox {{ color: {TEXT_SEC}; spacing: 8px; font-size: 15px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border: 1.5px solid {BORDER};
    border-radius: 4px; background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT};
    image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'%3E%3C/polyline%3E%3C/svg%3E");
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QLabel {{ color: {TEXT_PRI}; background: transparent; }}
"""

def get_badge_text(status):
    mapping = {
        "loading": "badge_loading",
        "queued":  "badge_queued",
        "running": "badge_running",
        "done":    "badge_done",
        "error":   "badge_error"
    }
    return get_txt(mapping.get(status, "badge_queued"))

# ── Utility functions now imported from blender_utils as bu ──

def find_blender_versions():
    found = []
    for base in [
        r"C:\Program Files\Blender Foundation",
        r"C:\Program Files (x86)\Blender Foundation",
        os.path.expanduser(r"~\AppData\Roaming\Blender Foundation"),
    ]:
        if os.path.isdir(base):
            for entry in os.scandir(base):
                exe = os.path.join(entry.path, "blender.exe")
                if os.path.isfile(exe):
                    found.append(exe)
    steam = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
    if os.path.isfile(steam):
        found.append(steam)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlenderFoundation")
        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                sk = winreg.OpenKey(key, winreg.EnumKey(key, i))
                path, _ = winreg.QueryValueEx(sk, "Install_Dir")
                exe = os.path.join(path, "blender.exe")
                if os.path.isfile(exe) and exe not in found:
                    found.append(exe)
            except Exception:
                pass
    except Exception:
        pass
    return list(dict.fromkeys(found))

def get_blender_label(exe):
    return bu.get_blender_label(exe)

# ── Blend info reader ──────────────────────────────────────────
BLEND_INFO_SCRIPT = """import bpy, json, sys, os
try:
    s = bpy.context.scene
    r = s.render
    path_dir, path_name = os.path.split(r.filepath) if r.filepath else ('//', '')
    data = {
        'engine':      str(r.engine),
        'frame_start': int(s.frame_start),
        'frame_end':   int(s.frame_end),
        'res_x':       int(r.resolution_x),
        'res_y':       int(r.resolution_y),
        'res_percent': int(r.resolution_percentage),
        'output_path': str(path_dir),
        'file_format': str(r.image_settings.file_format),
        'file_name':   str(path_name),
    }
    
    if data['engine'] == 'CYCLES':
        c = s.cycles
        data['cycles_samples'] = int(c.samples)
        data['cycles_noise_threshold'] = float(c.adaptive_threshold) if hasattr(c, 'adaptive_threshold') and c.use_adaptive_sampling else 0.0
    
    sys.stdout.write('BLENDINFO:' + json.dumps(data) + '\\n')
    sys.stdout.flush()
except Exception as e:
    sys.stdout.write('BLENDINFO_ERROR:' + str(e) + '\\n')
    sys.stdout.flush()
"""

class BlendInfoWorker(QThread):
    done = Signal(str, object)  # blend_path, dict or None

    def __init__(self, blend_path, blender_exe):
        super().__init__()
        self.blend_path  = blend_path
        self.blender_exe = blender_exe

    def run(self):
        info = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="blendinfo_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(BLEND_INFO_SCRIPT)

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            r = subprocess.run(
                [self.blender_exe, "--background", self.blend_path,
                 "--python", tmp_path],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
                creationflags=flags,
                env=env,
            )
            for line in (r.stdout + r.stderr).splitlines():
                if line.startswith("BLENDINFO:"):
                    info = json.loads(line[len("BLENDINFO:"):])
                    break
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass
        self.done.emit(self.blend_path, info)

# ── Thumbnail Worker ───────────────────────────────────────────
class ThumbnailWorker(QThread):
    """Read .blend thumbnail in a background thread — zero UI blocking."""
    done = Signal(str, int, int, bytes)   # path, w, h, rgba_bytes  (empty bytes = no thumb)

    def __init__(self, blend_path: str):
        super().__init__()
        self.blend_path = blend_path

    def run(self):
        result = bu.extract_blend_thumbnail(self.blend_path)
        if result:
            w, h, rgba = result
            self.done.emit(self.blend_path, w, h, rgba)
        else:
            self.done.emit(self.blend_path, 0, 0, b"")


# ── Render Worker ──────────────────────────────────────────────
class RenderWorker(QThread):
    progress = Signal(int, int)
    log_line = Signal(str)
    finished = Signal(bool)

    def __init__(self, blender_exe, blend_path, settings):
        super().__init__()
        self.blender_exe = blender_exe
        self.blend_path  = blend_path
        self.s           = settings
        self._abort      = False
        self._proc       = None

    def abort(self):
        self._abort = True
        if self._proc:
            try: self._proc.terminate()
            except Exception: pass

    def run(self):
        s = self.s
        blend_dir = os.path.dirname(self.blend_path)

        # 處理 output_path：把 // 轉成絕對路徑
        out_path = s.get('output_path', '//').strip()
        if out_path.startswith('//'):
            rel_path = out_path[2:].lstrip(os.sep)
            out_path = os.path.normpath(os.path.join(blend_dir, rel_path))
        elif not out_path:
            out_path = blend_dir

        file_prefix = s.get('file_name', '').strip()
        if not file_prefix:
            file_prefix = os.path.splitext(os.path.basename(self.blend_path))[0]
        
        _out = os.path.join(out_path, file_prefix)

        # ── Version Specific Handling (Blender 5+) ────────────────────
        blender_ver = bu.get_blender_version_tuple(self.blender_exe)
        
        script = (
            "import bpy\n"
            f"bpy.context.scene.render.engine = '{s['engine']}'\n"
            f"bpy.context.scene.frame_start = {s['frame_start']}\n"
            f"bpy.context.scene.frame_end   = {s['frame_end']}\n"
            f"bpy.context.scene.render.resolution_x = {s['res_x']}\n"
            f"bpy.context.scene.render.resolution_y = {s['res_y']}\n"
            f"bpy.context.scene.render.resolution_percentage = {s['res_percent']}\n"
            f"bpy.context.scene.render.filepath = r'{_out}'\n"
        )

        # Blender 5.0+ requires media_type set to 'VIDEO' for FFMPEG
        is_video = s['file_format'] in ("FFMPEG", "AVI_JPEG", "AVI_RAW")
        if blender_ver[0] >= 5:
            m_type = 'VIDEO' if is_video else 'IMAGE'
            script += f"bpy.context.scene.render.image_settings.media_type = '{m_type}'\n"
        
        script += f"bpy.context.scene.render.image_settings.file_format = '{s['file_format']}'\n"

        # Force safe defaults for FFMPEG to ensure output works
        if s['file_format'] == "FFMPEG":
            script += (
                "bpy.context.scene.render.ffmpeg.format = 'MPEG4'\n"
                "bpy.context.scene.render.ffmpeg.codec = 'H264'\n"
                "bpy.context.scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'\n"
                "bpy.context.scene.render.ffmpeg.audio_codec = 'AAC'\n"
            )

        script += (
            "\n# GPU/Device Config\n"
            f"dev = '{s.get('gpu_device', 'CPU')}'\n"
            "if dev != 'CPU':\n"
            "    try:\n"
            "        import bpy\n"
            "        cprefs = bpy.context.preferences.addons['cycles'].preferences\n"
            "        cprefs.compute_device_type = dev\n"
            "        for d in cprefs.get_devices_for_type(dev):\n"
            "            d.use = True\n"
            "        bpy.context.scene.cycles.device = 'GPU'\n"
            "    except: pass\n"
            "\n# Debug\n"
            "print('最終輸出路徑:', bpy.context.scene.render.filepath)\n"
        )

        if s['engine'] == 'CYCLES':
            samples = s.get('cycles_samples', 100)
            noise_thresh = s.get('cycles_noise_threshold', 0.010)
            script += (
                f"bpy.context.scene.cycles.samples = {samples}\n"
                f"bpy.context.scene.cycles.adaptive_threshold = {noise_thresh}\n"
                "bpy.context.scene.cycles.use_denoising = True\n"
            )

        fd, tmp = tempfile.mkstemp(suffix=".py", prefix="blender_render_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)

        cmd = [
            self.blender_exe, "--background", self.blend_path,
            "--python", tmp,
            "--render-anim",
            "--frame-start", str(s['frame_start']),
            "--frame-end",   str(s['frame_end']),
        ]
        total = max(1, s['frame_end'] - s['frame_start'] + 1)
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace",
                bufsize=1, creationflags=flags,
                env=env,
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                self.log_line.emit(line)
                m = re.search(r'Fra:(\d+)', line)
                if m:
                    cur = int(m.group(1)) - s['frame_start'] + 1
                    self.progress.emit(cur, total)
                if self._abort:
                    break
            self._proc.wait()
            self.finished.emit(self._proc.returncode == 0 and not self._abort)
        except Exception as e:
            self.log_line.emit(f"ERROR: {e}")
            self.finished.emit(False)
        finally:
            try: os.unlink(tmp)
            except Exception: pass

# ── Per-task settings dict (defaults) ─────────────────────────
DEFAULT_SETTINGS = {
    "engine":      "BLENDER_EEVEE_NEXT",
    "frame_start": 1,
    "frame_end":   1,
    "res_x":       1920,
    "res_y":       1080,
    "res_percent": 100,
    "output_path": "//",
    "file_format": "PNG",
    "file_name":   "",
    "cycles_samples": 100,
    "cycles_noise_threshold": 0.010,
}

# ── Custom Checkmark Widget ────────────────────────────────────
class CheckMark(QWidget):
    """
    A custom checkbox replacement drawn entirely with QPainter.
    Shows a rounded-rect border when unchecked, and a filled
    rounded rect with a crisp anti-aliased checkmark when checked.
    """
    stateChanged = Signal(int)   # 0 = unchecked, 2 = checked (matches QCheckBox API)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = True
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, val: bool):
        if self._checked != val:
            self._checked = val
            self.update()
            self.stateChanged.emit(2 if val else 0)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h   = self.width(), self.height()
        margin = 2
        rect   = QRectF(margin, margin, w - margin * 2, h - margin * 2)
        radius = 4.0

        if self._checked:
            # Filled background
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(ACCENT)))
            p.drawRoundedRect(rect, radius, radius)

            # Draw checkmark
            pen = QPen(QColor("#ffffff"))
            pen.setWidthF(2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)

            # Checkmark points scaled to widget size
            cx, cy = w / 2, h / 2
            p.drawLine(
                int(cx - 4.5), int(cy),
                int(cx - 1.5), int(cy + 3.5)
            )
            p.drawLine(
                int(cx - 1.5), int(cy + 3.5),
                int(cx + 4.5), int(cy - 3.5)
            )
        else:
            # Unchecked — border only
            pen = QPen(QColor(BORDER))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, radius, radius)

        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


# ── Task Card ──────────────────────────────────────────────────
class TaskCard(QFrame):
    removed  = Signal(object)
    selected = Signal(object)

    ST_LOADING = "loading"
    ST_QUEUED  = "queued"
    ST_RUNNING = "running"
    ST_DONE    = "done"
    ST_ERROR   = "error"

    def __init__(self, blend_path, parent=None):
        super().__init__(parent)
        self.blend_path = blend_path
        self.status     = self.ST_LOADING
        self.enabled    = True
        self.selected_active = False
        self._version_warning = False
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_frame = 0
        
        self._build()
        self._refresh()
        if self.status == self.ST_LOADING:
            self._anim_timer.start(80)

    def retranslate(self, d):
        self.del_btn.setToolTip(d["tip_del"])
        self._refresh()

    def _build(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)

        self.chk = CheckMark()
        self.chk.setChecked(True)
        self.chk.stateChanged.connect(self._on_check_change)
        lay.addWidget(self.chk)

        self.icon_lbl = QLabel("⏳")
        self.icon_lbl.setStyleSheet("font-size:16px;")
        self.icon_lbl.setFixedWidth(22)
        lay.addWidget(self.icon_lbl)

        info = QVBoxLayout(); info.setSpacing(0)
        self.name_lbl = QLabel(os.path.basename(self.blend_path))
        self.name_lbl.setStyleSheet(f"color:{TEXT_PRI};font-weight:bold;")
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100); self.prog_bar.setFixedHeight(3)
        self.prog_bar.setTextVisible(False); self.prog_bar.hide()
        info.addWidget(self.name_lbl)
        info.addWidget(self.prog_bar)
        lay.addLayout(info); lay.addStretch()

        self.status_lbl = QLabel(get_badge_text(self.ST_LOADING))
        self.status_lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:13px;")
        self.status_lbl.setFixedWidth(65)
        self.status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.status_lbl)

        # ── Version warning badge ──────────────────────────────
        self.ver_warn_lbl = QLabel("⚠")
        self.ver_warn_lbl.setFixedSize(26, 26)
        self.ver_warn_lbl.setAlignment(Qt.AlignCenter)
        self.ver_warn_lbl.setStyleSheet(
            f"color:#f5a623;font-size:15px;background:transparent;border:none;"
        )
        self.ver_warn_lbl.setToolTip("")
        self.ver_warn_lbl.hide()
        lay.addWidget(self.ver_warn_lbl)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(30, 30)
        self.del_btn = del_btn
        del_btn.setToolTip(get_txt("tip_del"))
        del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid transparent;"
            f"border-radius:4px;color:{TEXT_DIM};font-size:13px;font-weight:bold;padding:0;}}"
            f"QPushButton:hover{{background:{ERROR_C}22;border-color:{ERROR_C};color:{ERROR_C};}}"
            f"QPushButton:pressed{{background:{ERROR_C}44;}}"
        )
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(del_btn)

    def _on_check_change(self, state):
        self.enabled = (state == 2)
        if state == 2 and self.status == self.ST_DONE:
            self.status = self.ST_QUEUED
            self._refresh()
            self.prog_bar.hide()

    def set_info(self, info):
        self.set_status(self.ST_QUEUED)

    def _refresh(self):
        data = {
            self.ST_LOADING: (BORDER,    BG_MID,     TEXT_DIM, get_badge_text(self.ST_LOADING), "⏳"),
            self.ST_QUEUED:  (QUEUED,    BG_MID,     TEXT_DIM, get_badge_text(self.ST_QUEUED),  "▶"),
            self.ST_RUNNING: (ACCENT,    BG_MID,     ACCENT,   get_badge_text(self.ST_RUNNING), "⚙"),
            self.ST_DONE:    (SUCCESS,   BG_MID,     SUCCESS,  get_badge_text(self.ST_DONE),    ""),
            self.ST_ERROR:   (ERROR_C,   BG_MID,     ERROR_C,  get_badge_text(self.ST_ERROR),   "✕"),
        }
        bc, bg, sc, lbl, icon = data.get(self.status, (QUEUED, BG_CARD, TEXT_DIM, "", "▶"))
        border_color = ACCENT if self.selected_active else bc
        border_width = "2px" if self.selected_active else "1px"
        self.setStyleSheet(
            f"TaskCard{{background:{bg};border:{border_width} solid {border_color};border-radius:6px;}}"
            f"TaskCard:hover{{border-color:{ACCENT};}}"
        )
        self.status_lbl.setText(lbl)
        self.status_lbl.setStyleSheet(f"color:{sc};font-size:13px;")
        if self.status != self.ST_LOADING:
            self.icon_lbl.setText(icon)
            self.icon_lbl.setStyleSheet(f"color:{sc};font-size:16px;")
        else:
            self.icon_lbl.setStyleSheet(f"color:{ACCENT};font-size:16px;")

    def set_status(self, status):
        self.status = status
        if status == self.ST_LOADING:
            self._anim_timer.start(80)
        else:
            self._anim_timer.stop()
        self._refresh()
        if status == self.ST_RUNNING:
            self.prog_bar.show(); self.prog_bar.setValue(0)
        elif status == self.ST_DONE:
            self.prog_bar.setValue(100)
            self.chk.setChecked(False)
            self.enabled = False
        elif status == self.ST_ERROR:
            self.prog_bar.setValue(0)

    def set_progress(self, val):
        self.prog_bar.setValue(val)

    def set_version_warning(self, warn: bool, blender_ver: str = "", blend_ver: str = ""):
        self._version_warning = warn
        if warn:
            tip = f"Blender {blender_ver} 低於 .blend 版本 {blend_ver}，可能無法正確開啟"
            self.ver_warn_lbl.setToolTip(tip)
            self.ver_warn_lbl.show()
        else:
            self.ver_warn_lbl.setToolTip("")
            self.ver_warn_lbl.hide()

    def set_selected(self, active):
        self.selected_active = active
        self._refresh()

    def _on_anim_tick(self):
        if self.status == self.ST_LOADING:
            f = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            self._anim_frame = (self._anim_frame + 1) % len(f)
            self.icon_lbl.setText(f[self._anim_frame])

    def mousePressEvent(self, e):
        self.selected.emit(self)
        super().mousePressEvent(e)

# ── Drop Zone ──────────────────────────────────────────────────
class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(120)
        self.setCursor(Qt.PointingHandCursor)
        self._normal()

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        for text_key, style in [
            ("⊕",  f"color:{ACCENT};font-size:36px;background:transparent;"),
            ("drop_hint",
             f"color:{TEXT_DIM};font-size:14px;background:transparent;"),
        ]:
            text = get_txt(text_key) if text_key != "⊕" else "⊕"
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(style)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(lbl)
            if text_key == "drop_hint": self.hint_lbl = lbl

    def retranslate(self, d):
        self.hint_lbl.setText(d["drop_hint"])

    def _normal(self):
        self.setStyleSheet(
            f"DropZone{{border:2px dashed {BORDER};border-radius:8px;background:{BG_MID};}}"
            f"DropZone:hover{{border-color:{ACCENT};}}"
        )

    def _highlight(self):
        self.setStyleSheet(
            f"DropZone{{border:2px dashed {ACCENT};border-radius:8px;background:{BG_CARD};}}"
        )

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith(".blend") for u in e.mimeData().urls()
        ):
            self._highlight(); e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._normal()

    def dropEvent(self, e: QDropEvent):
        self._normal()
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith(".blend")]
        if paths:
            self.files_dropped.emit(paths)
        e.acceptProposedAction()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            paths, _ = QFileDialog.getOpenFileNames(
                self, get_txt("confirm_blend"), "", "Blender Files (*.blend)")
            if paths:
                self.files_dropped.emit(paths)
        super().mousePressEvent(e)

# ── Empty State ────────────────────────────────────────────────
class EmptyState(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        inner = QVBoxLayout()
        inner.setAlignment(Qt.AlignHCenter)
        inner.setSpacing(14)

        clapper = make_icon_label("blend.svg", 64)
        clapper.setStyleSheet("background:transparent;border:none;")
        clapper.setAlignment(Qt.AlignCenter)
        inner.addWidget(clapper, 0, Qt.AlignHCenter)

        self.hint1 = QLabel(get_txt("empty_hint1"))
        self.hint1.setStyleSheet(f"color:{TEXT_DIM};font-size:14px;background:transparent;")
        self.hint1.setAlignment(Qt.AlignCenter)
        inner.addWidget(self.hint1, 0, Qt.AlignHCenter)

        self.hint2 = QLabel(get_txt("empty_hint2"))
        self.hint2.setStyleSheet(f"color:{TEXT_DIM};font-size:14px;background:transparent;")
        self.hint2.setAlignment(Qt.AlignCenter)
        inner.addWidget(self.hint2, 0, Qt.AlignHCenter)

        outer.addLayout(inner)
        outer.addStretch()

    def retranslate(self, d):
        self.hint1.setText(d["empty_hint1"])
        self.hint2.setText(d["empty_hint2"])

def load_icon_pixmap(name: str, size: int = 32) -> QPixmap:
    """
    Load an icon from the icons/ folder as a crisp, HiDPI-aware QPixmap.

    SVG  → rendered by QSvgRenderer at physical pixel size, then devicePixelRatio
           is set so Qt treats it as a logical `size × size` pixmap. Perfectly
           sharp at any DPI with zero rasterisation artefacts.

    PNG  → tries <name_stem>@2x.<ext> first for Retina assets; falls back to the
           standard file and upscales with SmoothTransformation.

    Returns an empty QPixmap on failure.
    """
    icons_dir = resource_path("icons")
    path      = os.path.join(icons_dir, name)
    if not os.path.exists(path):
        return QPixmap()

    # ── Detect screen DPR from the running QApplication ───────────────────────
    try:
        dpr = QApplication.primaryScreen().devicePixelRatio()
    except Exception:
        dpr = 1.0
    phys = int(size * dpr)          # physical pixel count

    if name.lower().endswith(".svg"):
        renderer = QSvgRenderer(path)
        if not renderer.isValid():
            return QPixmap()
        pix = QPixmap(phys, phys)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        pix.setDevicePixelRatio(dpr)   # tell Qt this is a HiDPI pixmap
        return pix

    # ── PNG / raster ───────────────────────────────────────────────────────────
    # Try @2x asset first so we never upscale a lo-res source
    stem, ext = os.path.splitext(name)
    path_2x   = os.path.join(icons_dir, f"{stem}@2x{ext}")
    src_path  = path_2x if os.path.exists(path_2x) else path

    pix = QPixmap(src_path)
    if pix.isNull():
        return QPixmap()

    # Scale to physical pixels then tag with DPR
    pix = pix.scaled(phys, phys, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pix.setDevicePixelRatio(dpr)
    return pix


def make_icon_label(name: str, size: int = 32) -> "QLabel":
    """Create a QLabel showing a crisp icon (SVG or PNG) using QPixmap rendering."""
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("background:transparent;border:none;")
    pix = load_icon_pixmap(name, size)
    if not pix.isNull():
        lbl.setPixmap(pix)
    return lbl

def section(title, icon_file=""):
    """
    Returns (frame, content_lay, title_label).

    Layout anatomy (all values in px):
      frame padding-left : 14
      icon width         : 20
      icon↔title gap     : 8
      ─────────────────────
      content indent     : 14 + 20 + 8 = 42   ← content_lay left margin
      content right/tb   : 14 / 8 / 10

    All widgets added to content_lay are therefore left-aligned with
    the title text, with zero per-widget fiddling required.
    """
    ICON_W   = 18
    ICO_GAP  = 6
    PAD_L    = 12
    PAD_R    = 12
    PAD_TOP  = 8
    PAD_BOT  = 8
    CONTENT_INDENT = PAD_L + ICON_W + ICO_GAP   # 36 px

    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;}}"
    )
    root_lay = QVBoxLayout(frame)
    root_lay.setContentsMargins(PAD_L, PAD_TOP, PAD_R, PAD_BOT)
    root_lay.setSpacing(8)

    # ── Header row ────────────────────────────────────────────
    hdr_row = QHBoxLayout()
    hdr_row.setSpacing(ICO_GAP)
    hdr_row.setContentsMargins(0, 0, 0, 0)

    if icon_file:
        ico_lbl = make_icon_label(icon_file, ICON_W)
        hdr_row.addWidget(ico_lbl, 0, Qt.AlignVCenter)

    hdr = QLabel(title)
    hdr.setStyleSheet(
        f"color:{ACCENT};font-size:15px;font-weight:bold;letter-spacing:1px;border:none;"
    )
    hdr_row.addWidget(hdr, 0, Qt.AlignVCenter)
    hdr_row.addStretch()
    root_lay.addLayout(hdr_row)

    # ── Content layout — indented to align with title text ────
    content_lay = QVBoxLayout()
    content_lay.setContentsMargins(CONTENT_INDENT - PAD_L, 0, 0, 0)
    content_lay.setSpacing(6)
    root_lay.addLayout(content_lay)
    root_lay.addStretch()   # push content to top when frame is taller than its natural size

    # Allow the frame to expand vertically so paired frames in a QHBoxLayout equalise
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    return frame, content_lay, hdr

# ── Settings Panel ─────────────────────────────────────────────
class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = None
        self._current_version = ""
        self._loading = False
        self._on_change_cb = None
        self._thumb_worker = None   # background thumbnail loader
        self._build()
        self.engine.currentIndexChanged.connect(self._on_engine_changed)
        self._on_engine_changed()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        hrow = QHBoxLayout()
        hrow.setSpacing(12)

        # ── Thumbnail preview ──────────────────────────────────
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(96, 72)
        self.thumb_lbl.setAlignment(Qt.AlignCenter)
        self.thumb_lbl.setStyleSheet(
            f"background:{BG_INPUT};border:1px solid {BORDER};border-radius:6px;"
        )
        self.thumb_lbl.setText("🎬")
        self.thumb_lbl.setToolTip("Blend File Preview")
        hrow.addWidget(self.thumb_lbl)

        # ── File info ──────────────────────────────────────────
        vv = QVBoxLayout(); vv.setSpacing(2)
        self.fname = QLabel("—"); self.fname.setStyleSheet("font-size:15px;font-weight:bold;")
        self.fversion = QLabel(""); self.fversion.setStyleSheet(f"color:{ACCENT};font-size:11px;font-weight:bold;")
        self.fversion.hide()
        self.fpath = QLabel(""); self.fpath.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        self.fpath.setWordWrap(True)
        vv.addWidget(self.fname); vv.addWidget(self.fversion); vv.addWidget(self.fpath)
        hrow.addLayout(vv); hrow.addStretch()
        self.badge = QLabel(get_txt("badge_queued"))
        self.badge.setStyleSheet(
            f"background:{QUEUED};color:white;border-radius:4px;padding:4px 10px;font-size:11px;"
        )
        hrow.addWidget(self.badge)
        root.addLayout(hrow)

        r1 = QVBoxLayout(); r1.setSpacing(12)  # Changed to Vertical to avoid clipping

        engine_frame, el, self.sec_engine_title = section(get_txt("sec_engine"), "engine.svg")
        self.engine = QComboBox()
        self.engine.addItems(["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"])
        el.addWidget(self.engine)
        
        # Simplify Sampling: Put Sample and Device on the same row, Remove Noise Threshold
        self.cycles_group = QWidget()
        # Ensure only the container is transparent, but its inputs keep their global style
        self.cycles_group.setStyleSheet(f"QWidget#{id(self.cycles_group)}{{background:transparent;border:none;}}") 
        self.cycles_group.setObjectName(str(id(self.cycles_group)))
        csl = QVBoxLayout(self.cycles_group)
        csl.setContentsMargins(0, 8, 0, 0)
        csl.setSpacing(8)
        
        cs_row = QHBoxLayout(); cs_row.setSpacing(12)
        
        # Combined Sampling and Device Row
        sd_row = QHBoxLayout(); sd_row.setSpacing(15)
        
        # Sampling part (left)
        s_lay = QVBoxLayout(); s_lay.setSpacing(2)
        self.cycles_samples_lbl = QLabel(get_txt("cycles_samples"))
        self.cycles_samples_lbl.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;")
        self.cycles_samples = QSpinBox()
        self.cycles_samples.setRange(1, 65536); self.cycles_samples.setValue(100); self.cycles_samples.setSingleStep(32)
        s_lay.addWidget(self.cycles_samples_lbl); s_lay.addWidget(self.cycles_samples)
        sd_row.addLayout(s_lay)
        
        # Device part (right)
        d_lay = QVBoxLayout(); d_lay.setSpacing(2)
        self.gpu_lbl = QLabel("Device:")
        self.gpu_lbl.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;")
        self.gpu_dev = QComboBox()
        self.gpu_dev.addItems(["CPU", "CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"])
        d_lay.addWidget(self.gpu_lbl); d_lay.addWidget(self.gpu_dev)
        sd_row.addLayout(d_lay)
        
        csl.addLayout(sd_row)

        self.cycles_hint_lbl = QLabel(get_txt("cycles_hint"))
        self.cycles_hint_lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;border:none;")
        csl.addWidget(self.cycles_hint_lbl)
        
        self.engine_hint = QLabel(get_txt("engine_hint"))
        self.engine_hint.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;border:none;")
        el.addWidget(self.engine_hint)
        el.addWidget(self.cycles_group)
        r1.addWidget(engine_frame)

        format_frame, fl, self.sec_format_title = section(get_txt("sec_format"), "output.svg")
        self.fmt = QComboBox()
        self.fmt.addItems([
            "PNG", "JPEG", "BMP", "TIFF",
            "OPEN_EXR", "OPEN_EXR_MULTILAYER",
            "CINEON", "DPX", "FFMPEG", "HDR"
        ])
        fl.addWidget(self.fmt)
        r1.addWidget(format_frame)
        root.addLayout(r1)

        r2 = QVBoxLayout(); r2.setSpacing(12) # Vertical stacking

        range_frame, frl, self.sec_range_title = section(get_txt("sec_range"), "frame.svg")
        frow = QHBoxLayout(); frow.setSpacing(10)
        self.fs = QSpinBox()
        self.fs.setRange(1, 999999)
        self.fs.setValue(1)
        self.frame_from_lbl = QLabel(get_txt("frame_from"))
        frow.addWidget(self.frame_from_lbl)
        frow.addWidget(self.fs)
        self.fe = QSpinBox()
        self.fe.setRange(1, 999999)
        self.fe.setValue(1)
        self.frame_to_lbl = QLabel(get_txt("frame_to"))
        frow.addWidget(self.frame_to_lbl)
        frow.addWidget(self.fe)
        self.fc_lbl = QLabel(get_txt("frame_total").format(1))
        self.fc_lbl.setStyleSheet(f"color:{TEXT_DIM};")
        frow.addWidget(self.fc_lbl)
        frl.addLayout(frow)
        r2.addWidget(range_frame)

        res_frame, resl, self.sec_res_title = section(get_txt("sec_res"), "resolution.svg")
        resrow = QHBoxLayout(); resrow.setSpacing(10)
        self.rx = QSpinBox()
        self.rx.setRange(1, 16384)
        self.rx.setValue(1920)
        self.ry = QSpinBox()
        self.ry.setRange(1, 16384)
        self.ry.setValue(1080)
        self.res_w_lbl = QLabel(get_txt("res_w"))
        resrow.addWidget(self.res_w_lbl)
        resrow.addWidget(self.rx)
        self.res_h_lbl = QLabel(get_txt("res_h"))
        resrow.addWidget(self.res_h_lbl)
        resrow.addWidget(self.ry)
        self.pct_spin = QSpinBox()
        self.pct_spin.setRange(1, 1000)
        self.pct_spin.setValue(100)
        self.pct_spin.setSuffix("%")
        resrow.addWidget(self.pct_spin)
        self.res_lbl = QLabel(get_txt("res_actual").format(1920, 1080))
        self.res_lbl.setStyleSheet(f"color:{TEXT_DIM};")
        resl.addLayout(resrow)
        resl.addWidget(self.res_lbl)
        r2.addWidget(res_frame)
        root.addLayout(r2)

        output_frame, ol, self.sec_output_title = section(get_txt("sec_output"), "folder.svg")
        # Vertical stacking for labels and inputs to prevent clipping
        dir_lay = QVBoxLayout(); dir_lay.setSpacing(4)
        self.out_dir_lbl = QLabel(get_txt("out_dir"))
        self.out_dir_lbl.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;border:none;")
        dir_lay.addWidget(self.out_dir_lbl)
        
        path_h = QHBoxLayout(); path_h.setSpacing(8)
        self.out_path = QLineEdit("//")
        self.out_path.setReadOnly(True)
        path_h.addWidget(self.out_path)
        self.browse_out_btn = QPushButton(get_txt("btn_browse"))
        self.browse_out_btn.setFixedHeight(28)
        self.browse_out_btn.clicked.connect(self._browse_out)
        path_h.addWidget(self.browse_out_btn)
        dir_lay.addLayout(path_h)
        ol.addLayout(dir_lay)

        pre_lay = QVBoxLayout(); pre_lay.setSpacing(4)
        self.out_prefix_lbl = QLabel(get_txt("out_prefix"))
        self.out_prefix_lbl.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;border:none;")
        self.file_name = QLineEdit("")
        self.file_name.setPlaceholderText("(Default: .blend filename)")
        pre_lay.addWidget(self.out_prefix_lbl)
        pre_lay.addWidget(self.file_name)
        ol.addLayout(pre_lay)
        self.fn_hint = QLabel(get_txt("out_hint"))
        self.fn_hint.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;border:none;")
        ol.addWidget(self.fn_hint)
        root.addWidget(output_frame)
        root.addStretch()

        for w in [
            self.engine, self.gpu_dev, self.fmt, self.fs, self.fe, self.rx, self.ry,
            self.pct_spin, self.out_path, self.file_name,
            self.cycles_samples
        ]:
            if hasattr(w, 'currentIndexChanged'):
                w.currentIndexChanged.connect(self._on_any_change)
            elif hasattr(w, 'valueChanged'):
                w.valueChanged.connect(self._on_any_change)
            elif hasattr(w, 'textChanged'):
                w.textChanged.connect(self._on_any_change)

    def _on_engine_changed(self):
        is_cycles = self.engine.currentText() == "CYCLES"
        self.cycles_group.setVisible(is_cycles)

    def _on_any_change(self):
        if self._loading:
            return
        if self._on_change_cb:
            self._on_change_cb()

    def _upd_fc(self):
        n = max(0, self.fe.value() - self.fs.value() + 1)
        self.fc_lbl.setText(get_txt("frame_total").format(n))

    def _upd_res(self):
        p = self.pct_spin.value() / 100
        self.res_lbl.setText(
            get_txt("res_actual").format(int(self.rx.value()*p), int(self.ry.value()*p))
        )

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, get_txt("confirm_out_folder"))
        if d:
            self.out_path.setText(d + "/")

    def load(self, settings: dict, blend_path: str):
        self._loading = True
        try:
            self._current_path = blend_path
            self.fname.setText(os.path.basename(blend_path))
            self.fpath.setText(blend_path)

            # Version comes from already-loaded task_settings — no extra file I/O
            self._current_version = bu.get_blend_file_version(blend_path)
            if self._current_version:
                self.fversion.setText(f"{get_txt('blend_version', 'Blender Version:')} {self._current_version}")
                self.fversion.show()
            else:
                self.fversion.hide()

            # Kick off async thumbnail load (non-blocking)
            self._load_thumbnail(blend_path)

            s = settings
            idx = self.engine.findText(s.get("engine", ""))
            if idx >= 0: self.engine.setCurrentIndex(idx)

            self.fs.setValue(s.get("frame_start", 1))
            self.fe.setValue(s.get("frame_end",   1))
            self.rx.setValue(s.get("res_x",       1920))
            self.ry.setValue(s.get("res_y",       1080))
            self.pct_spin.setValue(s.get("res_percent", 100))
            self.out_path.setText(s.get("output_path", "//") or "//")
            self.file_name.setText(s.get("file_name", ""))
            idx = self.fmt.findText(s.get("file_format", "PNG"))
            if idx >= 0: self.fmt.setCurrentIndex(idx)

            self.cycles_samples.setValue(s.get("cycles_samples", 100))

            idx = self.gpu_dev.findText(s.get("gpu_device", "CPU"))
            if idx >= 0: self.gpu_dev.setCurrentIndex(idx)

            self._on_engine_changed()
            self._upd_fc()
            self._upd_res()
        finally:
            self._loading = False

    def _load_thumbnail(self, blend_path: str):
        """Kick off a background worker to read the thumbnail; update UI when done."""
        # Reset to placeholder immediately
        self.thumb_lbl.setPixmap(QPixmap())
        self.thumb_lbl.setText("🎬")

        # Cancel any in-flight worker for a different file
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.done.disconnect()
            self._thumb_worker.quit()
            self._thumb_worker = None

        w = ThumbnailWorker(blend_path)
        w.done.connect(self._on_thumbnail_loaded)
        self._thumb_worker = w
        w.start()

    def _on_thumbnail_loaded(self, path: str, w: int, h: int, rgba: bytes):
        """Called in the main thread once ThumbnailWorker finishes."""
        if path != self._current_path:
            return
        if not rgba or w <= 0 or h <= 0:
            self.thumb_lbl.setText("🎬")
            return

        from PySide6.QtGui import QImage

        # Flip rows bottom-up → top-down (Blender stores bottom-up)
        row     = w * 4
        buf     = bytes(rgba)
        flipped = b"".join(buf[i:i + row] for i in range((h - 1) * row, -1, -row))

        # Keep flipped alive on self so Python GC doesn't reclaim it before
        # QImage is done — QImage with raw-pointer constructor does NOT copy.
        self._thumb_buf = flipped

        img = QImage(self._thumb_buf, w, h, row, QImage.Format_RGBA8888)

        # .copy() makes Qt own the pixel data internally — safe to release self._thumb_buf
        img = img.copy()
        self._thumb_buf = None

        if img.isNull():
            self.thumb_lbl.setText("🎬")
            return

        pix = QPixmap.fromImage(img)
        if pix.isNull():
            self.thumb_lbl.setText("🎬")
            return

        try:
            dpr = QApplication.primaryScreen().devicePixelRatio()
        except Exception:
            dpr = 1.0

        phys_w = int(self.thumb_lbl.width()  * dpr)
        phys_h = int(self.thumb_lbl.height() * dpr)
        if phys_w > 0 and phys_h > 0:
            pix = pix.scaled(phys_w, phys_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pix.setDevicePixelRatio(dpr)
        self.thumb_lbl.setText("")
        self.thumb_lbl.setPixmap(pix)

    def get(self) -> dict:
        d = {
            "engine":      self.engine.currentText(),
            "frame_start": self.fs.value(),
            "frame_end":   self.fe.value(),
            "res_x":       self.rx.value(),
            "res_y":       self.ry.value(),
            "res_percent": self.pct_spin.value(),
            "output_path": self.out_path.text(),
            "file_name":   self.file_name.text(),
            "file_format": self.fmt.currentText(),
            "gpu_device":  self.gpu_dev.currentText(),
        }
        if d["engine"] == "CYCLES":
            d["cycles_samples"] = self.cycles_samples.value()
        return d

    def update_engines(self, engines: list[str]):
        cur = self.engine.currentText()
        self._loading = True
        try:
            self.engine.clear()
            self.engine.addItems(engines)
            idx = self.engine.findText(cur)
            self.engine.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._loading = False
            self._on_engine_changed()

    def update_formats(self, formats: list[str]):
        """Repopulate the output format ComboBox for the selected Blender version."""
        cur = self.fmt.currentText()
        self._loading = True
        try:
            self.fmt.clear()
            self.fmt.addItems(formats)
            idx = self.fmt.findText(cur)
            self.fmt.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._loading = False

    def set_on_change(self, callback):
        self._on_change_cb = callback

    def retranslate(self, d):
        self.sec_engine_title.setText(d['sec_engine'])
        self.sec_format_title.setText(d['sec_format'])
        self.sec_range_title.setText(d['sec_range'])
        self.sec_res_title.setText(d['sec_res'])
        self.sec_output_title.setText(d['sec_output'])

        if hasattr(self, 'fversion') and not self.fversion.isHidden() and self._current_version:
            self.fversion.setText(f"{d.get('blend_version', 'Blender Version:')} {self._current_version}")

        self.engine_hint.setText(d["engine_hint"])
        self.cycles_samples_lbl.setText(d["cycles_samples"])
        self.gpu_lbl.setText(d["cycles_device"])
        self.cycles_hint_lbl.setText(d["cycles_hint"])

        self.frame_from_lbl.setText(d["frame_from"])
        self.frame_to_lbl.setText(d["frame_to"])
        self._upd_fc()

        self.res_w_lbl.setText(d["res_w"])
        self.res_h_lbl.setText(d["res_h"])
        self._upd_res()

        self.out_dir_lbl.setText(d["out_dir"])
        self.browse_out_btn.setText(d["btn_browse"])
        self.out_prefix_lbl.setText(d["out_prefix"])
        self.fn_hint.setText(d["out_hint"])

    def set_badge(self, text, color):
        self.badge.setText(text)
        self.badge.setStyleSheet(
            f"background:{color};color:white;border-radius:4px;padding:4px 10px;font-size:11px;"
        )

# ── Progress Panel ─────────────────────────────────────────────
class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(8)

        overall_frame, ol, self.ov_title = section(get_txt("prog_overall"), "render.svg")
        self.ov_lbl = QLabel(get_txt("prog_wait"))
        self.ov_lbl.setStyleSheet(f"color:{TEXT_SEC};border:none;")
        
        ov_h = QHBoxLayout(); ov_h.setSpacing(10)
        self.ov_perc = QLabel("0%")
        self.ov_perc.setFixedWidth(40)
        self.ov_perc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ov_perc.setStyleSheet(f"color:{ACCENT};font-weight:bold;font-size:12px;border:none;")
        self.ov_bar = QProgressBar(); self.ov_bar.setFixedHeight(6) # Even thinner
        self.ov_bar.setTextVisible(False)
        ov_h.addWidget(self.ov_perc); ov_h.addWidget(self.ov_bar)
        
        ol.addWidget(self.ov_lbl); ol.addLayout(ov_h)
        overall_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum) # Minimize height
        lay.addWidget(overall_frame)

        current_frame, cl, self.cur_title = section(get_txt("prog_current"), "blend.svg")
        self.cur_lbl   = QLabel("—")
        self.cur_lbl.setStyleSheet(f"color:{TEXT_PRI};font-weight:bold;border:none;")
        
        cur_h = QHBoxLayout(); cur_h.setSpacing(10)
        self.cur_perc = QLabel("0%")
        self.cur_perc.setFixedWidth(40)
        self.cur_perc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cur_perc.setStyleSheet(f"color:{ACCENT};font-weight:bold;font-size:12px;border:none;")
        self.cur_bar = QProgressBar(); self.cur_bar.setFixedHeight(8)
        self.cur_bar.setTextVisible(False)
        cur_h.addWidget(self.cur_perc); cur_h.addWidget(self.cur_bar)
        
        self.cur_frame_lbl = QLabel("")
        self.cur_frame_lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:13px;border:none;")
        cl.addWidget(self.cur_lbl); cl.addLayout(cur_h); cl.addWidget(self.cur_frame_lbl)
        current_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum) # Minimize height
        lay.addWidget(current_frame)

        log_frame, ll, self.log_title = section(get_txt("prog_log"), "log.svg")
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setMinimumHeight(200)
        log_w = QWidget()
        self.log_lay = QVBoxLayout(log_w)
        self.log_lay.setContentsMargins(4, 4, 4, 4)
        self.log_lay.setSpacing(2)
        self.log_lay.addStretch()
        self.log_scroll.setWidget(log_w)
        # Log scroll is full-width — remove the content indent for this section
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.log_scroll)
        lay.addWidget(log_frame)

    def retranslate(self, d):
        self.ov_title.setText(d['prog_overall'])
        self.cur_title.setText(d['prog_current'])
        self.log_title.setText(d['prog_log'])
        if self.ov_lbl.text().startswith( ("Waiting", "等待") ):
            self.ov_lbl.setText(d["prog_wait"])

    def add_log(self, text):
        l = QLabel(text); l.setWordWrap(True)
        l.setStyleSheet(
            f"color:{TEXT_DIM};font-size:13px;font-family:Consolas,monospace;border:none;"
        )
        self.log_lay.insertWidget(self.log_lay.count() - 1, l)
        QTimer.singleShot(50, lambda: self.log_scroll.verticalScrollBar().setValue(
            self.log_scroll.verticalScrollBar().maximum()))

    def clear_log(self):
        while self.log_lay.count() > 1:
            item = self.log_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def set_overall(self, done, total):
        p = int(done / total * 100) if total else 0
        self.ov_bar.setValue(p)
        self.ov_perc.setText(f"{p}%")
        self.ov_lbl.setText(get_txt("prog_done").format(done, total))

    def set_current(self, name, cur, total):
        self.cur_lbl.setText(name)
        p = int(cur / total * 100) if total else 0
        self.cur_bar.setValue(p)
        self.cur_perc.setText(f"{p}%")
        self.cur_frame_lbl.setText(get_txt("prog_frame").format(cur, total))

# ── Main Window ────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blender Batch Multi-Tool")
        self.setMinimumSize(900, 600)
        self.resize(1400, 860)

        # Set Window Icon
        logo_pix = load_icon_pixmap("Rlogo.svg", 64)
        if not logo_pix.isNull():
            self.setWindowIcon(QIcon(logo_pix))

        self.task_settings: dict[str, dict | None] = {}
        self.tasks         = []
        self.selected_task = None
        self.render_worker = None
        self.render_queue  = []
        self._last_rendered_paths = []
        self.done_count    = 0
        self._info_workers: dict[str, BlendInfoWorker] = {}
        self.settings = QSettings("BlenderBatch", "Renderer")

        # Load Persisted Settings
        self.lang_key = self.settings.value("language", "zh_TW")
        last_exe = self.settings.value("blender_exe", "")
        global CUR_LANG_DATA
        CUR_LANG_DATA = LANGUAGES.get(self.lang_key, LANGUAGES.get("en_US", {}))

        self._build_ui()
        
        # Apply last exe if exists
        if last_exe and os.path.isfile(last_exe):
            self.exe_edit.setText(last_exe)
            # We skip full scan if last_exe is valid, or scan anyway?
            # Let's scan to keep the combo updated, but select last_exe.
        
        self._scan_blender()
        
        # If last_exe was in found, it will be selected by index. 
        # Otherwise, force it if it's a valid manual path.
        if last_exe and self.exe_edit.text() != last_exe:
            if os.path.isfile(last_exe):
                self.exe_edit.setText(last_exe)
                self._on_ver(-1) # Trigger engines update for custom path

        self._update_lang()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {BORDER};
            }}
            QSplitter::handle:hover {{
                background: {ACCENT};
            }}
        """)

        left = QWidget()
        left.setMinimumWidth(340)
        left.setMaximumWidth(600)
        left.setStyleSheet(f"background:{BG_MID};")
        llay = QVBoxLayout(left)
        llay.setContentsMargins(14, 14, 14, 14); llay.setSpacing(8)

        hr = QHBoxLayout()
        logo = QLabel("⬡"); logo.setStyleSheet(f"color:{ACCENT};font-size:24px;")
        hr.addWidget(logo)
        tv = QVBoxLayout(); tv.setSpacing(1)
        self.t1 = QLabel("BLENDER")
        self.t1.setStyleSheet(f"font-size:16px;font-weight:bold;letter-spacing:2px;color:{TEXT_PRI};")
        self.t2 = QLabel("BATCH RENDERER")
        self.t2.setStyleSheet(f"font-size:9px;letter-spacing:3px;color:{ACCENT};")
        tv.addWidget(self.t1); tv.addWidget(self.t2)
        hr.addLayout(tv); hr.addStretch()

        # Language Button
        self.lang_btn = QPushButton("EN")
        self.lang_btn.setFixedSize(50, 28)
        self.lang_btn.setToolTip("Switch Language")
        self.lang_btn.setStyleSheet(f"QPushButton{{background:transparent;border:1px solid {BORDER};font-size:12px;font-weight:600;color:{TEXT_SEC};}}QPushButton:hover{{color:{ACCENT};border-color:{ACCENT};}}")
        self.lang_btn.clicked.connect(self._toggle_lang)
        hr.addWidget(self.lang_btn)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{TEXT_DIM};font-size:16px;")
        hr.addWidget(self.dot)
        llay.addLayout(hr)

        self._add_sep(llay)

        self.ver_label = self._dim(get_txt("ver_label"))
        llay.addWidget(self.ver_label)
        cr = QHBoxLayout()
        self.ver_combo = QComboBox()
        self.ver_combo.setPlaceholderText(get_txt("ver_placeholder"))
        self.ver_combo.currentIndexChanged.connect(self._on_ver)
        self.scan_btn = QPushButton(get_txt("scan")); self.scan_btn.setFixedWidth(100)
        self.scan_btn.clicked.connect(self._scan_blender)
        cr.addWidget(self.ver_combo); cr.addWidget(self.scan_btn)
        llay.addLayout(cr)

        er = QHBoxLayout()
        self.exe_edit = QLineEdit()
        self.exe_edit.setPlaceholderText(get_txt("exe_placeholder"))
        self.brw_btn = QPushButton(get_txt("browse")); self.brw_btn.setFixedWidth(100)
        self.brw_btn.clicked.connect(self._browse_exe)
        er.addWidget(self.exe_edit); er.addWidget(self.brw_btn)
        llay.addLayout(er)

        self.exe_status = QLabel(get_txt("no_ver"))
        self.exe_status.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        llay.addWidget(self.exe_status)

        self._add_sep(llay)
        task_hdr = QHBoxLayout()
        task_hdr.setSpacing(8) # 圖示與文字間距
        self.task_ico_lbl = QLabel()
        self.task_ico_lbl.setFixedSize(24, 24)
        task_hdr.addWidget(self.task_ico_lbl)
        self.task_head_lbl = self._dim(get_txt("tasks"))
        task_hdr.addWidget(self.task_head_lbl)
        task_hdr.addStretch()
        self.clear_btn = QPushButton(get_txt("clear_all"))
        self.clear_btn.setFixedHeight(22)
        self.clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {BORDER};"
            f"border-radius:3px;color:{TEXT_DIM};font-size:10px;padding:0 6px;}}"
            f"QPushButton:hover{{border-color:{ERROR_C};color:{ERROR_C};}}"
        )
        self.clear_btn.clicked.connect(self._clear_all_tasks)
        task_hdr.addWidget(self.clear_btn)
        llay.addLayout(task_hdr)

        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_container = QWidget()
        self.task_lay = QVBoxLayout(self.task_container)
        self.task_lay.setContentsMargins(0, 0, 0, 0)
        self.task_lay.setSpacing(6)
        self.task_lay.addStretch()
        self.task_scroll.setWidget(self.task_container)
        llay.addWidget(self.task_scroll, 1)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._add_files)
        llay.addWidget(self.drop_zone)

        self.action_btn = QPushButton(get_txt("start_render"))
        self.action_btn.setStyleSheet(
            f"QPushButton{{background:{ACCENT};color:white;border:none;border-radius:4px;"
            f"font-size:16px;font-weight:bold;padding:12px;}}" # 字體稍微放大一點
            f"QPushButton:hover{{background:{ACCENT_DIM};}}"
            f"QPushButton:disabled{{background:{QUEUED};color:{TEXT_DIM};}}"
        )
        self.action_btn.clicked.connect(self._on_action_btn_clicked)
        llay.addWidget(self.action_btn)

        self.splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True)

        self.right_stack  = QStackedWidget()
        self.empty_state  = EmptyState()
        self.settings_pan = SettingsPanel()
        settings_scroll   = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(self.settings_pan)
        self.right_stack.addWidget(self.empty_state)
        self.right_stack.addWidget(settings_scroll)
        self.right_stack.setCurrentIndex(0)
        self.tabs.addTab(self.right_stack, get_txt("tab_settings"))

        self.prog_pan = ProgressPanel()
        ps = QScrollArea(); ps.setWidgetResizable(True); ps.setWidget(self.prog_pan)
        self.tabs.addTab(ps, get_txt("tab_progress"))

        rl.addWidget(self.tabs)
        self.splitter.addWidget(right)
        self.splitter.setSizes([320, 1080]) # Narrower left side
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        root.addWidget(self.splitter)

    def _dim(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{TEXT_SEC};font-size:15px;font-weight:600;letter-spacing:1px;")
        return l

    def _add_sep(self, layout):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setFrameShape(QFrame.NoFrame)
        sep.setStyleSheet(f"background-color:{BORDER};")
        layout.addWidget(sep)

    def _scan_blender(self):
        self.ver_combo.clear()
        found = find_blender_versions()

        # 解析版本號並排序，讓最新版本排在前面
        def get_version_key(exe):
            label = get_blender_label(exe)
            m = re.search(r"Blender (\d+)\.(\d+)(?:\.(\d+))?", label)
            if m:
                major = int(m.group(1))
                minor = int(m.group(2))
                patch = int(m.group(3)) if m.group(3) else 0
                return (major, minor, patch)
            return (0, 0, 0)

        sorted_found = sorted(found, key=get_version_key, reverse=True)

        for exe in sorted_found:
            self.ver_combo.addItem(get_blender_label(exe), userData=exe)

        if sorted_found:
            self.ver_combo.setCurrentIndex(0)
            self._on_ver(0)  # 讓介面立即更新到最新版本
        else:
            self.ver_combo.setPlaceholderText(get_txt("no_ver_found"))

    def _on_ver(self, idx):
        if idx == -1: # Custom path case from manual entry or persistence
            exe = self.exe_edit.text()
        else:
            exe = self.ver_combo.itemData(idx)
        
        if exe:
            self.exe_edit.setText(exe)
            self.exe_status.setText(f"● {os.path.basename(exe)}")
            self.exe_status.setStyleSheet(f"color:{ACCENT};font-size:11px;")
            self.settings.setValue("blender_exe", exe)
            
            engines = bu.get_supported_engines(exe)
            self.settings_pan.update_engines(engines)
            formats = bu.get_supported_formats(exe)
            self.settings_pan.update_formats(formats)
            self._check_version_warnings(exe)
        else:
            self.exe_status.setText(get_txt("no_ver"))

    def _check_version_warnings(self, exe: str):
        """
        Compare the selected Blender version against each task's .blend file version.
        Show a warning badge on any card whose .blend was saved with a newer Blender.
        If any warnings exist, show a single non-blocking status message.
        """
        if not exe or not os.path.isfile(exe):
            for card in self.tasks:
                card.set_version_warning(False)
            return

        blender_ver_tuple = bu.get_blender_version_tuple(exe)
        blender_ver_str   = ".".join(str(x) for x in blender_ver_tuple)

        warned_cards = []
        for card in self.tasks:
            blend_ver_str = bu.get_blend_file_version(card.blend_path)
            if blend_ver_str:
                blend_ver_tuple = bu.parse_version_tuple(blend_ver_str)
                if blend_ver_tuple > blender_ver_tuple:
                    card.set_version_warning(True, blender_ver_str, blend_ver_str)
                    warned_cards.append((os.path.basename(card.blend_path), blend_ver_str))
                    continue
            card.set_version_warning(False)

        # Update exe_status line to reflect warnings
        if warned_cards:
            self.exe_status.setText(
                f"⚠ Blender {blender_ver_str}  —  {len(warned_cards)} 個任務版本較新"
            )
            self.exe_status.setStyleSheet(f"color:#f5a623;font-size:11px;")
        else:
            self.exe_status.setText(f"● {os.path.basename(exe)}")
            self.exe_status.setStyleSheet(f"color:{ACCENT};font-size:11px;")

    def _browse_exe(self):
        p, _ = QFileDialog.getOpenFileName(
            self, get_txt("confirm_exe"), "", "Executable (*.exe)")
        if p:
            self.exe_edit.setText(p)
            self.exe_status.setText(f"● {os.path.basename(p)}")
            self.exe_status.setStyleSheet(f"color:{ACCENT};font-size:11px;")

    def _exe(self):
        return self.exe_edit.text().strip()

    def _add_files(self, paths):
        existing = {t.blend_path for t in self.tasks}
        for p in paths:
            if p in existing: continue
            card = TaskCard(p)
            card.removed.connect(self._remove_task)
            card.selected.connect(self._select_task)
            self.tasks.append(card)
            self.task_lay.insertWidget(self.task_lay.count() - 1, card)
            self.task_settings[p] = None
            self._start_info_load(p)
            if self.selected_task is None:
                self._select_task(card)

    def _start_info_load(self, blend_path):
        exe = self._exe()
        if not exe or not os.path.isfile(exe):
            self._on_info_loaded(blend_path, None)
            return
        if blend_path in self._info_workers:
            return
        w = BlendInfoWorker(blend_path, exe)
        w.done.connect(self._on_info_loaded)
        self._info_workers[blend_path] = w
        w.start()

    def _on_info_loaded(self, blend_path, info):
        if self.task_settings.get(blend_path) is None:
            merged = dict(DEFAULT_SETTINGS)
            if info:
                merged.update({k: v for k, v in info.items() if v is not None})
            self.task_settings[blend_path] = merged
            if self.selected_task and self.selected_task.blend_path == blend_path:
                self.settings_pan.load(merged, blend_path)
                self.right_stack.setCurrentIndex(1)

        for card in self.tasks:
            if card.blend_path == blend_path:
                card.set_info(info)
                break
        self._info_workers.pop(blend_path, None)
        # Re-check version warnings now that blend version is known
        self._check_version_warnings(self._exe())

    def _remove_task(self, card):
        if card not in self.tasks: return
        self.tasks.remove(card)
        self.task_settings.pop(card.blend_path, None)
        self.task_lay.removeWidget(card)
        card.deleteLater()
        if self.selected_task is card:
            self.selected_task = None
            if self.tasks:
                self._select_task(self.tasks[-1])
            else:
                self.right_stack.setCurrentIndex(0)

    def _select_task(self, card):
        if self.selected_task and self.selected_task is not card:
            prev_card = self.selected_task
            prev_path = prev_card.blend_path
            if self.task_settings.get(prev_path) is not None:
                self.task_settings[prev_path] = self.settings_pan.get()

        # Update visuals for all cards
        for t in self.tasks:
            t.set_selected(t is card)

        self.selected_task = card
        
        if card.status == TaskCard.ST_LOADING:
            self.right_stack.setCurrentIndex(0)
        else:
            self.right_stack.setCurrentIndex(1)
            s = self.task_settings.get(card.blend_path)
            if s is None:
                s = dict(DEFAULT_SETTINGS)
            self.settings_pan.load(s, card.blend_path)
            self.settings_pan.set_on_change(self._auto_save_current)
            self.settings_pan.set_badge(get_badge_text(card.status), self._get_status_color(card.status))

    def _get_status_color(self, status):
        colors = {
            TaskCard.ST_LOADING: TEXT_DIM,
            TaskCard.ST_QUEUED:  QUEUED,
            TaskCard.ST_RUNNING: ACCENT,
            TaskCard.ST_DONE:    SUCCESS,
            TaskCard.ST_ERROR:   ERROR_C,
        }
        return colors.get(status, QUEUED)

    def _auto_save_current(self):
        if self.selected_task:
            p = self.selected_task.blend_path
            self.task_settings[p] = self.settings_pan.get()

    def _save_current(self):
        if self.selected_task:
            p = self.selected_task.blend_path
            if self.task_settings.get(p) is not None:
                self.task_settings[p] = self.settings_pan.get()

    def _on_action_btn_clicked(self):
        if self.render_worker and self.render_worker.isRunning():
            self._stop()
        else:
            self._start()

    def _toggle_lang(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"background:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {BORDER};")
        for k in LANGUAGES.keys():
            act = QAction(k, self)
            act.triggered.connect(lambda checked=False, key=k: self._change_lang(key))
            menu.addAction(act)
        menu.exec(self.lang_btn.mapToGlobal(self.lang_btn.rect().bottomLeft()))

    def _change_lang(self, key):
        self.lang_key = key
        global CUR_LANG_DATA
        CUR_LANG_DATA = LANGUAGES.get(key, {})
        self.lang_btn.setText(key.split('_')[0].upper())
        self.settings.setValue("language", key)
        self._update_lang()

    def _update_lang(self):
        d = CUR_LANG_DATA
        if not d: return
        self.setWindowTitle(d["title"])
        self.ver_label.setText(d["ver_label"])
        
        # 任務標籤同步 (使用獨立圖示標籤避免 HTML 偏移)
        self.task_head_lbl.setText(d["tasks"])
        pix = load_icon_pixmap("blend.svg", 22)
        if not pix.isNull():
            self.task_ico_lbl.setPixmap(pix)
        
        self.ver_combo.setPlaceholderText(d["ver_placeholder"])
        self.scan_btn.setText(d["scan"])
        self.exe_edit.setPlaceholderText(d["exe_placeholder"])
        self.brw_btn.setText(d["browse"])
        self.clear_btn.setText(d["clear_all"])

        self.action_btn.setIcon(QIcon()) # 清除舊圖示
        self._set_action_btn_state(self.render_worker and self.render_worker.isRunning())
        
        self.tabs.setTabText(0, d["tab_settings"])
        self.tabs.setTabText(1, d["tab_progress"])
        
        # Update current exe status if not selected
        if not self._exe():
            self.exe_status.setText(d["no_ver"])

        # Update Children
        self.settings_pan.retranslate(d)
        self.prog_pan.retranslate(d)
        self.empty_state.retranslate(d)
        self.drop_zone.retranslate(d)
        
        for task in self.tasks:
            task.retranslate(d)

    def _set_action_btn_state(self, rendering: bool):
        txt = get_txt("stop_render") if rendering else get_txt("start_render")
        # 移除文字開頭的所有非文字元（符號、空格等）
        txt_clean = re.sub(r'^[^\w\u4e00-\u9fff]+', '', txt).strip()
        self.action_btn.setText(f" {txt_clean}")
        
        # 設定圖示
        pix = load_icon_pixmap("start.svg", 20)
        if not pix.isNull():
            self.action_btn.setIcon(QIcon(pix))
            self.action_btn.setIconSize(QSize(20, 20))

        if rendering:
            self.action_btn.setStyleSheet(
                f"QPushButton{{background:{BG_CARD};color:{ERROR_C};border:2px solid {ERROR_C};"
                f"border-radius:4px;font-size:14px;font-weight:bold;padding:12px;}}"
                f"QPushButton:hover{{background:{ERROR_C};color:white;}}"
            )
        else:
            self.action_btn.setStyleSheet(
                f"QPushButton{{background:{ACCENT};color:white;border:none;border-radius:4px;"
                f"font-size:14px;font-weight:bold;padding:12px;}}"
                f"QPushButton:hover{{background:{ACCENT_DIM};}}"
                f"QPushButton:disabled{{background:{QUEUED};color:{TEXT_DIM};}}"
            )

    def _start(self):
        self._save_current()
        exe = self._exe()
        if not os.path.isfile(exe):
            QMessageBox.warning(self, get_txt("badge_error"), get_txt("msg_no_exe"))
            return
        supported = bu.get_supported_engines(exe)
        bad = []
        for t in self.tasks:
            if t.enabled and t.status not in (TaskCard.ST_RUNNING, TaskCard.ST_LOADING):
                s = self.task_settings.get(t.blend_path) or {}
                eng = s.get("engine", "")
                if eng and eng not in supported:
                    bad.append(f"{os.path.basename(t.blend_path)}: {eng}")
        if bad:
            msg = get_txt("msg_engine_unsupported") + "\n\n"
            msg += "\n".join(bad)
            msg += f"\n\n" + get_txt("msg_version_support") + f" {', '.join(supported)}"
            QMessageBox.warning(self, get_txt("badge_error"), msg)
            return

        # ── Version mismatch warning ───────────────────────────
        blender_ver_tuple = bu.get_blender_version_tuple(exe)
        blender_ver_str   = ".".join(str(x) for x in blender_ver_tuple)
        ver_mismatch = []
        for t in self.tasks:
            if t.enabled and t.status not in (TaskCard.ST_RUNNING, TaskCard.ST_LOADING):
                blend_ver = bu.get_blend_file_version(t.blend_path)
                if blend_ver and bu.parse_version_tuple(blend_ver) > blender_ver_tuple:
                    ver_mismatch.append(
                        f"  • {os.path.basename(t.blend_path)}  （儲存版本 {blend_ver}）"
                    )
        if ver_mismatch:
            msg = (
                f"以下任務的 .blend 版本高於目前選擇的 Blender {blender_ver_str}，\n"
                f"可能導致部分功能無法正確算圖：\n\n"
                + "\n".join(ver_mismatch)
                + "\n\n是否仍要繼續算圖？"
            )
            reply = QMessageBox.warning(
                self, "版本不相容警告", msg,
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if reply != QMessageBox.Yes:
                return
        self.render_queue = [
            t for t in self.tasks
            if t.enabled and t.status not in (TaskCard.ST_RUNNING, TaskCard.ST_LOADING)
        ]
        if not self.render_queue:
            QMessageBox.information(self, get_txt("msg_info"), get_txt("msg_no_task")); return
        self.done_count = 0
        self._last_rendered_paths = []
        self.prog_pan.clear_log()
        self.prog_pan.set_overall(0, len(self.render_queue))
        self.tabs.setCurrentIndex(1)
        
        self._set_action_btn_state(True)
        self.dot.setStyleSheet(f"color:{ACCENT};font-size:16px;")
        self._next()

    def _next(self):
        if not self.render_queue: self._all_done(); return
        task  = self.render_queue.pop(0)
        blend = task.blend_path
        s     = self.task_settings.get(blend) or dict(DEFAULT_SETTINGS)
        task.set_status(TaskCard.ST_RUNNING)
        total = max(1, s['frame_end'] - s['frame_start'] + 1)
        self.prog_pan.set_current(os.path.basename(blend), 0, total)
        self.prog_pan.add_log(get_txt("log_start").format(blend))
        self.render_worker = RenderWorker(self._exe(), blend, s)
        self.render_worker.progress.connect(lambda c, t, tk=task: self._on_prog(tk, c, t))
        self.render_worker.log_line.connect(self.prog_pan.add_log)
        self.render_worker.finished.connect(lambda ok, tk=task: self._on_done(tk, ok))
        self.render_worker.start()

    def _on_prog(self, task, cur, total):
        task.set_progress(int(cur / total * 100) if total else 0)
        self.prog_pan.set_current(os.path.basename(task.blend_path), cur, total)

    def _on_done(self, task, ok):
        task.set_status(TaskCard.ST_DONE if ok else TaskCard.ST_ERROR)
        self.prog_pan.add_log(f"{'✓' if ok else '✗'} {task.blend_path}")
        if ok:
            self._last_rendered_paths.append(task.blend_path)
        self.done_count += 1
        remaining = len(self.render_queue)
        self.prog_pan.set_overall(
            self.done_count,
            self.done_count + remaining + (1 if remaining else 0)
        )
        self._next()

    def _open_output_folder(self, blend_path):
        s = self.task_settings.get(blend_path) or {}
        out = s.get("output_path", "//") or "//"
        if out.startswith("//"):
            base = os.path.dirname(blend_path)
            out = os.path.join(base, out[2:])
        out = os.path.normpath(out)
        if not os.path.isdir(out):
            out = os.path.dirname(out)
        if os.path.isdir(out):
            if sys.platform == "win32":
                os.startfile(out)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out])
            else:
                subprocess.Popen(["xdg-open", out])

    def _all_done(self):
        self.prog_pan.add_log(get_txt("all_done"))
        self.prog_pan.set_overall(self.done_count, self.done_count)
        self._set_action_btn_state(False)
        self.dot.setStyleSheet(f"color:{SUCCESS};font-size:16px;")

        # Open unique output folders
        opened_dirs = set()
        for blend_path in self._last_rendered_paths:
            s = self.task_settings.get(blend_path) or {}
            out = s.get("output_path", "//") or "//"
            if out.startswith("//"):
                base = os.path.dirname(blend_path)
                out = os.path.join(base, out[2:])
            out = os.path.normpath(out)
            if not os.path.isdir(out):
                out = os.path.dirname(out)
            
            if os.path.isdir(out) and out not in opened_dirs:
                opened_dirs.add(out)
                if sys.platform == "win32":
                    os.startfile(out)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", out])
                else:
                    subprocess.Popen(["xdg-open", out])

    def _clear_all_tasks(self):
        for card in list(self.tasks):
            if card.status != TaskCard.ST_RUNNING:
                self._remove_task(card)

    def _stop(self):
        if self.render_worker: self.render_worker.abort()
        self.render_queue.clear()
        self._set_action_btn_state(False)
        self.dot.setStyleSheet(f"color:{ERROR_C};font-size:16px;")
        self.prog_pan.add_log(get_txt("stopped"))

    def closeEvent(self, e):
        self._stop()
        for w in list(self._info_workers.values()):
            w.quit(); w.wait(1000)
        super().closeEvent(e)

# ── Entry ──────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG_DARK))
    pal.setColor(QPalette.WindowText,      QColor(TEXT_PRI))
    pal.setColor(QPalette.Base,            QColor(BG_INPUT))
    pal.setColor(QPalette.AlternateBase,   QColor(BG_MID))
    pal.setColor(QPalette.Text,            QColor(TEXT_PRI))
    pal.setColor(QPalette.Button,          QColor(BG_CARD))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT_PRI))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()