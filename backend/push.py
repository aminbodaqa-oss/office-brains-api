from __future__ import annotations

import asyncio
import json
from urllib.request import Request, urlopen

from database import deactivate_push_device, finish_push, pending_pushes


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _send_expo_message(item: dict) -> dict:
    payload = {
        "to": item["token"],
        "title": item["title"],
        "body": item["message"],
        "sound": "default",
        "priority": "high",
        "channelId": "office-updates",
        "data": {
            "notification_id": item["notification_id"],
            "employee_id": item.get("employee_id"),
        },
    }
    request = Request(
        EXPO_PUSH_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=8) as response:
        result = json.loads(response.read().decode("utf-8"))
    ticket = result.get("data") or {}
    if isinstance(ticket, list):
        ticket = ticket[0] if ticket else {}
    return ticket if isinstance(ticket, dict) else {}


async def push_delivery_loop() -> None:
    while True:
        try:
            items = pending_pushes(25)
            for item in items:
                try:
                    ticket = await asyncio.to_thread(_send_expo_message, item)
                    if ticket.get("status") == "ok":
                        finish_push(item["id"], True)
                        continue
                    details = ticket.get("details") or {}
                    error = str(details.get("error") or ticket.get("message") or "Expo rejected the push")
                    if details.get("error") == "DeviceNotRegistered":
                        deactivate_push_device(item["token"])
                    finish_push(item["id"], False, error)
                except Exception as exc:
                    finish_push(item["id"], False, str(exc))
        except Exception:
            # Keep the office API alive even if Expo Push is temporarily unavailable.
            pass
        await asyncio.sleep(12)
