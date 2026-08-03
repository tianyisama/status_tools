"""Desktop-embedding dispatcher.

``apply_embedding(widget, config)`` tries to attach the widget to the desktop
layer (Windows WorkerW / X11 DESKTOP window type). It returns ``True`` when the
widget is embedded, ``False`` when the caller should rely on the bottom-most
fallback window. Any failure falls back silently so the app always works.
"""

from __future__ import annotations

from ...platform_utils import is_linux, is_wayland, is_windows


def apply_embedding(widget, config) -> bool:
    if not getattr(config, "embed_desktop", False):
        return False

    hwnd = int(widget.winId())

    if is_windows():
        try:
            from .windows import embed_into_desktop

            return bool(embed_into_desktop(hwnd))
        except Exception:
            return False

    if is_linux() and not is_wayland():
        try:
            from .linux_x11 import set_desktop_window

            return bool(set_desktop_window(hwnd))
        except Exception:
            return False

    return False
