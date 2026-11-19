from __future__ import annotations
import asyncio, json, os, urllib.error, urllib.request
from employee_data_access import datasets_for

BASE_URL = os.getenv("VINDORA_API_URL", "").strip().rstrip("/")
API_KEY = os.getenv("VINDORA_API_KEY", "").strip()
TIMEOUT = float(os.getenv("VINDORA_TIMEOUT", "12"))

class VindoraUnavailable(RuntimeError):
    pass

def _fetch_dataset(dataset: str, days: int) -> dict:
    if not BASE_URL or not API_KEY:
        raise VindoraUnavailable("اتصال Vindora غير مكتمل على السيرفر. راجع VINDORA_API_URL وVINDORA_API_KEY.")
    payload = json.dumps({"dataset": dataset, "days": days}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(BASE_URL + "/backend/office_brains.php", data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise VindoraUnavailable("Vindora returned an invalid data response.")
        return result.get("data") or {}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise VindoraUnavailable("Vindora رفض اتصال Office Brains. راجع مفتاح الربط.") from exc
        raise VindoraUnavailable(f"تعذر جلب بيانات Vindora (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VindoraUnavailable("تعذر الاتصال بخدمة بيانات Vindora.") from exc

async def employee_context(employee_id: str, days: int = 30) -> str:
    datasets = datasets_for(employee_id)
    if not datasets:
        if employee_id == "كريم":
            return "\nبيانات Vindora: لا يوجد حاليًا جدول حملات أو إنفاق إعلاني أو نتائج حملات في قاعدة البيانات؛ لذلك لا تدّعِ أنك حللت حملات فعلية أو ROAS/CPA. يمكنك تقديم اقتراحات وخطط تقديرية فقط مع توضيح أنها ليست نتائج فعلية."
        return ""
    results = await asyncio.gather(*(asyncio.to_thread(_fetch_dataset, name, days) for name in datasets))
    bundle = {name: value for name, value in zip(datasets, results)}
    return "\nملخصات حقيقية من قاعدة Vindora (بيانات مجمعة للقراءة فقط، لا تحتوي بيانات تعريف العملاء):\n" + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\nاستخدم هذه الأرقام عند الإجابة، واذكر الفترة وحدود كل مؤشر. لا تستنتج بيانات غير موجودة ولا تعتبر إجمالي الطلبات مبيعات محققة."
