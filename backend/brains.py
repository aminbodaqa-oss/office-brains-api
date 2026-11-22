from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

from platform_ai import get_runtime_ai_config


class BrainUnavailable(RuntimeError):
    pass


def get_provider() -> str:
    try:
        return str(get_runtime_ai_config().get("provider", "demo")).strip().lower()
    except RuntimeError as exc:
        raise BrainUnavailable(str(exc)) from exc


def _ollama_chat(messages: list[dict[str, str]], config: dict) -> str:
    base_url = str(config.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
    model = str(config.get("model") or "qwen2.5:3b")
    timeout = int(config.get("timeout_seconds") or 90)
    body = json.dumps({"model": model, "messages": messages, "stream": False}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base_url + "/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = result.get("message", {}).get("content", "").strip()
        if not answer:
            raise BrainUnavailable("نموذج Ollama لم يُرجع محتوى نصيًا.")
        return answer
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BrainUnavailable("تعذر الاتصال بمحرك Ollama. راجع عنوان الخدمة وحالة النموذج.") from exc


def _gemini_chat(messages: list[dict[str, str]], config: dict) -> str:
    api_key = str(config.get("api_key") or "").strip()
    model = str(config.get("model") or "gemini-3.8-flash").strip()
    timeout = int(config.get("timeout_seconds") or 90)
    if not api_key:
        raise BrainUnavailable("مفتاح Gemini غير مضبوط. أضفه من إعدادات الذكاء الاصطناعي أو متغيرات السيرفر.")
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
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
            message = "تم الوصول إلى حد طلبات Gemini أو معدل الاستخدام. انتظر قليلًا ثم حاول مجددًا."
        elif exc.code in (401, 403):
            message = "Gemini رفض مفتاح API أو صلاحياته. راجع المفتاح وإعدادات Gemini API."
        elif exc.code == 404:
            message = "نموذج Gemini المحدد غير متاح لهذا المفتاح. راجع اسم النموذج."
        else:
            message = f"فشل طلب Gemini (HTTP {exc.code})."
        if detail:
            message += " التفاصيل: " + detail[:400]
        raise BrainUnavailable(message) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BrainUnavailable("تعذر الاتصال بـ Gemini API. تحقق من اتصال السيرفر وإعدادات الخدمة.") from exc


def _demo_message() -> str:
    return "محرك الذكاء الاصطناعي مضبوط على وضع التجربة. اختر مزودًا فعليًا من إعدادات المنصة لتفعيل الردود الذكية."


async def _generate_with_config(messages: list[dict[str, str]], config: dict) -> str:
    provider = str(config.get("provider", "demo")).strip().lower()
    if provider == "demo":
        return _demo_message()
    if provider == "ollama":
        return await asyncio.to_thread(_ollama_chat, messages, config)
    if provider == "gemini":
        return await asyncio.to_thread(_gemini_chat, messages, config)
    raise BrainUnavailable("مزود الذكاء الاصطناعي غير مدعوم. استخدم demo أو ollama أو gemini.")


async def generate(messages: list[dict[str, str]]) -> str:
    try:
        config = get_runtime_ai_config()
    except RuntimeError as exc:
        raise BrainUnavailable(str(exc)) from exc
    try:
        return await _generate_with_config(messages, config)
    except BrainUnavailable as primary_error:
        fallback_provider = str(config.get("fallback_provider", "demo")).strip().lower()
        if fallback_provider == "demo" or fallback_provider == str(config.get("provider", "demo")).strip().lower():
            raise
        fallback_config = {
            "provider": fallback_provider,
            "model": str(config.get("fallback_model") or ""),
            "base_url": str(config.get("fallback_base_url") or config.get("base_url") or ""),
            "timeout_seconds": int(config.get("timeout_seconds") or 90),
            "api_key": str(config.get("api_key") or ""),
        }
        try:
            return await _generate_with_config(messages, fallback_config)
        except BrainUnavailable as fallback_error:
            raise BrainUnavailable(
                "تعذر الرد من المزود الأساسي والاحتياطي. الأساسي: "
                + str(primary_error)[:220] + " | الاحتياطي: " + str(fallback_error)[:220]
            ) from fallback_error


async def employee_reply(system_prompt: str, history: list[dict[str, str]]) -> str:
    return await generate([{"role": "system", "content": system_prompt}, *history])
