from __future__ import annotations
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
from database import add_memory, get_memories, init_db, log_interaction, add_notification, get_notifications, mark_notifications_read
from employees import EMPLOYEES, EMPLOYEE_IDS
from brains import BrainUnavailable, employee_reply
from auth import issue_token, require_owner, verify_password
from vindora_client import VindoraUnavailable, employee_context
from automation import automation_status, recent_reports, scheduler_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
                   allow_methods=["GET", "POST", "OPTIONS"],
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

class NotificationReadRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=100)
    all_read: bool = False

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

@app.get("/api/automation/status")
async def get_automation_status(_: str = Depends(require_owner)):
    return automation_status()

@app.get("/api/automation/reports")
async def get_automation_reports(limit: int = 30, _: str = Depends(require_owner)):
    return {"reports": recent_reports(limit)}

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
