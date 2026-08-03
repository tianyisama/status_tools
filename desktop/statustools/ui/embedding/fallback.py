"""Fallback: keep the widget as a bottom-most top-level window (not embedded)."""

from __future__ import annotations

from ...platform_utils import is_windows


def keep_at_bottom(hwnd: int) -> None:
    """Reassert HWND_BOTTOM on Windows (the Qt flag usually suffices)."""
    if not is_windows():
        return
    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        HWND_BOTTOM = 1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        user32.SetWindowPos(
            hwnd, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except Exception:
        pass
