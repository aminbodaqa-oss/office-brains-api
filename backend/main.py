from __future__ import annotations
import json
import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Literal
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
from database import add_memory, get_memories, init_db, log_interaction, add_notification, get_notifications, mark_notifications_read, delete_chat_interactions
from employees import EMPLOYEES, EMPLOYEE_IDS
from brains import BrainUnavailable, employee_reply
from auth import issue_token, require_owner, verify_password
from vindora_client import VindoraUnavailable, employee_context
from automation import automation_status, recent_reports, scheduler_loop
from workflow import (TASK_PRIORITIES, TASK_STATUSES, create_task, update_task, list_tasks, create_meeting, list_meetings, list_activity, workflow_overview, log_activity, init_workflow_db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_workflow_db()
    scheduler_task = None
    if os.getenv("AUTONOMOUS_OFFICE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        scheduler_task = asyncio.create_task(scheduler_loop())
    try:
        yield
    finally:
        if scheduler_task:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

app = FastAPI(title="Office Brains API", version="0.2.0", lifespan=lifespan)
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "https://aminbodaqa-oss.github.io").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
                   allow_headers=["Content-Type", "Authorization"])

_login_attempts: dict[str, list[float]] = {}

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)

@app.post("/api/auth/login")
async def login(body: LoginRequest, request: Request):
    now = time.time()
    client_ip = request.client.host if request.client else "unknown"
    attempts = [stamp for stamp in _login_attempts.get(client_ip, []) if now - stamp < 900]
    if len(attempts) >= 8:
        raise HTTPException(status_code=429, detail="محاولات دخول كثيرة. انتظر 15 دقيقة ثم حاول مجددًا.")
    expected_user = os.getenv("OWNER_USERNAME", "").strip()
    password_hash = os.getenv("OWNER_PASSWORD_HASH", "").strip()
    if not expected_user or not password_hash:
        raise HTTPException(status_code=503, detail="إعداد حساب المالك غير مكتمل على السيرفر.")
    valid_user = body.username.strip() == expected_user
    valid_password = verify_password(body.password, password_hash)
    if not (valid_user and valid_password):
        attempts.append(now)
        _login_attempts[client_ip] = attempts
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة.")
    _login_attempts.pop(client_ip, None)
    try:
        token = issue_token(expected_user)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"access_token": token, "token_type": "bearer", "expires_in": int(os.getenv("OFFICE_TOKEN_TTL_SECONDS", "1800"))}

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)

class ChatRequest(BaseModel):
    employee_id: str
    role: str = ""
    employee_prompt: str = ""
    messages: list[Message] = Field(min_length=1, max_length=30)

class MeetingRequest(BaseModel):
    employee_id: str
    role: str = ""
    employee_prompt: str = ""
    personality: str = ""
    company_context: str = ""
    rules: str = ""
    time: str = ""
    transcript: str = ""
    instruction: str = ""


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=5000)
    assigned_to: str = Field(min_length=1, max_length=120)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: str | None = None

class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["open", "in_progress", "review", "completed", "cancelled"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_at: str | None = None

class MeetingCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    agenda: str = Field(default="", max_length=5000)
    attendees: list[str] = Field(default_factory=list, max_length=20)
    scheduled_at: str = Field(min_length=10, max_length=80)

class SecretaryRequest(BaseModel):
    message: str = Field(default="نظمي لي يومي ووريني أهم المهام والمواعيد اللي محتاجة متابعة.", max_length=6000)

class NotificationReadRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=100)
    all_read: bool = False

class NotificationEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=180)
    message: str = Field(min_length=1, max_length=1000)
    details: str = Field(default="", max_length=12000)

class ChatDeleteRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=120)

class MemoryRequest(BaseModel):
    employee_id: str
    content: str = Field(min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)

@app.get("/")
async def root():
    return {"name": "Office Brains API", "version": "0.2.0", "health": "/health"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "office-brains-api", "provider": os.getenv("BRAIN_PROVIDER", "demo")}

@app.get("/api/employees")
async def employees(_: str = Depends(require_owner)):
    return {"employees": EMPLOYEES}

@app.get("/api/notifications")
async def list_notifications(limit: int = 50, unread_only: bool = False, _: str = Depends(require_owner)):
    return get_notifications(limit, unread_only)

@app.post("/api/notifications/read")
async def read_notifications(body: NotificationReadRequest, _: str = Depends(require_owner)):
    return {"updated": mark_notifications_read(body.ids, body.all_read)}

@app.post("/api/notifications/event")
async def create_notification_event(body: NotificationEventRequest, _: str = Depends(require_owner)):
    notification_id = add_notification(body.event_type, body.title, body.message, body.details)
    return {"id": notification_id, "saved": True}

@app.get("/api/automation/status")
async def get_automation_status(_: str = Depends(require_owner)):
    return automation_status()

@app.get("/api/automation/reports")
async def get_automation_reports(limit: int = 30, _: str = Depends(require_owner)):
    return {"reports": recent_reports(limit)}

@app.post("/api/chat/delete")
async def delete_chat(body: ChatDeleteRequest, _: str = Depends(require_owner)):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    deleted = delete_chat_interactions(body.employee_id)
    return {"employee_id": body.employee_id, "deleted": deleted}

@app.post("/api/chat")
async def chat(body: ChatRequest, _: str = Depends(require_owner)):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    memories = get_memories(body.employee_id, 12)
    system = "أنت موظف افتراضي متخصص داخل مكتب. التزم بالشخصية والتعليمات المرسلة. لا تخترع بيانات، واسأل عند نقص المعلومات. " + body.employee_prompt
    if memories:
        system += "\nذكريات محفوظة لهذا الموظف:\n" + "\n".join("- " + m["content"] for m in reversed(memories))
    try:
        system += await employee_context(body.employee_id)
        content = await employee_reply(system, [m.model_dump() for m in body.messages])
    except VindoraUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BrainUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_interaction(body.employee_id, "chat", {"messages": [m.model_dump() for m in body.messages], "response": content})
    last_user = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
    add_notification("chat", "محادثة جديدة مع " + body.employee_id,
        "الموظف رد على رسالتك داخل المكتب.", "رسالتك: " + last_user + "\n\nرد الموظف:\n" + content)
    return {"employee_id": body.employee_id, "content": content}

@app.post("/api/meeting/respond")
async def meeting_respond(body: MeetingRequest, _: str = Depends(require_owner)):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    system = "أنت موظف في اجتماع عمل. اتكلم بالعامية المصرية، بإيجاز، ولا تخترع معلومات.\n" + body.employee_prompt + "\n" + body.personality + "\n" + body.company_context + "\n" + body.rules
    prompt = "الوقت: " + body.time + "\nسياق الاجتماع حتى الآن:\n" + body.transcript + "\n\nالمطلوب منك:\n" + body.instruction
    try:
        system += await employee_context(body.employee_id)
        content = await employee_reply(system, [{"role": "user", "content": prompt}])
    except VindoraUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BrainUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_interaction(body.employee_id, "meeting", {"transcript": body.transcript, "instruction": body.instruction, "response": content})
    add_notification("meeting", "مداخلة من " + body.employee_id,
        "وصل رد جديد أثناء جلسة الاجتماع.", "التوجيه: " + body.instruction + "\n\nالرد:\n" + content)
    return {"employee_id": body.employee_id, "content": content}


@app.get("/api/workspace/overview")
async def get_workspace_overview(_: str = Depends(require_owner)):
    return workflow_overview()

@app.get("/api/tasks")
async def get_tasks(limit: int = 100, status: str | None = None, assigned_to: str | None = None,
                    _: str = Depends(require_owner)):
    if status and status not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail="حالة المهمة غير صحيحة.")
    if assigned_to and assigned_to not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود.")
    return {"tasks": list_tasks(limit, status, assigned_to)}

@app.post("/api/tasks")
async def post_task(body: TaskCreateRequest, _: str = Depends(require_owner)):
    if body.assigned_to not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف المسؤول غير موجود.")
    if body.priority not in TASK_PRIORITIES:
        raise HTTPException(status_code=400, detail="درجة أولوية غير صحيحة.")
    task = create_task(body.title, body.description, body.assigned_to, "الريّس",
                       body.priority, body.due_at, "owner")
    add_notification("task_created", "مهمة جديدة لسلمى/الفريق",
        "تم تسجيل مهمة وتكليف " + body.assigned_to + ".", 
        "المهمة: " + body.title + "\nالأولوية: " + body.priority + "\nالموعد: " + (body.due_at or "غير محدد"))
    return {"saved": True, "task": task}

@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: int, body: TaskUpdateRequest, _: str = Depends(require_owner)):
    updates = body.model_dump(exclude_unset=True)
    if "assigned_to" in updates and updates["assigned_to"] not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف المسؤول غير موجود.")
    if "status" in updates and updates["status"] not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail="حالة المهمة غير صحيحة.")
    if "priority" in updates and updates["priority"] not in TASK_PRIORITIES:
        raise HTTPException(status_code=400, detail="درجة أولوية غير صحيحة.")
    task = update_task(task_id, updates, "الريّس")
    if task is None:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة.")
    add_notification("task_updated", "تحديث مهمة #" + str(task_id),
        "تم تحديث حالة أو تفاصيل المهمة.", "المهمة: " + task["title"] + "\nالحالة: " + task["status"])
    return {"saved": True, "task": task}

@app.get("/api/meetings")
async def get_meetings(limit: int = 50, _: str = Depends(require_owner)):
    return {"meetings": list_meetings(limit)}

@app.post("/api/meetings")
async def post_meeting(body: MeetingCreateRequest, _: str = Depends(require_owner)):
    if not body.attendees:
        raise HTTPException(status_code=400, detail="اختار موظفًا واحدًا على الأقل للاجتماع.")
    unknown = [name for name in body.attendees if name not in EMPLOYEE_IDS]
    if unknown:
        raise HTTPException(status_code=400, detail="يوجد اسم موظف غير معروف: " + "، ".join(unknown))
    try:
        scheduled = body.scheduled_at.replace("Z", "+00:00")
        from datetime import datetime
        datetime.fromisoformat(scheduled)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="صيغة موعد الاجتماع غير صحيحة.") from exc
    meeting = create_meeting(body.title, body.agenda, body.attendees, body.scheduled_at, "الريّس")
    add_notification("meeting_scheduled", "تمت جدولة اجتماع جديد",
        body.title + " · " + body.scheduled_at,
        "الحضور: " + "، ".join(body.attendees) + "\nجدول الأعمال:\n" + body.agenda)
    return {"saved": True, "meeting": meeting}

@app.get("/api/activity")
async def get_activity(limit: int = 60, _: str = Depends(require_owner)):
    return {"activity": list_activity(limit)}

@app.post("/api/secretary/briefing")
async def secretary_briefing(body: SecretaryRequest, _: str = Depends(require_owner)):
    overview = workflow_overview()
    reports = recent_reports(12)
    tasks_text = "\n".join(
        f"- #{item['id']} {item['title']} | المسؤول: {item['assigned_to']} | الحالة: {item['status']} | الأولوية: {item['priority']} | الموعد: {item.get('due_at') or 'غير محدد'}"
        for item in overview["tasks"]
    ) or "لا توجد مهام مسجلة بعد."
    meetings_text = "\n".join(
        f"- {item['title']} | الموعد: {item['scheduled_at']} | الحضور: {'، '.join(item.get('attendees') or [])} | الحالة: {item['status']}"
        for item in overview["meetings"]
    ) or "لا توجد اجتماعات مسجلة."
    activity_text = "\n".join(
        f"- {item['created_at']} | {item['actor']} | {item['summary']}"
        for item in overview["activity"][:15]
    ) or "لا يوجد نشاط مسجل بعد."
    reports_text = "\n\n".join(
        f"{item['employee_id']} ({item['run_date']}):\n{item['content'][:1800]}"
        for item in reports[:8]
    ) or "لا توجد تقارير يومية محفوظة."
    system = (
        "أنتِ سلمى، السكرتيرة التنفيذية والمساعدة الشخصية لصاحب Vindora. أنتِ حلقة التنسيق بين المالك وإبراهيم المدير العام وباقي الموظفين. "
        "شخصيتك مصرية نغشة وخفيفة الدم وذكية، بتاخدي وتدي مع الريّس باحترام ومن غير مبالغة، لكن في التنظيم دقيقة وحازمة. "
        "مهمتك تنظيم يوم المالك، ترتيب الأولويات، متابعة المهام والمواعيد والاجتماعات، تلخيص ما حدث، تجهيز جداول الأعمال ومحاضر الاجتماعات، "
        "التنبيه للمتأخرات والتعارضات، واقتراح الشخص المناسب لكل متابعة. استخدمي البيانات المرفقة فقط. "
        "لا تقولي إنك أرسلتي تذكيرًا أو كلفتي موظفًا أو حجزتي اجتماعًا إلا إذا ظهر ذلك صراحة في البيانات. "
        "لو اقترحتي مهمة جديدة، اكتبيها كمقترح ينتظر موافقة الريّس ولا تسجليها بنفسك. "
        "فرّقي بوضوح بين المسجل فعليًا، والاستنتاج، والاقتراح. لا تختلقي مواعيد أو إنجازات أو رسائل. "
        "اكتبي بالعامية المصرية، مختصرة ومنظمة، وابدئي بالأهم."
    )
    prompt = (
        "طلب الريّس: " + body.message +
        "\n\nملخص النظام الحالي:\n" + json.dumps({
            "task_counts": overview["task_counts"], "tasks_total": overview["tasks_total"],
            "upcoming_meetings": overview["upcoming_meetings"], "overdue_tasks": overview["overdue_tasks"]
        }, ensure_ascii=False) +
        "\n\nالمهام الحالية:\n" + tasks_text +
        "\n\nالاجتماعات المسجلة:\n" + meetings_text +
        "\n\nآخر نشاط محفوظ:\n" + activity_text +
        "\n\nتقارير الموظفين الأخيرة:\n" + reports_text +
        "\n\nقدمي ردًا عمليًا للريّس، واذكري ما يحتاج موافقته."
    )
    try:
        answer = await employee_reply(system, [{"role": "user", "content": prompt}])
    except BrainUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_interaction("سلمى", "secretary", {"request": body.message, "response": answer})
    log_activity("سلمى", "secretary_briefing", "workspace", None, "سلمى أعدّت ملخص متابعة للريّس", body.message)
    add_notification("secretary_briefing", "سلمى جهزت لك ملخص متابعة",
        "السكرتيرة التنفيذية أعدّت ردًا بناءً على المهام والاجتماعات والنشاط المسجل.",
        answer)
    return {"employee_id": "سلمى", "content": answer, "overview": {
        "tasks_total": overview["tasks_total"], "overdue_tasks": overview["overdue_tasks"],
        "upcoming_meetings": overview["upcoming_meetings"]
    }}

@app.post("/api/memories")
async def create_memory(body: MemoryRequest, _: str = Depends(require_owner)):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    memory_id = add_memory(body.employee_id, body.content, body.tags)
    return {"id": memory_id, "saved": True}

@app.get("/api/memories/{employee_id}")
async def list_memories(employee_id: str, limit: int = 20, _: str = Depends(require_owner)):
    if employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    return {"memories": get_memories(employee_id, limit)}
