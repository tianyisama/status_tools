"""Widget colour themes and desktop-background adaptation.

The widget sits on the wallpaper, so a single fixed palette looks wrong on a
bright desktop. We sample the screen luminance outside the widget every few
seconds and swap between a dark glass palette and a light glass palette so the
text always stays readable. Manual override is possible via settings
(theme_mode = "auto" | "dark" | "light").
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QWidget

# ---- palettes -------------------------------------------------------------


@dataclass(frozen=True)
class WidgetTheme:
    name: str            # "dark" | "light"
    bg: QColor           # glass body colour (opacity applied from settings)
    bg_dim: QColor       # gradient-bottom body colour
    border: QColor       # 1px outer edge
    glow: QColor         # soft top highlight for the glass edge
    fg: QColor           # primary text
    fg_dim: QColor       # secondary text
    track: QColor        # progress-bar background
    card: QColor         # metric card fill
    card_border: QColor
    button: QColor
    button_hover: QColor
    button_fg: QColor
    good: QColor         # status colours: readable on this theme's glass
    warn: QColor
    bad: QColor
    accent: QColor


DARK = WidgetTheme(
    name="dark",
    bg=QColor(28, 28, 38),
    bg_dim=QColor(20, 20, 29),
    border=QColor(255, 255, 255, 52),
    glow=QColor(255, 255, 255, 26),
    fg=QColor(235, 236, 240),
    fg_dim=QColor(150, 152, 160),
    track=QColor(255, 255, 255, 22),
    card=QColor(255, 255, 255, 13),
    card_border=QColor(255, 255, 255, 24),
    button=QColor(255, 255, 255, 14),
    button_hover=QColor(255, 255, 255, 34),
    button_fg=QColor(205, 208, 216),
    good=QColor(76, 217, 123),
    warn=QColor(255, 180, 84),
    bad=QColor(255, 92, 92),
    accent=QColor(96, 150, 255),
)

LIGHT = WidgetTheme(
    name="light",
    bg=QColor(255, 255, 255),
    bg_dim=QColor(244, 245, 250),
    border=QColor(0, 0, 0, 40),
    glow=QColor(255, 255, 255, 120),
    fg=QColor(24, 24, 32),
    fg_dim=QColor(108, 110, 122),
    track=QColor(0, 0, 0, 24),
    card=QColor(255, 255, 255, 130),
    card_border=QColor(255, 255, 255, 210),
    button=QColor(0, 0, 0, 12),
    button_hover=QColor(0, 0, 0, 26),
    button_fg=QColor(48, 50, 60),
    good=QColor(46, 158, 79),
    warn=QColor(217, 138, 31),
    bad=QColor(217, 74, 74),
    accent=QColor(31, 111, 224),
)

_PALETTES = {"dark": DARK, "light": LIGHT}


def get(name: str) -> WidgetTheme:
    return _PALETTES.get(name, DARK)


# ---- helpers for stylesheets ---------------------------------------------


def rgba(c: QColor) -> str:
    """``rgba(r,g,b,a)`` string for Qt stylesheets."""
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


def hex(c: QColor) -> str:
    return c.name()


# ---- wallpaper luminance sampling ----------------------------------------

_GRID_W, _GRID_H = 64, 36


def sample_wallpaper_luminance(widget: QWidget) -> float | None:
    """Average 0..1 luminance of the wallpaper around the widget, or None.

    Grabs the screen, downscales it to a small grid and averages the pixels
    *outside* the widget's own rect (the widget is translucent glass, so its
    own pixels would bias the sample). On Windows a GDI BitBlt grab is tried
    first (works even when Qt cannot open the monitor interface, e.g. in
    service/sandboxed sessions); QScreen.grabWindow is the cross-platform
    fallback. Returns None on any failure so the caller keeps the current
    theme.
    """
    try:
        import os

        if os.name == "nt":
            lum = _sample_win32_gdi(widget)
            if lum is not None:
                return lum
    except Exception:
        pass
    return _sample_qt_screen(widget)


def _sample_qt_screen(widget: QWidget) -> float | None:
    try:
        screen = widget.screen()
        if screen is None:
            return None
        pix = screen.grabWindow(0)
        if pix is None or pix.isNull():
            return None
        # grabWindow() may return a device-pixel-ratio-sized image; normalise
        # to logical screen coordinates so the widget rect maps 1:1.
        img = (
            pix.toImage()
            .scaled(
                screen.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            .scaled(
                _GRID_W,
                _GRID_H,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            .convertToFormat(QImage.Format.Format_Grayscale8)
        )
        data = _gray_bytes(img)
        if len(data) < _GRID_W * _GRID_H:
            return None

        # Exclude the widget's own rect, clamped to the grid.
        sw, sh = max(1, screen.width()), max(1, screen.height())
        g = widget.frameGeometry()
        sx = max(0, min(_GRID_W, g.x() * _GRID_W // sw))
        sy = max(0, min(_GRID_H, g.y() * _GRID_H // sh))
        ex = max(0, min(_GRID_W, (g.x() + g.width()) * _GRID_W // sw))
        ey = max(0, min(_GRID_H, (g.y() + g.height()) * _GRID_H // sh))

        total = 0
        count = 0
        for y in range(_GRID_H):
            row = y * _GRID_W
            for x in range(_GRID_W):
                if sx <= x < ex and sy <= y < ey:
                    continue
                total += data[row + x]
                count += 1
        if count == 0:
            return None
        return total / count / 255.0
    except Exception:
        return None


def _gray_bytes(img: QImage) -> bytes:
    """Byte array of a Grayscale8 image (one byte per pixel)."""
    try:
        # constScanLine is stride-safe; one byte per pixel in Grayscale8.
        return b"".join(bytes(img.constScanLine(y)) for y in range(img.height()))
    except Exception:
        return bytes(img.pixelColor(x, y).red() for y in range(img.height()) for x in range(img.width()))


def _sample_win32_gdi(widget: QWidget) -> float | None:
    """Windows: capture the virtual screen with GDI and average its luminance.

    Fallback used before the Qt grab: unlike ``QScreen.grabWindow`` it needs
    only a desktop DC, which is available in interactive sessions even when Qt
    cannot open the monitor interface.
    """
    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

        SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
        SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if vw <= 0 or vh <= 0:
            return None

        dc = user32.GetDC(None)
        if not dc:
            return None
        mem = None
        bmp = None
        try:
            mem = gdi32.CreateCompatibleDC(dc)
            bmp = gdi32.CreateCompatibleBitmap(dc, vw, vh)
            gdi32.SelectObject(mem, bmp)
            # SRCCOPY blit of the whole virtual screen.
            if not gdi32.BitBlt(mem, 0, 0, vw, vh, dc, vx, vy, 0x00CC0020):
                return None

            class _InfoHeader(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32),
                    ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            header = _InfoHeader()
            header.biSize = ctypes.sizeof(_InfoHeader)
            header.biWidth = vw
            header.biHeight = -vh  # top-down rows
            header.biPlanes = 1
            header.biBitCount = 24
            header.biCompression = 0  # BI_RGB
            buf = ctypes.create_string_buffer(vw * vh * 3)
            if gdi32.GetDIBits(mem, bmp, 0, vh, buf, ctypes.byref(header), 0) == 0:
                return None

            # Widget rect in physical pixels (GDI coords).
            g = widget.frameGeometry()
            dpr = float(widget.devicePixelRatioF() or 1.0)
            gx = int(g.x() * dpr) - vx
            gy = int(g.y() * dpr) - vy
            gw, gh = int(g.width() * dpr), int(g.height() * dpr)

            data = buf.raw
            stride = vw * 3
            step = 6  # sample every 6th pixel (~50k iterations for 1080p)
            total = 0
            count = 0
            for y in range(0, vh, step):
                row = y * stride
                in_row = gy <= y < gy + gh
                for x in range(0, vw, step):
                    if in_row and gx <= x < gx + gw:
                        continue
                    i = row + x * 3
                    total += (data[i] * 114 + data[i + 1] * 587 + data[i + 2] * 299) // 1000
                    count += 1
            if count == 0:
                return None
            return total / count / 255.0
        finally:
            if bmp:
                gdi32.DeleteObject(bmp)
            if mem:
                gdi32.DeleteDC(mem)
            user32.ReleaseDC(None, dc)
    except Exception:
        return None


# ---- hysteresis ------------------------------------------------------------

_HI = 0.52  # luminance at/above this switches dark -> light
_LO = 0.42  # luminance at/below this switches light -> dark


def resolve(theme_mode: str, luminance: float | None, current: str) -> str:
    """Pick the theme name for the given mode + sampled luminance.

    ``theme_mode`` is the config value ("auto"/"dark"/"light"); ``current`` is
    the theme in use, providing a dead band so mid-grey wallpapers do not
    flicker.
    """
    if theme_mode != "auto":
        return theme_mode
    if luminance is None:
        return current or "dark"
    if current == "dark":
        return "light" if luminance >= _HI else "dark"
    return "dark" if luminance <= _LO else "light"
