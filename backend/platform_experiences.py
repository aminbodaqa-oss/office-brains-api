from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from database import _connect

SURFACES = {"platform_site", "office_login", "office_workspace", "super_admin", "customer_workspace"}
TEXT_LIMITS = {
    "site_name": 100, "page_title": 160, "meta_description": 320,
    "headline": 180, "headline_emphasis": 180, "subtitle": 900,
    "primary_cta_text": 80, "primary_cta_url": 300,
    "footer_text": 240, "welcome_title": 180, "welcome_message": 600,
    "login_title": 160, "login_message": 600, "sidebar_title": 100,
}
COLOR_KEYS = {"primary", "accent", "highlight", "background", "surface", "text"}
DEFAULT_CONFIG: dict[str, Any] = {
    "site_name": "Office Brains",
    "page_title": "Office Brains | مساحة العمل الذكية",
    "meta_description": "",
    "headline": "",
    "headline_emphasis": "",
    "subtitle": "",
    "primary_cta_text": "",
    "primary_cta_url": "",
    "footer_text": "",
    "welcome_title": "",
    "welcome_message": "",
    "login_title": "",
    "login_message": "",
    "sidebar_title": "",
    "theme": {
        "primary": "#172A3A", "accent": "#00A884", "highlight": "#F2B84B",
        "background": "#0B1020", "surface": "#131B31", "text": "#F6F7FF",
    },
    "font_family": "system",
    "density": "comfortable",
    "corner_style": "rounded",
    "navigation": [],
    "pages": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_platform_experiences_db() -> None:
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
            entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_experiences (
            surface TEXT NOT NULL,
            workspace_id TEXT NOT NULL DEFAULT '',
            draft_json TEXT NOT NULL,
            published_json TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'draft',
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            published_at TEXT,
            PRIMARY KEY(surface, workspace_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS platform_experience_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surface TEXT NOT NULL,
            workspace_id TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL,
            config_json TEXT NOT NULL,
            published_by TEXT NOT NULL,
            published_at TEXT NOT NULL,
            UNIQUE(surface, workspace_id, version)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experience_revisions ON platform_experience_revisions(surface,workspace_id,version DESC)")


def _scope(surface: str, workspace_id: str | None) -> tuple[str, str]:
    surface = str(surface or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if surface not in SURFACES:
        raise ValueError("نطاق Website Studio غير معروف.")
    if surface == "customer_workspace" and not workspace_id:
        raise ValueError("اختار مساحة عمل العميل أولًا.")
    if surface != "customer_workspace" and workspace_id:
        raise ValueError("معرّف مساحة العمل مسموح به لنطاق مكاتب العملاء فقط.")
    if len(workspace_id) > 80:
        raise ValueError("معرّف مساحة العمل غير صالح.")
    return surface, workspace_id


def _clean_config(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or len(raw) > 24:
        raise ValueError("إعدادات التجربة غير صالحة.")
    unknown = set(raw) - (set(TEXT_LIMITS) | {"theme", "font_family", "density", "corner_style", "navigation", "pages"})
    if unknown:
        raise ValueError("يوجد حقل غير مدعوم في إعدادات الواجهة.")
    cleaned = dict(DEFAULT_CONFIG)
    for key, limit in TEXT_LIMITS.items():
        if key in raw:
            value = str(raw[key]).strip()
            if len(value) > limit:
                raise ValueError("قيمة أطول من الحد المسموح: " + key)
            cleaned[key] = value
    theme = raw.get("theme", {})
    if not isinstance(theme, dict) or set(theme) - COLOR_KEYS:
        raise ValueError("إعدادات الألوان غير صالحة.")
    for key, value in theme.items():
        value = str(value).strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("كل لون يجب أن يكون بصيغة HEX صحيحة.")
        cleaned["theme"][key] = value.upper()
    enums = {
        "font_family": {"system", "tajawal", "inter", "cairo"},
        "density": {"compact", "comfortable", "spacious"},
        "corner_style": {"sharp", "rounded", "soft"},
    }
    for key, choices in enums.items():
        value = str(raw.get(key, cleaned[key])).strip()
        if value not in choices:
            raise ValueError("اختيار غير مدعوم في " + key)
        cleaned[key] = value
    navigation = raw.get("navigation", [])
    if not isinstance(navigation, list) or len(navigation) > 12:
        raise ValueError("القائمة الرئيسية تقبل حتى 12 رابطًا.")
    safe_navigation = []
    for item in navigation:
        if not isinstance(item, dict) or set(item) - {"label", "url"}:
            raise ValueError("عنصر قائمة غير صالح.")
        label, url = str(item.get("label", "")).strip(), str(item.get("url", "")).strip()
        if not label or len(label) > 60 or not url or len(url) > 300:
            raise ValueError("اسم ورابط كل عنصر قائمة مطلوبان.")
        if not (url.startswith("/") or url.startswith("./") or url.startswith("https://")) or url.startswith("//") or ".." in url:
            raise ValueError("روابط القوائم يجب أن تكون داخلية أو HTTPS.")
        safe_navigation.append({"label": label, "url": url})
    cleaned["navigation"] = safe_navigation
    pages = raw.get("pages", {})
    if not isinstance(pages, dict) or len(pages) > 20:
        raise ValueError("إعدادات الصفحات غير صالحة.")
    safe_pages = {}
    for page_id, page in pages.items():
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", str(page_id)) or not isinstance(page, dict) or set(page) - {"title", "description", "visible"}:
            raise ValueError("تعريف صفحة غير صالح.")
        title, description = str(page.get("title", "")).strip(), str(page.get("description", "")).strip()
        if len(title) > 180 or len(description) > 1200:
            raise ValueError("محتوى الصفحة يتجاوز الحد المسموح.")
        safe_pages[str(page_id)] = {"title": title, "description": description, "visible": bool(page.get("visible", True))}
    cleaned["pages"] = safe_pages
    return cleaned


def get_experience(surface: str, workspace_id: str | None = None) -> dict[str, Any]:
    surface, workspace_id = _scope(surface, workspace_id)
    with _connect() as conn:
        row = conn.execute("SELECT * FROM platform_experiences WHERE surface=? AND workspace_id=?",
                           (surface, workspace_id)).fetchone()
    if not row:
        return {"surface": surface, "workspace_id": workspace_id or None,
                "draft": dict(DEFAULT_CONFIG), "published": None, "version": 0, "status": "default"}
    return {"surface": surface, "workspace_id": workspace_id or None,
            "draft": json.loads(row["draft_json"]),
            "published": json.loads(row["published_json"]) if row["published_json"] else None,
            "version": int(row["version"]), "status": row["status"],
            "updated_by": row["updated_by"], "updated_at": row["updated_at"],
            "published_at": row["published_at"]}


def save_experience_draft(surface: str, workspace_id: str | None, config: dict[str, Any], actor: str) -> dict[str, Any]:
    surface, workspace_id = _scope(surface, workspace_id)
    cleaned = _clean_config(config)
    now = _now()
    encoded = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
    with _connect() as conn:
        conn.execute("""INSERT INTO platform_experiences
            (surface,workspace_id,draft_json,published_json,version,status,updated_by,updated_at,published_at)
            VALUES(?,?,?,NULL,0,'draft',?,?,NULL)
            ON CONFLICT(surface,workspace_id) DO UPDATE SET
            draft_json=excluded.draft_json,status='draft',updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (surface, workspace_id, encoded, actor, now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""", (actor, "experience_draft_saved", "experience", surface + ":" + workspace_id, now))
    return get_experience(surface, workspace_id)


def publish_experience(surface: str, workspace_id: str | None, actor: str) -> dict[str, Any]:
    surface, workspace_id = _scope(surface, workspace_id)
    now = _now()
    with _connect() as conn:
        row = conn.execute("SELECT draft_json,version FROM platform_experiences WHERE surface=? AND workspace_id=?",
                           (surface, workspace_id)).fetchone()
        if not row:
            raise ValueError("احفظ مسودة قبل النشر.")
        config = _clean_config(json.loads(row["draft_json"]))
        version = int(row["version"]) + 1
        encoded = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        conn.execute("""UPDATE platform_experiences SET published_json=?,version=?,status='published',
            updated_by=?,updated_at=?,published_at=? WHERE surface=? AND workspace_id=?""",
            (encoded, version, actor, now, now, surface, workspace_id))
        conn.execute("""INSERT INTO platform_experience_revisions
            (surface,workspace_id,version,config_json,published_by,published_at)
            VALUES(?,?,?,?,?,?)""", (surface, workspace_id, version, encoded, actor, now))
        conn.execute("""INSERT INTO platform_audit_log(actor,action,entity_type,entity_id,created_at)
            VALUES(?,?,?,?,?)""", (actor, "experience_published", "experience", surface + ":" + workspace_id, now))
    return get_experience(surface, workspace_id)


def list_experience_revisions(surface: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
    surface, workspace_id = _scope(surface, workspace_id)
    with _connect() as conn:
        rows = conn.execute("""SELECT version,published_by,published_at FROM platform_experience_revisions
            WHERE surface=? AND workspace_id=? ORDER BY version DESC LIMIT 30""",
            (surface, workspace_id)).fetchall()
    return [dict(row) for row in rows]


def restore_experience_revision(surface: str, workspace_id: str | None, version: int, actor: str) -> dict[str, Any]:
    surface, workspace_id = _scope(surface, workspace_id)
    with _connect() as conn:
        row = conn.execute("""SELECT config_json FROM platform_experience_revisions
            WHERE surface=? AND workspace_id=? AND version=?""",
            (surface, workspace_id, int(version))).fetchone()
    if not row:
        raise ValueError("الإصدار المطلوب غير موجود.")
    return save_experience_draft(surface, workspace_id, json.loads(row["config_json"]), actor)
