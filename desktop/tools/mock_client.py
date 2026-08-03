"""Simulated Android client for testing the desktop server + alert engine.

Connects to the desktop's WebSocket server, sends a `hello` handshake, then
streams `metrics` messages. Useful for exercising low-battery and charging-stall
alerts without a real phone.

Examples:
  # Report a healthy battery:
  python tools/mock_client.py --battery 80

  # Trigger the low-battery alert (default threshold 30%):
  python tools/mock_client.py --battery 29

  # Simulate a stalled charge (plugged but not gaining) to trigger the stall alert:
  python tools/mock_client.py --battery 29 --plugged

  # Drain 1% per tick from 35% to watch it cross the threshold:
  python tools/mock_client.py --battery 35 --drain 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time


def build_metrics(args, battery: float) -> dict:
    return {
        "cpu": {"percent": args.cpu, "core_count": 8},
        "gpu": {
            "available": False, "percent": None, "memory_used_mb": None,
            "memory_total_mb": None, "temperature_c": None,
        },
        "memory": {"percent": args.mem, "used_mb": 4820, "total_mb": 7864},
        "disk": {"percent": 60.0, "used_gb": 60.0, "total_gb": 100.0},
        "battery": {
            "present": True,
            "percent": max(0.0, battery),
            "plugged": args.plugged,
            "status": "charging" if args.plugged else "discharging",
        },
    }


async def run(args) -> None:
    import websockets

    uri = f"ws://{args.host}:{args.port}"
    print(f"connecting to {uri} ...")
    async with websockets.connect(uri) as ws:
        hello = {
            "type": "hello",
            "protocol_version": "1.0",
            "device_id": args.id,
            "device_name": args.name,
            "platform": "android",
            "app_version": "1.0.0",
            "timestamp": time.time(),
        }
        await ws.send(json.dumps(hello))
        print("sent hello")

        async def reader() -> None:
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    print(f"<- {msg.get('type')}: {json.dumps(msg, ensure_ascii=False)[:160]}")
            except Exception:
                pass

        rt = asyncio.create_task(reader())
        battery = args.battery
        sent = 0
        try:
            while True:
                msg = {
                    "type": "metrics",
                    "device_id": args.id,
                    "timestamp": time.time(),
                    "data": build_metrics(args, battery),
                }
                await ws.send(json.dumps(msg))
                sent += 1
                print(f"-> metrics #{sent} battery={battery:.0f}% plugged={args.plugged}")
                battery -= args.drain
                if args.count and sent >= args.count:
                    break
                await asyncio.sleep(args.interval)
        finally:
            rt.cancel()


def main() -> None:
    ap = argparse.ArgumentParser(description="Mock Android client for status_tools.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9700)
    ap.add_argument("--name", default="Mock Phone")
    ap.add_argument("--id", default="mock-phone-001")
    ap.add_argument("--battery", type=float, default=80.0)
    ap.add_argument("--plugged", action="store_true")
    ap.add_argument("--drain", type=float, default=0.0, help="decrease battery by this much each tick")
    ap.add_argument("--cpu", type=float, default=25.0)
    ap.add_argument("--mem", type=float, default=55.0)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--count", type=int, default=0, help="stop after this many metrics (0 = forever)")
    args = ap.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
