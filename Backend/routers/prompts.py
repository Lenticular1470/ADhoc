import os
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import supabase
from auth_utils import get_current_user
import config

router = APIRouter(prefix="", tags=["prompts"])

class PromptCreate(BaseModel):
    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    variables: List[str] = []

class SettingsUpdate(BaseModel):
    groq_api_key: str

@router.post("/api/prompts")
async def create_prompt(data: PromptCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Admin/Faculty access required")

    prompt_data = {
        "name": data.name,
        "description": data.description,
        "system_prompt": data.system_prompt,
        "user_prompt_template": data.user_prompt_template,
        "variables": data.variables,
        "created_by": current_user["id"],
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }
    result = supabase.table("prompt_templates").insert(prompt_data).execute()
    return result.data[0]

@router.get("/api/prompts")
async def get_prompts():
    result = supabase.table("prompt_templates").select("*").eq("is_active", True).execute()
    return result.data or []

@router.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    result = supabase.table("prompt_templates").select("*").eq("id", prompt_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return result.data

@router.get("/api/settings/groq-key")
async def get_groq_key_status(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    has_key = bool(config.GROQ_API_KEY)
    masked_key = ""
    if has_key:
        masked_key = config.GROQ_API_KEY[:6] + "..." + config.GROQ_API_KEY[-4:] if len(config.GROQ_API_KEY) > 10 else "Configured"
    return {"configured": has_key, "masked_key": masked_key}

@router.post("/api/settings/groq-key")
async def update_groq_key(data: SettingsUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    key = data.groq_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Key cannot be empty")
        
    config.reload_groq_client(key)
    os.environ["GROQ_API_KEY"] = key
    
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = []
            found = False
            for line in lines:
                if line.startswith("GROQ_API_KEY="):
                    new_lines.append(f"GROQ_API_KEY={key}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"\nGROQ_API_KEY={key}\n")
                
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"Failed to write to .env: {e}")
            
    return {"success": True, "message": "Groq API key updated successfully"}

@router.post("/api/prompts/{prompt_id}/test")
async def test_prompt(prompt_id: str, variables: Dict[str, str]):
    result = supabase.table("prompt_templates").select("*").eq("id", prompt_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt = result.data
    user_prompt = prompt["user_prompt_template"]
    for key, value in variables.items():
        user_prompt = user_prompt.replace(f"{{{key}}}", value)

    if not config.groq_client:
        raise HTTPException(status_code=500, detail="Groq not configured")

    messages_for_groq: List[Dict[str, str]] = [
        {"role": "system", "content": prompt["system_prompt"]},
        {"role": "user", "content": user_prompt}
    ]

    response = config.groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=messages_for_groq,
        max_tokens=500
    )

    return {
        "rendered_prompt": user_prompt,
        "response": response.choices[0].message.content or ""
    }
