from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import Literal
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
from database import add_memory, get_memories, init_db, log_interaction
from employees import EMPLOYEES, EMPLOYEE_IDS
from brains import BrainUnavailable, employee_reply

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Office Brains API", version="0.1.0", lifespan=lifespan)
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["Content-Type", "X-API-Key"])

async def verify_api_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("OFFICE_API_KEY", "").strip()
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="مفتاح الوصول غير صحيح")

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)

class ChatRequest(BaseModel):
    employee_id: str
    role: str = ""
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

class MemoryRequest(BaseModel):
    employee_id: str
    content: str = Field(min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)

@app.get("/")
async def root():
    return {"name": "Office Brains API", "version": "0.1.0", "health": "/health"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "office-brains-api", "provider": os.getenv("BRAIN_PROVIDER", "demo")}

@app.get("/api/employees", dependencies=[Depends(verify_api_key)])
async def employees():
    return {"employees": EMPLOYEES}

@app.post("/api/chat", dependencies=[Depends(verify_api_key)])
async def chat(body: ChatRequest):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    memories = get_memories(body.employee_id, 12)
    system = "أنت موظف افتراضي متخصص داخل مكتب. التزم بالشخصية والتعليمات المرسلة. لا تخترع بيانات، واسأل عند نقص المعلومات. "
    if memories:
        system += "\nذكريات محفوظة لهذا الموظف:\n" + "\n".join("- " + m["content"] for m in reversed(memories))
    try:
        content = await employee_reply(system, [m.model_dump() for m in body.messages])
    except BrainUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_interaction(body.employee_id, "chat", {"messages": [m.model_dump() for m in body.messages], "response": content})
    return {"employee_id": body.employee_id, "content": content}

@app.post("/api/meeting/respond", dependencies=[Depends(verify_api_key)])
async def meeting_respond(body: MeetingRequest):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    system = "أنت موظف في اجتماع عمل. اتكلم بالعامية المصرية، بإيجاز، ولا تخترع معلومات.\n" + body.employee_prompt + "\n" + body.personality + "\n" + body.company_context + "\n" + body.rules
    prompt = "الوقت: " + body.time + "\nسياق الاجتماع حتى الآن:\n" + body.transcript + "\n\nالمطلوب منك:\n" + body.instruction
    try:
        content = await employee_reply(system, [{"role": "user", "content": prompt}])
    except BrainUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_interaction(body.employee_id, "meeting", {"transcript": body.transcript, "instruction": body.instruction, "response": content})
    return {"employee_id": body.employee_id, "content": content}

@app.post("/api/memories", dependencies=[Depends(verify_api_key)])
async def create_memory(body: MemoryRequest):
    if body.employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    memory_id = add_memory(body.employee_id, body.content, body.tags)
    return {"id": memory_id, "saved": True}

@app.get("/api/memories/{employee_id}", dependencies=[Depends(verify_api_key)])
async def list_memories(employee_id: str, limit: int = 20):
    if employee_id not in EMPLOYEE_IDS:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    return {"memories": get_memories(employee_id, limit)}
