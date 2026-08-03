"""Protocol (de)serialisation — mirrors protocol/SPEC.md.

Messages are single-line JSON objects with a top-level ``type``. Helpers here
build and parse the messages the desktop side sends/receives.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from .. import PROTOCOL_VERSION

TYPE_HELLO = "hello"
TYPE_HELLO_ACK = "hello_ack"
TYPE_METRICS = "metrics"
TYPE_PING = "ping"
TYPE_PONG = "pong"
TYPE_CONFIG = "config"


def now_ts() -> float:
    return time.time()


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(text: str) -> Optional[dict]:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def major_version_ok(version: str) -> bool:
    """True when the peer's major protocol version matches ours."""
    try:
        return str(version).split(".")[0] == PROTOCOL_VERSION.split(".")[0]
    except Exception:
        return False


# ---- builders --------------------------------------------------------------
def make_hello_ack(device_id: str, device_name: str, platform: str,
                   interval_seconds: float) -> dict:
    return {
        "type": TYPE_HELLO_ACK,
        "protocol_version": PROTOCOL_VERSION,
        "device_id": device_id,
        "device_name": device_name,
        "platform": platform,
        "interval_seconds": interval_seconds,
        "timestamp": now_ts(),
    }


def make_metrics(device_id: str, data: dict) -> dict:
    return {
        "type": TYPE_METRICS,
        "device_id": device_id,
        "timestamp": now_ts(),
        "data": data,
    }


def make_pong() -> dict:
    return {"type": TYPE_PONG, "timestamp": now_ts()}


def make_config(thresholds: dict, charging_stall_minutes: int) -> dict:
    return {
        "type": TYPE_CONFIG,
        "thresholds": thresholds,
        "charging_stall_minutes": charging_stall_minutes,
        "timestamp": now_ts(),
    }
