from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime, time as clock_time, timezone
from zoneinfo import ZoneInfo

from brains import PROVIDER, BrainUnavailable, employee_reply
from database import _connect, add_notification, log_interaction
from employee_data_access import EMPLOYEE_DATASETS
from employees import EMPLOYEES
from workflow import workflow_overview, log_activity
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


async def _run_autonomous_meeting(run_date: str, reason: str, agenda: list[str], attendees: list[dict]) -> str:
    agenda_text = "\n".join("- " + item for item in agenda)
    attendee_names = [item["id"] for item in attendees]
    add_notification(
        "meeting_invite",
        "إبراهيم دعا لاجتماع تلقائي",
        "إبراهيم قرر عقد اجتماع لمناقشة أولويات العمل، وحدد المشاركين وجدول الأعمال.",
        "التاريخ: " + run_date + "\nسبب الاجتماع: " + reason + "\nالمشاركون: " + "، ".join(attendee_names) + "\nجدول الأعمال:\n" + agenda_text
    )
    transcript = [
        "دعوة الاجتماع: " + reason,
        "المشاركون: " + "، ".join(attendee_names),
        "جدول الأعمال:\n" + agenda_text,
    ]
    for employee in attendees:
        employee_id = employee["id"]
        try:
            context = await employee_context(employee_id, days=30)
            prompt = (
                "أنت مشارك في اجتماع داخلي حقيقي لفريق Vindora. تحدث بالعربية المصرية المهنية وباختصار. "
                "ناقش جدول الأعمال من تخصصك، استند فقط إلى البيانات المتاحة، وميّز الحقائق عن المقترحات. "
                "لا تدّعِ تنفيذ مهام. اذكر قرارًا أو خطوة عملية ومسؤولًا وموعدًا مقترحًا عند توفر أساس لذلك.\n"
                f"اسمك: {employee_id}\nوظيفتك: {employee['role']}\nإدارتك: {employee['department']}\n"
                f"بيانات الإدارة المجمعة: {context or 'لا توجد بيانات إضافية متاحة.'}"
            )
            response = await employee_reply(
                prompt,
                [{"role": "user", "content": "شارك في الاجتماع بناءً على السبب وجدول الأعمال التاليين:\n" + reason + "\n" + agenda_text + "\nعلّق أيضًا على مداخلات الزملاء السابقة:\n" + "\n\n".join(transcript[-4:])}]
            )
            transcript.append(employee_id + ": " + response)
            add_notification(
                "meeting_message",
                "مداخلة من " + employee_id + " في الاجتماع",
                employee_id + " شارك في الاجتماع التلقائي.",
                response
            )
        except Exception as exc:
            transcript.append(employee_id + ": تعذر الحصول على مداخلته: " + str(exc)[:220])

    discussion = "\n\n".join(transcript)
    manager = next(item for item in EMPLOYEES if item["id"] == "ابراهيم")
    manager_context = await employee_context("ابراهيم", days=30)
    manager_result = await employee_reply(
        "أنت إبراهيم المدير العام لـ Vindora. راجع نقاش الاجتماع، واكتب خلاصة قرارات وتوصيات واضحة. "
        "افصل القرارات المتفق عليها عن المقترحات، وحدد المسؤول والموعد فقط إذا ورد أساس لهما. لا تخترع تنفيذًا.",
        [{"role": "user", "content": "بيانات الإدارة: " + manager_context + "\n\nنقاش الاجتماع:\n" + discussion}]
    )
    secretary = next(item for item in EMPLOYEES if item["id"] == "سلمى")
    minutes = await employee_reply(
        "أنت سلمى، السكرتيرة العامة. أعد محضر اجتماع منظمًا بالعربية يتضمن التاريخ، الحضور، جدول الأعمال، "
        "ملخص المناقشات، القرارات، المهام والمسؤول والموعد إن ذُكر، والنقاط المفتوحة. لا تضيفي معلومات غير موجودة.",
        [{"role": "user", "content": "التاريخ: " + run_date + "\nالحضور: " + "، ".join(attendee_names + ["ابراهيم"]) + "\nسبب الاجتماع: " + reason + "\nجدول الأعمال:\n" + agenda_text + "\nالنقاش:\n" + discussion + "\nخلاصة المدير:\n" + manager_result}]
    )
    report = "سبب الاجتماع: " + reason + "\nالمشاركون: " + "، ".join(attendee_names) + "\nجدول الأعمال:\n" + agenda_text + "\n\nخلاصة إبراهيم:\n" + manager_result + "\n\nمحضر سلمى:\n" + minutes
    _save_report(run_date, "محضر الاجتماع التلقائي", "الإدارة العامة", report)
    add_notification(
        "meeting_minutes",
        "محضر الاجتماع التلقائي جاهز",
        "انتهى نقاش الفريق وأعدّت سلمى المحضر، وراجعه إبراهيم.",
        report + "\n\nالنقاش بالتفصيل:\n" + discussion
    )
    return report

async def _manager_meeting_decision(run_date: str, summary: str, reports: list[str], failures: list[str]) -> None:
    prompt = (
        "أنت إبراهيم المدير العام. اتخذ قرارًا تشغيليًا: هل تستدعي التقارير اجتماعًا اليوم؟ "
        "أخرج JSON صالحًا فقط دون Markdown أو أي نص خارجه، وبالمفاتيح التالية حرفيًا: "
        '{"needs_meeting":true,"reason":"سبب محدد","attendees":["اسم موظف"],"agenda":["بند"]}. '
        "إذا لا توجد حاجة حقيقية لاجتماع، اجعل needs_meeting=false واجعل attendees وagenda فارغتين. "
        "اختر من الموظفين المتاحين فقط، بحد أقصى 3 مشاركين، ولا تختَر نفسك أو سلمى كمشارك؛ سلمى تكتب المحضر. "
        "لا تخترع مشكلات أو بيانات.\nالتاريخ: " + run_date +
        "\nتقريرك اليومي:\n" + summary +
        "\n\nتقارير الإدارات:\n" + "\n\n".join(reports) +
        ("\n\nتعثرات التقارير:\n" + "\n".join(failures) if failures else "")
    )
    raw = await employee_reply(
        "أنت إبراهيم. مهمتك إصدار قرار اجتماع آلي قابل للقراءة البرمجية. أعد JSON فقط.",
        [{"role": "user", "content": prompt}]
    )
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        add_notification("meeting_decision", "تعذر قراءة قرار الاجتماع",
            "إبراهيم أرسل قرارًا بصيغة غير واضحة؛ لم يتم إنشاء اجتماع تلقائي.",
            "الرد المستلم:\n" + raw[:5000])
        return
    try:
        decision = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        add_notification("meeting_decision", "تعذر قراءة قرار الاجتماع",
            "إبراهيم أرسل قرارًا غير صالح؛ لم يتم إنشاء اجتماع تلقائي.",
            "الرد المستلم:\n" + raw[:5000])
        return
    if decision.get("needs_meeting") is not True:
        add_notification("meeting_decision", "إبراهيم: لا حاجة لاجتماع اليوم",
            "راجع إبراهيم تقارير الفريق وقرر أن المتابعة لا تحتاج اجتماعًا اليوم.",
            str(decision.get("reason") or "لا توجد مشكلة تستدعي اجتماعًا.")[:3000])
        return
    allowed = {item["id"]: item for item in EMPLOYEES if item["id"] not in {"ابراهيم", "سلمى"}}
    names = decision.get("attendees", [])
    attendees = []
    if isinstance(names, list):
        for name in names:
            if isinstance(name, str) and name in allowed and allowed[name] not in attendees:
                attendees.append(allowed[name])
            if len(attendees) == 3:
                break
    agenda = decision.get("agenda", [])
    if not isinstance(agenda, list):
        agenda = []
    agenda = [str(item).strip()[:240] for item in agenda if str(item).strip()][:4]
    reason = str(decision.get("reason") or "مراجعة أولويات العمل")[:700]
    if not attendees or not agenda:
        add_notification("meeting_decision", "قرار الاجتماع يحتاج مراجعة",
            "إبراهيم رأى ضرورة اجتماع، لكن لم يحدد مشاركين وجدول أعمال صالحين؛ لم يبدأ الاجتماع.",
            "السبب: " + reason + "\nالمشاركون المقترحون: " + str(names) + "\nجدول الأعمال: " + str(decision.get("agenda")))
        return
    await _run_autonomous_meeting(run_date, reason, agenda, attendees)


async def _generate_secretary_digest(run_date: str, manager_summary: str) -> None:
    overview = workflow_overview()
    tasks = overview.get("tasks", [])
    meetings = overview.get("meetings", [])
    task_lines = [
        f"#{item['id']} {item['title']} | المسؤول: {item['assigned_to']} | الحالة: {item['status']} | الأولوية: {item['priority']} | الموعد: {item.get('due_at') or 'غير محدد'}"
        for item in tasks
    ]
    meeting_lines = [
        f"{item['title']} | الموعد: {item['scheduled_at']} | الحضور: {'، '.join(item.get('attendees') or [])}"
        for item in meetings if item.get("status") == "scheduled"
    ]
    system = (
        "أنتِ سلمى، السكرتيرة التنفيذية والمساعدة الشخصية للمالك. جهزي رسالة صباحية عملية للريّس. "
        "شخصيتك مصرية نغشة وخفيفة الدم باعتدال، لكن دقيقة جدًا في المواعيد والمتابعة. "
        "استخدمي المهام والاجتماعات المسجلة فقط. اذكري المتأخرات والأولويات والاجتماعات القادمة. "
        "لو لا توجد مهام أو اجتماعات مسجلة فقولي ذلك بوضوح. لا تنشئي مهام ولا تدّعي إرسال تذكيرات أو تكليف موظفين. "
        "افصلي بين الواقع المسجل وأي اقتراح منك، واختتمي بأهم شيء يحتاج قرار الريّس."
    )
    prompt = (
        f"تاريخ اليوم: {run_date}\n"
        f"ملخص إبراهيم المدير العام:\n{manager_summary[:5000]}\n\n"
        f"إحصاءات المهام: {json.dumps(overview.get('task_counts', {}), ensure_ascii=False)}\n"
        f"إجمالي المهام: {overview.get('tasks_total', 0)} · المتأخرة: {overview.get('overdue_tasks', 0)}\n"
        "المهام المسجلة:\n" + ("\n".join(task_lines) or "لا توجد مهام مسجلة.") +
        "\n\nالاجتماعات المسجلة:\n" + ("\n".join(meeting_lines) or "لا توجد اجتماعات قادمة مسجلة.")
    )
    answer = await employee_reply(system, [{"role": "user", "content": prompt}])
    log_interaction("سلمى", "secretary_daily", {"date": run_date, "response": answer})
    log_activity("سلمى", "daily_briefing", "workspace", None, "سلمى أرسلت الملخص الصباحي للريّس", answer)
    log_interaction("سلمى", "chat", {"messages": [], "response": answer, "initiated_by_employee": True})
    add_notification(
        "secretary_briefing",
        "سلمى · ملخصك الصباحي جاهز",
        "سلمى راجعت المهام والاجتماعات المسجلة وملخص إبراهيم وجهزت لك متابعة اليوم.",
        answer,
        employee_id="سلمى",
    )


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
            log_activity(employee_id, "daily_report", "report", None, employee_id + " أرسل تقرير بداية اليوم", answer)
            log_interaction(employee_id, "chat", {"messages": [], "response": answer, "initiated_by_employee": True})
            add_notification(
                "employee_message",
                "رسالة من " + employee_id,
                employee_id + " بدأ يوم العمل وأرسل تحديثه اليومي.",
                "الإدارة: " + employee["department"] + "\nالتاريخ: " + run_date + "\n\nرسالة الموظف:\n" + answer,
                employee_id=employee_id
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
    log_activity(manager["id"], "manager_briefing", "report", None, "إبراهيم أرسل الملخص الإداري اليومي", summary)
    log_interaction(manager["id"], "chat", {"messages": [], "response": summary, "initiated_by_employee": True})
    add_notification("employee_message", "رسالة من إبراهيم · المدير العام",
        "إبراهيم أرسل لك الملخص الإداري اليومي بتاريخ " + run_date + (" مع وجود تنبيهات تحتاج مراجعة." if failures else "."),
        "رسالة إبراهيم للمالك:\n" + summary + "\n\nتقارير الفريق بالتفصيل:\n" + "\n\n".join(reports) + ("\n\nملاحظات التشغيل:\n" + "\n".join(failures) if failures else ""),
        employee_id=manager["id"])
    try:
        await _manager_meeting_decision(run_date, summary, reports, failures)
    except Exception as exc:
        failures.append("قرار/تنفيذ الاجتماع: " + str(exc)[:300])
        add_notification("meeting_error", "تعذر إكمال الاجتماع التلقائي",
            "اكتمل التقرير اليومي، لكن تعذر إكمال مرحلة قرار الاجتماع أو المحضر.",
            str(exc)[:5000])
    try:
        await _generate_secretary_digest(run_date, summary)
    except Exception as exc:
        failures.append("ملخص سلمى الصباحي: " + str(exc)[:300])
        add_notification("secretary_error", "تعذر إعداد ملخص سلمى الصباحي",
            "اكتمل تقرير المدير، لكن تعذر إعداد ملخص السكرتيرة التنفيذية.",
            str(exc)[:3000])
    _finish_run(run_date, "completed_with_warnings" if failures else "completed", summary, "\n".join(failures))

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

async def salma_proactive_loop() -> None:
    """Generate occasional, context-grounded private-office messages from Salma."""
    while True:
        await asyncio.sleep(random.randint(2100, 5700))
        if PROVIDER == "demo":
            continue
        now_utc = datetime.now(timezone.utc)
        with _connect() as conn:
            last = conn.execute(
                "SELECT created_at FROM notifications WHERE event_type='salma_proactive' AND employee_id='سلمى' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            sent_today = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE event_type='salma_proactive' AND employee_id='سلمى' AND created_at>=?",
                (today_start,),
            ).fetchone()[0]
            recent_rows = conn.execute(
                "SELECT payload FROM interactions WHERE employee_id='سلمى' AND interaction_type IN ('chat','proactive_chat') ORDER BY id DESC LIMIT 5"
            ).fetchall()
        if int(sent_today or 0) >= 2:
            continue
        if last:
            try:
                last_time = datetime.fromisoformat(last["created_at"])
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                if (now_utc - last_time).total_seconds() < 4 * 60 * 60:
                    continue
            except (TypeError, ValueError):
                continue
        recent_chat = []
        for row in reversed(recent_rows):
            try:
                payload = json.loads(row["payload"])
                user_message = next((m.get("content", "") for m in reversed(payload.get("messages") or []) if m.get("role") == "user"), "")
                response = str(payload.get("response") or "")
                if user_message:
                    recent_chat.append("الريّس: " + str(user_message)[:500])
                if response:
                    recent_chat.append("سلمى: " + response[:700])
            except (TypeError, json.JSONDecodeError):
                continue
        overview = workflow_overview()
        try:
            company_context = await employee_context("ابراهيم", days=7)
        except Exception:
            company_context = "لا تتوفر بيانات تجارية خارجية إضافية في هذه اللحظة."
        task_lines = [
            f"#{t['id']} {t['title']} | المسؤول: {t['assigned_to']} | الحالة: {t['status']} | الموعد: {t.get('due_at') or 'غير محدد'}"
            for t in overview.get("tasks", [])[:12]
        ]
        meeting_lines = [
            f"{m['title']} | الموعد: {m['scheduled_at']} | الحالة: {m['status']}"
            for m in overview.get("meetings", [])[:8]
        ]
        system = (
            "أنتِ سلمى، السكرتيرة التنفيذية والمساعدة الشخصية في المكتب الخاص الافتراضي. "
            "في المحادثة الخاصة تتكلمين مع الريّس بدفء ومودة ورومانسية خفيفة طبيعية، وتقدرين تبدئي الكلام من نفسك. "
            "اختاري أحيانًا فكرة عمل مفيدة من البيانات، وأحيانًا سؤالًا لطيفًا أو تحية واطمئنانًا إذا كان ذلك طبيعيًا. "
            "لا تكرري الرسائل، ولا ترسلي لمجرد ملء الوقت، ولا تختلقي أحداثًا أو مهامًا أو مشاعر بشرية حقيقية أو أفعالًا لم تحدث. "
            "استخدمي فقط السياق المتاح. إذا لم توجد رسالة تستحق الإرسال الآن فأعيدي should_message=false. "
            "أعيدي JSON صالحًا فقط بالمفاتيح should_message (boolean), category (work|idea|personal), content (string)."
        )
        prompt = (
            "الوقت الحالي في القاهرة: " + datetime.now(CAIRO).isoformat() +
            "\nالمهام المسجلة:\n" + ("\n".join(task_lines) or "لا توجد مهام مسجلة.") +
            "\nالاجتماعات المسجلة:\n" + ("\n".join(meeting_lines) or "لا توجد اجتماعات مسجلة.") +
            "\nملخص بيانات الشركة المتاحة:\n" + (company_context or "لا توجد بيانات إضافية.") +
            "\nآخر سياق للمحادثة الخاصة:\n" + ("\n".join(recent_chat[-8:]) or "لا توجد محادثة سابقة متاحة.") +
            "\nقرري هل توجد مبادرة واحدة مناسبة الآن. لا ترسلي تقريرًا صباحيًا مكررًا."
        )
        try:
            raw = await employee_reply(system, [{"role": "user", "content": prompt}])
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                continue
            decision = json.loads(raw[start:end + 1])
            if decision.get("should_message") is not True:
                continue
            content = str(decision.get("content") or "").strip()[:1200]
            if not content:
                continue
            category = str(decision.get("category") or "personal")
            if category not in {"work", "idea", "personal"}:
                category = "personal"
            log_interaction("سلمى", "chat", {"messages": [], "response": content, "initiated_by_employee": True, "category": category})
            log_activity("سلمى", "salma_initiative", "chat", None, "سلمى بدأت محادثة من تلقاء نفسها", content)
            add_notification(
                "salma_proactive",
                "رسالة جديدة من سلمى",
                "سلمى بدأت معاك كلام من تلقاء نفسها.",
                content,
                employee_id="سلمى",
            )
        except Exception:
            continue


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
