"""UDP discovery responder (desktop).

Phones broadcast a small JSON ``discover`` datagram to the LAN broadcast address
on ``discovery_port``; this responder replies unicast with a ``discover_ack`` that
carries the device name and the WebSocket ``service_port``, so the phone can
auto-fill the address instead of the user typing it. See protocol/SPEC.md.
"""

from __future__ import annotations

import json
import logging
import platform
import socket
import threading

from .. import PROTOCOL_VERSION

log = logging.getLogger(__name__)


class DiscoveryResponder:
    def __init__(self, config, device_id: str, device_name: str):
        self.config = config
        self.device_id = device_id
        self.device_name = device_name
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if not self.config.server_enabled:
            return
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", self.config.discovery_port))
            self._sock.settimeout(1.0)
        except OSError as exc:
            log.warning("Discovery responder failed to bind: %s", exc)
            self._sock = None
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="udp-discovery")
        self._thread.start()
        log.info("Discovery responder listening on UDP :%s", self.config.discovery_port)

    def _run(self) -> None:
        assert self._sock is not None
        while self._running:
            try:
                data, addr = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                msg = json.loads(data.decode("utf-8", "ignore"))
            except Exception:
                continue
            if not isinstance(msg, dict) or msg.get("type") != "discover":
                continue

            ack = {
                "type": "discover_ack",
                "protocol_version": PROTOCOL_VERSION,
                "device_id": self.device_id,
                "device_name": self.device_name,
                "platform": platform.system().lower(),
                "service_port": self.config.service_port,
            }
            try:
                self._sock.sendto(json.dumps(ack, ensure_ascii=False).encode("utf-8"), addr)
            except Exception:
                pass

    def stop(self) -> None:
        self._running = False
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
