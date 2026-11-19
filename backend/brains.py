from __future__ import annotations
import asyncio
import json
import os
import urllib.error
import urllib.request

PROVIDER = os.getenv("BRAIN_PROVIDER", "demo").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "90"))

class BrainUnavailable(RuntimeError):
    pass

def _ollama_chat(messages: list[dict[str, str]]) -> str:
    body = json.dumps({"model": OLLAMA_MODEL, "messages": messages, "stream": False}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA_BASE_URL + "/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("message", {}).get("content", "").strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BrainUnavailable("تعذر الاتصال بمحرك الذكاء الاصطناعي المحلي. راجع عنوان Ollama وحالة النموذج.") from exc

def _demo_message() -> str:
    return "الـAPI شغال، لكن عقل الذكاء الاصطناعي المحلي لسه مش متوصل. دي نسخة تجهيز واختبار اتصال، ومش هقدّم ردود تمثيلية على إنها تفكير حقيقي. بعد تشغيل نموذج محلي متوافق مع Ollama، غيّر BRAIN_PROVIDER إلى ollama واضبط عنوانه واسم النموذج."

async def generate(messages: list[dict[str, str]]) -> str:
    if PROVIDER == "demo":
        return _demo_message()
    if PROVIDER != "ollama":
        raise BrainUnavailable("قيمة BRAIN_PROVIDER غير مدعومة. استخدم demo أو ollama.")
    return await asyncio.to_thread(_ollama_chat, messages)

async def employee_reply(system_prompt: str, history: list[dict[str, str]]) -> str:
    return await generate([{"role": "system", "content": system_prompt}, *history])
