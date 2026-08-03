"""Deliver alert notifications (tray toast) and append them to a JSONL log."""

from __future__ import annotations

import json
import time

from ..platform_utils import alert_log_path


class Notifier:
    def __init__(self, tray=None):
        self.tray = tray

    def notify(self, title: str, message: str, warning: bool = True) -> None:
        if self.tray is not None:
            try:
                self.tray.notify(title, message, warning)
            except Exception:
                pass
        self._log(title, message, warning)

    @staticmethod
    def _log(title: str, message: str, warning: bool) -> None:
        try:
            with open(alert_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {"ts": time.time(), "title": title, "message": message, "warning": warning},
                    ensure_ascii=False,
                ) + "\n")
        except Exception:
            pass
