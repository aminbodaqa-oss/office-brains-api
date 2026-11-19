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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "90"))

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

def _gemini_chat(messages: list[dict[str, str]]) -> str:
    if not GEMINI_API_KEY:
        raise BrainUnavailable("مفتاح Gemini غير مضبوط على السيرفر. أضف GEMINI_API_KEY في متغيرات البيئة.")
    system_instruction = None
    contents = []
    for item in messages:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role == "system":
            system_instruction = (system_instruction + "\n" if system_instruction else "") + content
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}]
        })
    if not contents:
        raise BrainUnavailable("لا توجد رسالة صالحة لإرسالها إلى Gemini.")
    payload = {"contents": contents}
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
        candidates = result.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or []
        answer = "".join(part.get("text", "") for part in parts).strip()
        if not answer:
            raise BrainUnavailable("Gemini لم يُرجع نصًا. قد يكون الرد محجوبًا أو لا يحتوي على محتوى نصي.")
        return answer
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            error_data = json.loads(exc.read().decode("utf-8"))
            detail = error_data.get("error", {}).get("message", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        if exc.code == 429:
            message = "تم الوصول إلى حد طلبات Gemini المجاني أو معدل الاستخدام. انتظر قليلًا ثم حاول مجددًا."
        elif exc.code in (401, 403):
            message = "Gemini رفض مفتاح API أو صلاحياته. راجع المفتاح وإعدادات Gemini API."
        elif exc.code == 404:
            message = "نموذج Gemini المحدد غير متاح لهذا المفتاح. راجع GEMINI_MODEL."
        else:
            message = f"فشل طلب Gemini (HTTP {exc.code})."
        if detail:
            message += " التفاصيل: " + detail[:400]
        raise BrainUnavailable(message) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BrainUnavailable("تعذر الاتصال بـ Gemini API. تحقق من اتصال السيرفر وإعدادات الخدمة.") from exc

def _demo_message() -> str:
    return "الـAPI شغال، لكن عقل الذكاء الاصطناعي المحلي لسه مش متوصل. دي نسخة تجهيز واختبار اتصال، ومش هقدّم ردود تمثيلية على إنها تفكير حقيقي. بعد تشغيل نموذج محلي متوافق مع Ollama، غيّر BRAIN_PROVIDER إلى ollama واضبط عنوانه واسم النموذج."

async def generate(messages: list[dict[str, str]]) -> str:
    if PROVIDER == "demo":
        return _demo_message()
    if PROVIDER == "ollama":
        return await asyncio.to_thread(_ollama_chat, messages)
    if PROVIDER == "gemini":
        return await asyncio.to_thread(_gemini_chat, messages)
    raise BrainUnavailable("قيمة BRAIN_PROVIDER غير مدعومة. استخدم demo أو ollama أو gemini.")

async def employee_reply(system_prompt: str, history: list[dict[str, str]]) -> str:
    return await generate([{"role": "system", "content": system_prompt}, *history])
