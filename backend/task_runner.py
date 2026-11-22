from __future__ import annotations

import asyncio
import json

from brains import get_provider, employee_reply
from database import add_notification, log_interaction
from internal_messaging import send_internal_message
from employees import EMPLOYEES, management_context_for
from workflow import (claim_next_task_execution, fail_task_execution, finish_task_execution,
                      save_delegation_plan, update_delegation_diagnostic,
                      delegation_children, save_delegation_report_once,
                      pending_delegation_groups)



_delegation_report_failures: set[int] = set()


async def finalize_delegation_group(parent_task_id: int) -> bool:
    if parent_task_id in _delegation_report_failures:
        return False
    children = delegation_children(parent_task_id)
    if not children or not all(item.get("execution_status") in {"review", "completed"} for item in children):
        return False
    team_report_prompt = (
        f"المهمة الرئيسية: #{parent_task_id}\n"
        "اجمع النتائج المسجلة التالية في تقرير تنفيذي موحد. لا تضف حقائق غير موجودة، "
        "واشرح أي تعارض أو نقص، وافصل بين النتائج المؤكدة والتوصيات.\n\n"
        + json.dumps(children, ensure_ascii=False)
    )
    try:
        team_report = (await employee_reply(
            "أنت إبراهيم المدير العام في مكتب مساحة العمل. أعدد تقريرًا موحدًا من نتائج فريقك المسجلة فقط. "
            "لا تدّعِ تنفيذ شيء لم يرد في النتائج. اكتب بالعربية المصرية المهنية مع ملخص، نتائج كل موظف، "
            "النواقص والمخاطر، والخطوات التالية المقترحة.",
            [{"role": "user", "content": team_report_prompt}]
        )).strip()
        if not team_report:
            raise RuntimeError("لم يُرجع المحرك تقريرًا موحدًا.")
        if save_delegation_report_once(parent_task_id, team_report):
            log_interaction("ابراهيم", "delegation_team_report", {
                "parent_task_id": parent_task_id, "report": team_report,
                "child_task_ids": [item["id"] for item in children]
            })
            add_notification(
                "delegation_team_report_ready",
                f"إبراهيم جمع التقرير النهائي للمهمة الرئيسية #{parent_task_id}",
                "اكتملت نتائج المهام الفرعية وتم تجميعها في تقرير واحد.",
                team_report
            )
        return True
    except Exception as exc:
        _delegation_report_failures.add(parent_task_id)
        add_notification(
            "delegation_team_report_failed",
            f"اكتملت المهام الفرعية لكن تعذر تجميع التقرير · #{parent_task_id}",
            "النتائج الفردية محفوظة ووصلت لإبراهيم، لكن تجميع التقرير النهائي تعثر.",
            str(exc)[:1200]
        )
        return False


async def task_execution_loop() -> None:
    """Process queued AI-capable office tasks and leave every deliverable for owner review."""
    while True:
        if get_provider() == "demo":
            await asyncio.sleep(15)
            continue

        try:
            task = claim_next_task_execution()
        except Exception:
            await asyncio.sleep(10)
            continue
        if not task:
            for parent_id in pending_delegation_groups(limit=5):
                await finalize_delegation_group(parent_id)
            await asyncio.sleep(5)
            continue

        task_id = int(task["id"])
        employee_id = str(task["assigned_to"])
        employee = next((item for item in EMPLOYEES if item["id"] == employee_id), None)
        if not employee:
            fail_task_execution(task_id, "تعذر العثور على ملف الموظف المسؤول.", "النظام")
            add_notification(
                "task_execution_failed",
                f"تعذر تنفيذ المهمة #{task_id}",
                f"لم يتم العثور على ملف الموظف {employee_id}.",
                "المهمة عادت إلى قائمة المهام المفتوحة.",
            )
            continue

        try:
            context = "لا توجد بيانات إضافية متصلة بمساحة العمل حاليًا. اعتمد على تفاصيل المهمة والسجلات المصرح بها فقط."

            system = (
                "أنت موظف متخصص داخل مكتب مساحة العمل، ومطلوب منك إعداد مخرج عملي للمهمة المسندة إليك. "
                "حلل المطلوب وفق اختصاصك، وقدّم نتيجة منظمة قابلة للمراجعة، مع توضيح الافتراضات والنواقص والخطوات التالية. "
                "لا تدّعِ إرسال رسائل أو إجراء مكالمات أو تعديل أنظمة أو تنفيذ عمليات خارجية أو الوصول إلى بيانات لم تُتح لك. "
                "إذا كان المطلوب يتضمن إجراءً خارج قدراتك أو يحتاج موافقة المالك، فاذكر بوضوح أنه لم يُنفذ وما المطلوب لإتمامه. "
                "لا تعتبر كتابة خطة أو مسودة دليلاً على إنجاز إجراء خارجي. لا تختلق أرقامًا أو حقائق. "
                "اكتب بالعربية الواضحة وبأسلوب عملي موجز.\n\n"
                f"اسم الموظف: {employee_id}\nالوظيفة: {employee['role']}\nالإدارة: {employee['department']}\n"
                + management_context_for(employee_id)
            )
            prompt = (
                f"المهمة رقم: #{task_id}\nالعنوان: {task['title']}\n"
                f"التفاصيل: {task.get('description') or 'لم يذكر المالك تفاصيل إضافية.'}\n"
                f"الأولوية: {task['priority']}\nالموعد النهائي: {task.get('due_at') or 'غير محدد'}\n"
                f"سياق العمل المتاح: {context or 'لا يوجد سياق إضافي.'}\n\n"
                "نفّذ ما يمكن إنجازه داخل قدراتك الحالية، ثم سلّم تقريرًا يتضمن: "
                "1) ما تم إعداده فعليًا، 2) المخرج أو المسودة، 3) ما لم يتم تنفيذه وسببه، "
                "4) ما يحتاج موافقة أو مدخلات من المالك."
            )
            result = (await employee_reply(system, [{"role": "user", "content": prompt}])).strip()
            if not result:
                raise RuntimeError("محرك الذكاء الاصطناعي لم يُرجع نتيجة للمهمة.")

            saved = finish_task_execution(task_id, result, employee_id)
            if not saved:
                continue
            log_interaction(employee_id, "task_execution", {
                "task_id": task_id,
                "title": task["title"],
                "result": result,
                "submitted_for_review": True,
            })
            parent_task_id = task.get("parent_task_id")
            if parent_task_id:
                parent_task_id = int(parent_task_id)
                parent = next((item for item in EMPLOYEES if item["id"] == "ابراهيم"), None)
                try:
                    send_internal_message(
                        employee_id, "ابراهيم",
                        f"تم تجهيز نتيجة المهمة الفرعية #{task_id} وإرسالها للمدير العام.\n"
                        f"المهمة: {task['title']}\nالنتيجة المسجلة للمراجعة:\n{result[:4500]}"
                    )
                except Exception as exc:
                    add_notification(
                        "delegation_result_message_failed", f"تعذر إرسال نتيجة المهمة #{task_id} لإبراهيم",
                        f"النتيجة محفوظة في النظام لكن تعذر إرسال رسالة داخلية من {employee_id}.",
                        str(exc)[:1000], employee_id="ابراهيم"
                    )
                await finalize_delegation_group(parent_task_id)

            if employee_id == "ابراهيم" and task.get("source") != "delegation":
                update_delegation_diagnostic(task_id, "generating")
                try:
                    team = [
                        {"id": item["id"], "role": item.get("role", ""), "department": item.get("department", "")}
                        for item in EMPLOYEES if item["id"] != "ابراهيم"
                    ]
                    delegation_system = (
                        "أنت إبراهيم المدير العام في مكتب مساحة العمل. حوّل توصيات المهمة الرئيسية إلى خطة مهام فرعية عملية. "
                        "لا تنفذ أي إجراء ولا تدّعِ أنك أرسلت التكليفات. أخرج JSON فقط بالشكل "
                        '{"delegations":[{"title":"...","description":"...","assigned_to":"اسم الموظف حرفيًا من القائمة","priority":"normal"}]}. '
                        "اختر من 1 إلى 5 مهام فقط، ولا تكرر التوصيات، ولا تسند عملًا خارج اختصاص الموظف. "
                        'إذا لم توجد مهام قابلة للتفويض فأخرج {"delegations":[]}.'
                    )
                    delegation_prompt = (
                        "التقرير المنجز:\n" + result[:14000] + "\n\n"
                        "قائمة الفريق المسموح بالتكليف إليه:\n" +
                        json.dumps(team, ensure_ascii=False) +
                        "\n\nاقترح المهام الفرعية. استخدم assigned_to من id فقط، والأولوية واحدة من low/normal/high/urgent."
                    )
                    allowed = {item["id"] for item in team}
                    clean_plan = []
                    last_error = ""
                    for attempt in range(2):
                        try:
                            retry_prompt = delegation_prompt if attempt == 0 else (
                                "أعد إخراج خطة التفويض كـ JSON صحيح فقط، دون Markdown أو شرح. "
                                "استخدم أسماء الموظفين حرفيًا من القائمة، ومهمة واحدة إلى خمس مهام عند وجود توصيات قابلة للتنفيذ.\n"
                                + delegation_prompt
                            )
                            raw_plan = (await employee_reply(
                                delegation_system, [{"role": "user", "content": retry_prompt}]
                            )).strip()
                            start, end = raw_plan.find("{"), raw_plan.rfind("}")
                            parsed = json.loads(raw_plan[start:end + 1]) if start >= 0 and end > start else {}
                            proposals = parsed.get("delegations", [])
                            candidate = []
                            if isinstance(proposals, list):
                                for item in proposals[:5]:
                                    if not isinstance(item, dict):
                                        continue
                                    assignee = str(item.get("assigned_to", "")).strip()
                                    title = str(item.get("title", "")).strip()
                                    description = str(item.get("description", "")).strip()
                                    priority = str(item.get("priority", "normal")).strip()
                                    if assignee in allowed and title and priority in {"low", "normal", "high", "urgent"}:
                                        candidate.append({"title": title[:180], "description": description[:5000],
                                                          "assigned_to": assignee, "priority": priority})
                            if candidate:
                                clean_plan = candidate
                                break
                            last_error = "لم يُرجع المحرك مهامًا صالحة قابلة للتفويض."
                        except Exception as exc:
                            last_error = str(exc)[:900] or "تعذر تحليل خطة التفويض."
                    if clean_plan and save_delegation_plan(task_id, clean_plan):
                        add_notification(
                            "delegation_plan_ready",
                            f"خطة توزيع إبراهيم جاهزة للموافقة · #{task_id}",
                            f"إبراهيم اقترح {len(clean_plan)} مهام فرعية. لم تُرسل التكليفات بعد.",
                            "راجع المقترحات ثم اعتمد توزيعها من لوحة مهام الشركة."
                        )
                    else:
                        detail = last_error or "تعذر حفظ خطة التفويض."
                        update_delegation_diagnostic(task_id, "failed", detail)
                        log_interaction("ابراهيم", "delegation_plan_failed", {
                            "task_id": task_id, "error": detail, "report": result[:4000]
                        })
                        add_notification(
                            "delegation_plan_failed",
                            f"تعذر تجهيز خطة التفويض · #{task_id}",
                            "تم حفظ تقرير إبراهيم، لكن لم تتولد قائمة مهام فرعية صالحة. لم يتم إرسال أي تكليف.",
                            detail
                        )
                except Exception as exc:
                    detail = str(exc)[:900] or "خطأ غير معروف في مرحلة التفويض."
                    update_delegation_diagnostic(task_id, "failed", detail)
                    log_interaction("ابراهيم", "delegation_plan_failed", {
                        "task_id": task_id, "error": detail
                    })
                    add_notification(
                        "delegation_plan_failed",
                        f"تعذر تجهيز خطة التفويض · #{task_id}",
                        "تم حفظ تقرير إبراهيم، لكن مرحلة تحويل التوصيات إلى تكليفات تعثرت. لم يتم إرسال أي تكليف.",
                        detail
                    )

            add_notification(
                "task_ready_for_review",
                f"نتيجة مهمة جاهزة للمراجعة · #{task_id}",
                f"{employee_id} جهّز نتيجة للمهمة: {task['title']}",
                "المهمة لم تُغلق تلقائيًا. راجع النتيجة وسجّل اعتمادك من لوحة المكتب.\n\n" + result,
                employee_id=employee_id,
            )
        except Exception as exc:
            message = str(exc)[:1200] or "حدث خطأ غير معروف أثناء تنفيذ المهمة."
            fail_task_execution(task_id, message, employee_id)
            add_notification(
                "task_execution_failed",
                f"تعذر إكمال تجهيز المهمة · #{task_id}",
                f"{employee_id} لم يتمكن من تجهيز نتيجة للمهمة: {task['title']}",
                message + "\n\nأُعيدت المهمة إلى الحالة الجديدة لتتمكن من إعادة المحاولة.",
                employee_id=employee_id,
            )
        await asyncio.sleep(1)
