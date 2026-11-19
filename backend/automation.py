from __future__ import annotations

import asyncio
import os
from datetime import datetime, time as clock_time
from zoneinfo import ZoneInfo

from brains import PROVIDER, BrainUnavailable, employee_reply
from database import _connect, add_notification
from employee_data_access import EMPLOYEE_DATASETS
from employees import EMPLOYEES
from vindora_client import VindoraUnavailable, employee_context

CAIRO = ZoneInfo("Africa/Cairo")
START_TIME = clock_time(9, 0)
WORK_DAYS = {6, 0, 1, 2, 3}
REPORT_EMPLOYEES = [e for e in EMPLOYEES if e["id"] != "ابراهيم" and EMPLOYEE_DATASETS.get(e["id"])]

def _enabled() -> bool:
    return os.getenv("AUTONOMOUS_OFFICE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

def _claim_run(run_date: str) -> bool:
    now_dt = datetime.now(CAIRO)
    now = now_dt.isoformat()
    with _connect() as conn:
        row = conn.execute("SELECT status,started_at FROM autonomous_runs WHERE run_date=?", (run_date,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO autonomous_runs(run_date,status,started_at) VALUES(?,?,?)", (run_date, "running", now))
            return True
        if row["status"] == "completed" or row["status"] == "completed_with_warnings":
            return False
        try:
            started = datetime.fromisoformat(row["started_at"])
            stale = (now_dt - started).total_seconds() > 1800
        except (TypeError, ValueError):
            stale = True
        if row["status"] == "failed" or (row["status"] == "running" and stale):
            conn.execute("UPDATE autonomous_runs SET status='running',started_at=?,finished_at=NULL,error='' WHERE run_date=?", (now, run_date))
            return True
        return False

def _save_report(run_date: str, employee_id: str, department: str, content: str) -> None:
    now = datetime.now(CAIRO).isoformat()
    with _connect() as conn:
        conn.execute("""INSERT INTO autonomous_reports(run_date,employee_id,department,content,created_at)
            VALUES(?,?,?,?,?) ON CONFLICT(run_date,employee_id) DO UPDATE SET
            department=excluded.department,content=excluded.content,created_at=excluded.created_at""",
            (run_date, employee_id, department, content, now))

def _finish_run(run_date: str, status: str, summary: str = "", error: str = "") -> None:
    with _connect() as conn:
        conn.execute("UPDATE autonomous_runs SET status=?,finished_at=?,summary=?,error=? WHERE run_date=?",
            (status, datetime.now(CAIRO).isoformat(), summary, error[:1000], run_date))

async def _generate_daily_briefing(run_date: str) -> None:
    reports = []
    failures = []
    for employee in REPORT_EMPLOYEES:
        employee_id = employee["id"]
        try:
            context = await employee_context(employee_id, days=30)
            prompt = (
                "أنت تبدأ يوم العمل من تلقاء نفسك بصفتك موظفًا داخل Vindora. "
                "اكتب تقرير بداية اليوم بالعربية المصرية المهنية، موجزًا وعمليًا. "
                "استخدم فقط البيانات المجمعة المرفقة للفترة المتاحة. "
                "اذكر بوضوح إذا لم توجد بيانات كافية، ولا تخترع أرقامًا أو مهامًا منفذة. "
                "حدد 1-3 أولويات مقترحة لهذا اليوم، وأي مشكلة تحتاج تدخل المدير. "
                "هذا تقرير تخطيطي وليس تنفيذًا فعليًا لأي إجراء.\n"
                f"التاريخ: {run_date}\nاسم الموظف: {employee_id}\n"
                f"الوظيفة: {employee['role']}\nالإدارة: {employee['department']}\n"
                f"سياق البيانات: {context or 'لا توجد مجموعات بيانات متاحة لهذا الموظف.'}"
            )
            answer = await employee_reply(prompt, [{"role": "user", "content": "ابدأ تقريرك اليومي الآن."}])
            _save_report(run_date, employee_id, employee["department"], answer)
            add_notification(
                "employee_message",
                "رسالة من " + employee_id,
                employee_id + " بدأ يوم العمل وأرسل تحديثه اليومي.",
                "الإدارة: " + employee["department"] + "\nالتاريخ: " + run_date + "\n\nرسالة الموظف:\n" + answer
            )
            reports.append(f"تقرير {employee_id} ({employee['department']}):\n{answer}")
        except Exception as exc:
            message = f"{employee_id}: تعذر إعداد التقرير ({str(exc)[:240]})"
            failures.append(message)
            _save_report(run_date, employee_id, employee["department"], message)

    manager = next(e for e in EMPLOYEES if e["id"] == "ابراهيم")
    manager_context = ""
    try:
        manager_context = await employee_context("ابراهيم", days=30)
    except Exception as exc:
        failures.append("بيانات المدير: " + str(exc)[:240])

    manager_prompt = (
        "أنت إبراهيم، المدير العام لـ Vindora. استلمت تقارير بداية اليوم من الإدارات. "
        "أعد تقريرًا إداريًا واضحًا للمالك، يتضمن ملخص الحالة، الأولويات، المشكلات التي تستحق التصعيد، "
        "توزيع المتابعة المقترح، وهل ترى حاجة لاجتماع اليوم مع السبب والموظفين المقترحين. "
        "لا تدّعِ أن اجتماعًا انعقد أو أن مهمة نُفذت. ميّز الحقائق عن الاقتراحات ولا تخترع أرقامًا.\n"
        f"التاريخ: {run_date}\nبيانات Vindora المجمعة: {manager_context}\n\n"
        + "\n\n".join(reports)
        + ("\n\nتعذر إعداد بعض التقارير:\n" + "\n".join(failures) if failures else "")
    )
    summary = await employee_reply(
        "أنت المدير العام إبراهيم. كن دقيقًا، لا تخترع بيانات، واكتب تقريرًا تنفيذيًا موجزًا للمالك.",
        [{"role": "user", "content": manager_prompt}],
    )
    _save_report(run_date, manager["id"], manager["department"], summary)
    _finish_run(run_date, "completed_with_warnings" if failures else "completed", summary, "\n".join(failures))
    add_notification("employee_message", "رسالة من إبراهيم · المدير العام",
        "إبراهيم أرسل لك الملخص الإداري اليومي بتاريخ " + run_date + (" مع وجود تنبيهات تحتاج مراجعة." if failures else "."),
        "رسالة إبراهيم للمالك:\n" + summary + "\n\nتقارير الفريق بالتفصيل:\n" + "\n\n".join(reports) + ("\n\nملاحظات التشغيل:\n" + "\n".join(failures) if failures else ""))

async def scheduler_loop() -> None:
    while True:
        now = datetime.now(CAIRO)
        if now.weekday() in WORK_DAYS and now.time().replace(tzinfo=None) >= START_TIME:
            run_date = now.date().isoformat()
            if PROVIDER != "demo" and _claim_run(run_date):
                add_notification("automation", "بدأ التشغيل التلقائي",
                    "بدأ إعداد تقارير الفريق اليومية.", "التاريخ: " + run_date + "\nموعد التشغيل: 09:00 بتوقيت القاهرة.")
                try:
                    await _generate_daily_briefing(run_date)
                except Exception as exc:
                    _finish_run(run_date, "failed", error=str(exc))
                    add_notification("error", "تعذر إكمال التشغيل التلقائي",
                        "حدث خطأ أثناء إعداد التقارير اليومية.", str(exc))
        await asyncio.sleep(30)

def automation_status() -> dict:
    today = datetime.now(CAIRO).date().isoformat()
    with _connect() as conn:
        row = conn.execute("SELECT run_date,status,started_at,finished_at,error FROM autonomous_runs WHERE run_date=?", (today,)).fetchone()
    return {
        "enabled": _enabled(),
        "provider_ready": PROVIDER != "demo",
        "timezone": "Africa/Cairo",
        "work_days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
        "start_time": "09:00",
        "today": dict(row) if row else None,
    }

def recent_reports(limit: int = 30) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT run_date,employee_id,department,content,created_at FROM autonomous_reports ORDER BY run_date DESC,id DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    return [dict(row) for row in rows]
