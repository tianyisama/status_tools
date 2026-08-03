"""X11 desktop embedding (Phase 5).

For now returns False so the widget uses the bottom-most fallback window. A full
implementation sets ``_NET_WM_WINDOW_TYPE`` to ``_NET_WM_WINDOW_TYPE_DESKTOP``
before mapping; Wayland has no portable equivalent.
"""

from __future__ import annotations


def set_desktop_window(hwnd: int) -> bool:  # noqa: ARG001
    return False
