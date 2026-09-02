from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import supabase
from auth_utils import get_current_user
import config

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class SessionCreate(BaseModel):
    session_type: str = "career"

@router.post("")
async def create_session(data: SessionCreate, current_user: dict = Depends(get_current_user)):
    session_data = {
        "user_id": current_user["id"],
        "session_type": data.session_type,
        "status": "active",
        "started_at": datetime.utcnow().isoformat(),
        "transcript": "",
        "recommendations": []
    }
    result = supabase.table("guidance_sessions").insert(session_data).execute()
    return result.data[0]

@router.get("/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    result = supabase.table("guidance_sessions").select("*").eq("id", session_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    session = result.data
    if session["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return session

@router.post("/{session_id}/end")
async def end_session(session_id: str, current_user: dict = Depends(get_current_user)):
    result = supabase.table("guidance_sessions").select("*").eq("id", session_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    session = result.data
    summary = ""
    if session.get("transcript"):
        summary_prompt = f"Summarize this career guidance conversation and provide 3 key recommendations:\n\n{session['transcript']}"
        if config.groq_client:
            try:
                summary = config.groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[{"role": "user", "content": summary_prompt}],
                    max_tokens=300
                ).choices[0].message.content or ""
            except Exception as e:
                print(f"Failed to generate session summary: {e}")

    update_data = {
        "status": "completed",
        "ended_at": datetime.utcnow().isoformat(),
        "summary": summary
    }
    supabase.table("guidance_sessions").update(update_data).eq("id", session_id).execute()
    return {"status": "completed", "summary": summary}
