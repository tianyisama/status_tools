"""WebSocket server (desktop is the server, phones are clients).

Runs an asyncio event loop in a daemon thread. Device events are surfaced to the
Qt main thread through :class:`NetBridge` signals, which is safe across threads.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import socket
import threading

from PySide6.QtCore import QObject, Signal

from . import protocol

log = logging.getLogger(__name__)


class NetBridge(QObject):
    """Thread-safe bridge between the server thread and the Qt UI thread."""

    device_connected = Signal(str, str)      # device_id, device_name
    device_metrics = Signal(str, object)     # device_id, data dict
    device_disconnected = Signal(str)        # device_id


class MetricsServer:
    def __init__(self, config, bridge: NetBridge, device_id: str, device_name: str):
        self.config = config
        self.bridge = bridge
        self.device_id = device_id
        self.device_name = device_name
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_server = None
        self._stop_event: threading.Event = threading.Event()
        self.clients: dict[str, object] = {}   # device_id -> websocket

    # ---- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if not self.config.server_enabled:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="ws-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        async def _close() -> None:
            try:
                for ws in list(self.clients.values()):
                    try:
                        await ws.close()
                    except Exception:
                        pass
                if self._ws_server is not None:
                    self._ws_server.close()
                    await self._ws_server.wait_closed()
            except Exception:
                pass

        try:
            asyncio.run_coroutine_threadsafe(_close(), loop).result(timeout=2)
        except Exception:
            pass
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass

    # ---- internals ---------------------------------------------------------
    def _run(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
            self._loop.run_forever()
        except OSError as exc:
            log.warning("WebSocket server failed to start: %s", exc)
        finally:
            try:
                if self._loop is not None:
                    self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                    self._loop.close()
            except Exception:
                pass

    async def _serve(self) -> None:
        import websockets

        host = "0.0.0.0"
        port = self.config.service_port
        self._ws_server = await websockets.serve(self._handler, host, port)
        log.info("WebSocket server listening on %s:%s", host, port)

    async def _handler(self, websocket) -> None:
        device_id: str | None = None
        try:
            async for raw in websocket:
                msg = protocol.loads(raw if isinstance(raw, str) else raw.decode("utf-8", "ignore"))
                if not msg:
                    continue
                mtype = msg.get("type")

                if mtype == protocol.TYPE_HELLO:
                    if not protocol.major_version_ok(msg.get("protocol_version", "")):
                        break
                    device_id = msg.get("device_id") or "unknown"
                    name = msg.get("device_name") or device_id
                    self.clients[device_id] = websocket
                    ack = protocol.make_hello_ack(
                        self.device_id, self.device_name, platform.system().lower(),
                        float(self.config.update_interval_seconds),
                    )
                    await websocket.send(protocol.dumps(ack))
                    self.bridge.device_connected.emit(device_id, name)

                elif mtype == protocol.TYPE_METRICS:
                    did = msg.get("device_id") or device_id
                    if did:
                        self.bridge.device_metrics.emit(did, msg.get("data") or {})

                elif mtype == protocol.TYPE_PING:
                    await websocket.send(protocol.dumps(protocol.make_pong()))
        except Exception:
            pass
        finally:
            if device_id:
                self.clients.pop(device_id, None)
                self.bridge.device_disconnected.emit(device_id)

    # ---- outgoing ----------------------------------------------------------
    def broadcast_config(self, thresholds: dict, charging_stall_minutes: int) -> None:
        """Push alert thresholds to all connected clients (best effort)."""
        if not self._loop:
            return
        payload = protocol.dumps(protocol.make_config(thresholds, charging_stall_minutes))

        async def _send_all():
            for ws in list(self.clients.values()):
                try:
                    await ws.send(payload)
                except Exception:
                    pass

        try:
            asyncio.run_coroutine_threadsafe(_send_all(), self._loop)
        except Exception:
            pass

    def broadcast_own_metrics(self, data: dict) -> None:
        """Send this device's own metrics to all connected peers (best effort).

        This lets a connected client display the desktop as a remote device, so
        every device shows itself *and* the devices connected to it.
        """
        if not self._loop or not self.clients:
            return
        payload = protocol.dumps(protocol.make_metrics(self.device_id, data))

        async def _send_all():
            for ws in list(self.clients.values()):
                try:
                    await ws.send(payload)
                except Exception:
                    pass

        try:
            asyncio.run_coroutine_threadsafe(_send_all(), self._loop)
        except Exception:
            pass


_LOCAL_IP_CACHE: list[str] | None = None


def local_ip_addresses() -> list[str]:
    """Return likely LAN IPv4 addresses (for showing the user what to type on the phone).

    Fast and cached: resolves the egress interface via a UDP "connect" (no packet is
    actually sent), which avoids the slow ``getaddrinfo`` lookup of the machine's own
    hostname. ``getaddrinfo`` is only used as a fallback.
    """
    global _LOCAL_IP_CACHE
    if _LOCAL_IP_CACHE is not None:
        return _LOCAL_IP_CACHE

    addrs: list[str] = []
    # UDP connect just selects the egress interface; nothing is transmitted.
    for probe in ("223.5.5.5", "8.8.8.8", "1.1.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127.") and ip not in addrs:
                addrs.append(ip)
            break
        except Exception:
            try:
                s.close()
            except Exception:
                pass

    if not addrs:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip not in addrs and not ip.startswith("127."):
                    addrs.append(ip)
        except Exception:
            pass

    _LOCAL_IP_CACHE = addrs
    return addrs
