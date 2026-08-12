"""Embed a window into the Windows desktop layer (Rainmeter / Wallpaper-Engine style).

Two desktop layouts exist in the wild:
  1. The icon view (``SHELLDLL_DefView``) lives inside a ``WorkerW``; the wallpaper
     layer is the next ``WorkerW`` sibling -> parent onto that WorkerW.
  2. The icon view lives directly inside ``Progman`` (common on Windows 11); there
     is no full-screen WorkerW behind it -> parent onto Progman itself.

We handle both, then push our window to the *bottom* of the chosen parent's child
Z-order so it sits above the wallpaper but below the desktop icons, and is covered
by normal top-level windows. Never raises; returns False to trigger the fallback.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)

_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowExW.restype = wintypes.HWND
_user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.SetParent.restype = wintypes.HWND
_user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
_user32.GetParent.restype = wintypes.HWND
_user32.GetParent.argtypes = [wintypes.HWND]
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SendMessageTimeoutW.restype = wintypes.LPARAM
_user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
]
_user32.SetWindowPos.restype = wintypes.BOOL
_user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]

_WM_SPAWN_WORKERW = 0x052C
_SW_SHOW = 5
_HWND_BOTTOM = 1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_GWL_STYLE = -16
_WS_POPUP = 0x80000000
_WS_CHILD = 0x40000000


def _find_desktop_parent() -> int | None:
    """Return the HWND to parent our widget onto, or None.

    Handles the two known desktop layouts:
      B (common on Win11): ``SHELLDLL_DefView`` is a child of Progman and the
        wallpaper layer is the full-screen ``WorkerW`` sibling right behind it.
      A (common on Win10): the icon view lives in a top-level ``WorkerW`` and the
        wallpaper layer is the next top-level ``WorkerW`` sibling.
    """
    progman = _user32.FindWindowW("Progman", None)
    if not progman:
        return None

    # Encourage Explorer to materialise the wallpaper WorkerW.
    result = ctypes.c_size_t(0)
    _user32.SendMessageTimeoutW(
        progman, _WM_SPAWN_WORKERW, 0xD, 0x1, 0x0, 300, ctypes.byref(result)
    )

    # Layout B: icon view directly under Progman -> wallpaper WorkerW is the
    # Progman child that sits immediately behind SHELLDLL_DefView.
    shelldll = _user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
    if shelldll:
        workerw = _user32.FindWindowExW(progman, shelldll, "WorkerW", None)
        if workerw:
            return workerw

    # Layout A: icon view in a top-level WorkerW -> wallpaper WorkerW is the
    # next top-level WorkerW sibling after the icon host.
    holder: dict[str, int] = {}

    def _enum(hwnd, _lparam):
        if _user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            holder["h"] = hwnd
        return True

    cb = _WNDENUMPROC(_enum)
    _user32.EnumWindows(cb, 0)
    icon_host = holder.get("h")
    if icon_host and icon_host != progman:
        workerw = _user32.FindWindowExW(None, icon_host, "WorkerW", None)
        if workerw:
            return workerw

    # Last resort: Progman itself.
    return progman


def embed_into_desktop(hwnd: int) -> bool:
    """Parent ``hwnd`` into the desktop layer. Returns True on success.

    Converts the window from ``WS_POPUP`` to ``WS_CHILD`` (required by SetParent)
    and restores the original style if embedding is refused, so the caller's window
    is left healthy and can fall back to a bottom-most top-level window.
    """
    try:
        parent = _find_desktop_parent()
        if not parent:
            return False

        original_style = _user32.GetWindowLongW(hwnd, _GWL_STYLE)
        _user32.SetWindowLongW(
            hwnd, _GWL_STYLE, (original_style & ~_WS_POPUP) | _WS_CHILD
        )
        _user32.ShowWindow(hwnd, _SW_SHOW)
        _user32.SetParent(hwnd, parent)

        if _user32.GetParent(hwnd) != parent:
            # Refused (e.g. recent Windows blocks cross-process desktop parenting).
            _user32.SetWindowLongW(hwnd, _GWL_STYLE, original_style)
            return False

        # Sink to the bottom of the parent's children: above wallpaper, below icons.
        _user32.SetWindowPos(
            hwnd, _HWND_BOTTOM, 0, 0, 0, 0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
        )
        return True
    except Exception:
        return False


def unembed(hwnd: int) -> bool:
    """Detach from the desktop layer back to a normal top-level window."""
    try:
        _user32.SetParent(hwnd, None)
        return True
    except Exception:
        return False


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_int),
        ("AnimationId", ctypes.c_int),
    ]


class _WCA_DATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(_ACCENT_POLICY)),
        ("SizeOfData", ctypes.c_size_t),
    ]


_WCA_ACCENT_POLICY = 19
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_ACRYLIC = 4


def set_acrylic(hwnd: int, rgba: tuple[int, int, int, int] = (18, 18, 24, 0)) -> bool:
    """Enable Windows 10/11 acrylic (frosted-glass blur) on the window.

    ``rgba`` is a subtle tint (red, green, blue, alpha 0-255). Best-effort: on
    systems where acrylic is unavailable this simply has no visible effect.
    """
    try:
        r, g, b, a = rgba
        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_ENABLE_ACRYLIC
        accent.AccentFlags = 2
        # GradientColor is 0xAABBGGRR.
        accent.GradientColor = (a << 24) | (b << 16) | (g << 8) | r
        data = _WCA_DATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        _user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return True
    except Exception:
        return False


def clear_acrylic(hwnd: int) -> bool:
    """Disable the acrylic/accent effect (back to a normal window)."""
    try:
        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_DISABLED
        accent.AccentFlags = 0
        accent.GradientColor = 0
        data = _WCA_DATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        _user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return True
    except Exception:
        return False
