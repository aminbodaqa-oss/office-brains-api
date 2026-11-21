from __future__ import annotations

import asyncio
import json

from brains import PROVIDER, employee_reply
from database import add_notification, log_interaction
from employees import EMPLOYEES, management_context_for
from vindora_client import employee_context
from workflow import claim_next_task_execution, fail_task_execution, finish_task_execution, save_delegation_plan


async def task_execution_loop() -> None:
    """Process queued AI-capable office tasks and leave every deliverable for owner review."""
    while True:
        if PROVIDER == "demo":
            await asyncio.sleep(15)
            continue

        try:
            task = claim_next_task_execution()
        except Exception:
            await asyncio.sleep(10)
            continue
        if not task:
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
            try:
                context = await employee_context(employee_id, days=7)
            except Exception:
                context = "لا تتوفر بيانات خارجية إضافية. اعتمد على تفاصيل المهمة فقط."

            system = (
                "أنت موظف متخصص داخل مكتب Vindora، ومطلوب منك إعداد مخرج عملي للمهمة المسندة إليك. "
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
            if employee_id == "ابراهيم" and task.get("source") != "delegation":
                try:
                    team = [
                        {"id": item["id"], "role": item.get("role", ""), "department": item.get("department", "")}
                        for item in EMPLOYEES if item["id"] != "ابراهيم"
                    ]
                    delegation_system = (
                        "أنت إبراهيم المدير العام في مكتب Vindora. حوّل توصيات المهمة الرئيسية إلى خطة مهام فرعية عملية. "
                        "لا تنفذ أي إجراء ولا تدّعِ أنك أرسلت التكليفات. أخرج JSON فقط بالشكل "
                        '{"delegations":[{"title":"...","description":"...","assigned_to":"اسم الموظف حرفيًا من القائمة","priority":"normal"}]}. '
                        "اختر من 1 إلى 5 مهام فقط، ولا تكرر التوصيات، ولا تسند عملًا خارج اختصاص الموظف. "
                        'إذا لم توجد مهام قابلة للتفويض فأخرج {"delegations":[]}.'
                    )
                    delegation_prompt = (
                        "التقرير المنجز:\\n" + result[:14000] + "\\n\\n"
                        "قائمة الفريق المسموح بالتكليف إليه:\\n" +
                        json.dumps(team, ensure_ascii=False) +
                        "\\n\\nاقترح المهام الفرعية. استخدم assigned_to من id فقط، والأولوية واحدة من low/normal/high/urgent."
                    )
                    raw_plan = (await employee_reply(
                        delegation_system, [{"role": "user", "content": delegation_prompt}]
                    )).strip()
                    start, end = raw_plan.find("{"), raw_plan.rfind("}")
                    parsed = json.loads(raw_plan[start:end + 1]) if start >= 0 and end > start else {}
                    allowed = {item["id"] for item in team}
                    proposals = parsed.get("delegations", [])
                    clean_plan = []
                    if isinstance(proposals, list):
                        for item in proposals[:5]:
                            if not isinstance(item, dict):
                                continue
                            assignee = str(item.get("assigned_to", "")).strip()
                            title = str(item.get("title", "")).strip()
                            description = str(item.get("description", "")).strip()
                            priority = str(item.get("priority", "normal")).strip()
                            if assignee in allowed and title and priority in {"low", "normal", "high", "urgent"}:
                                clean_plan.append({"title": title[:180], "description": description[:5000],
                                                   "assigned_to": assignee, "priority": priority})
                    if clean_plan and save_delegation_plan(task_id, clean_plan):
                        add_notification(
                            "delegation_plan_ready",
                            f"خطة توزيع إبراهيم جاهزة للموافقة · #{task_id}",
                            f"إبراهيم اقترح {len(clean_plan)} مهام فرعية. لم تُرسل التكليفات بعد.",
                            "راجع المقترحات ثم اعتمد توزيعها من لوحة مهام الشركة."
                        )
                except Exception:
                    # The employee's main deliverable remains valid even if delegation planning fails.
                    pass

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
