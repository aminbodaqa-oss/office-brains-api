import os
import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import connect, initialize_database
from .employees import BY_ID, EMPLOYEES


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Office Brains API",
    description="Standalone backend foundation for specialized digital employees.",
    version="0.1.0",
    lifespan=lifespan,
)

allowed_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    category: str = Field(default="general", min_length=1, max_length=40)


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("OFFICE_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="OFFICE_API_KEY is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/")
def root():
    return {"name": "Office Brains API", "version": "0.1.0", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"ok": True, "service": "office-brains-api", "ai_engine": "not_configured"}


@app.get("/api/employees")
def list_employees():
    return {"count": len(EMPLOYEES), "employees": EMPLOYEES}


@app.get("/api/employees/{employee_id}")
def get_employee(employee_id: str):
    employee = BY_ID.get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@app.get("/api/employees/{employee_id}/memories")
def list_memories(employee_id: str, limit: int = Query(default=20, ge=1, le=100)):
    if employee_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Employee not found")
    with connect() as db:
        rows = db.execute(
            "SELECT id, employee_id, content, category, created_at FROM memories WHERE employee_id=? ORDER BY id DESC LIMIT ?",
            (employee_id, limit),
        ).fetchall()
    return {"employee_id": employee_id, "memories": [dict(row) for row in rows]}


@app.post("/api/employees/{employee_id}/memories", dependencies=[Depends(require_api_key)], status_code=201)
def add_memory(employee_id: str, payload: MemoryInput):
    if employee_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Employee not found")
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO memories (employee_id, content, category) VALUES (?, ?, ?)",
            (employee_id, payload.content, payload.category),
        )
        row = db.execute(
            "SELECT id, employee_id, content, category, created_at FROM memories WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
    return {"saved": True, "memory": dict(row)}


@app.get("/api/status")
def system_status():
    return {
        "service": "online",
        "employee_count": len(EMPLOYEES),
        "memory_store": "sqlite",
        "language_model": "not_connected",
        "note": "This is the backend foundation. No AI responses are simulated.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
