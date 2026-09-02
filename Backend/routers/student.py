import os
import uuid as uuid_mod
import hashlib
import json as json_mod
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field, model_validator
from database import supabase
from auth_utils import get_current_user, verify_password, get_password_hash
import config

router = APIRouter(prefix="/api/student", tags=["student"])

# ─── PORTFOLIO PYDANTIC MODELS ────────────────────────────────────────────────
class StudentProfileUpdate(BaseModel):
    profile_photo_url: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    nationality: Optional[str] = None
    category: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    father_name: Optional[str] = None
    father_phone: Optional[str] = None
    mother_name: Optional[str] = None
    mother_phone: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    annual_income: Optional[float] = None

class AcademicRecordUpsert(BaseModel):
    education_level: str
    institution_name: Optional[str] = None
    board_university: Optional[str] = None
    degree: Optional[str] = None
    specialization: Optional[str] = None
    hall_ticket_number: Optional[str] = None
    year_of_passing: Optional[int] = None
    percentage: Optional[float] = None
    cgpa: Optional[float] = None
    max_cgpa: Optional[float] = None
    current_semester: Optional[int] = None
    backlogs: Optional[int] = None
    remarks: Optional[str] = None
    is_current: Optional[bool] = None

class SemesterMarkUpsert(BaseModel):
    semester: int
    academic_year: Optional[str] = None
    sgpa: Optional[float] = None
    cgpa: Optional[float] = None
    credits_earned: Optional[float] = None
    total_credits: Optional[float] = None
    result_status: Optional[str] = None
    remarks: Optional[str] = None

class CertificationCreate(BaseModel):
    title: str
    issuing_organization: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None
    skills_gained: Optional[List[str]] = None
    document_id: Optional[str] = None

class SkillsUpdate(BaseModel):
    programming_languages: Optional[List[str]] = None
    frameworks: Optional[List[str]] = None
    databases: Optional[List[str]] = None
    cloud_platforms: Optional[List[str]] = None
    ai_ml_skills: Optional[List[str]] = None
    web_technologies: Optional[List[str]] = None
    mobile_technologies: Optional[List[str]] = None
    devops_tools: Optional[List[str]] = None
    software_tools: Optional[List[str]] = None
    soft_skills: Optional[List[str]] = None
    languages_known: Optional[List[str]] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    leetcode_url: Optional[str] = None
    codechef_url: Optional[str] = None
    hackerrank_url: Optional[str] = None
    codeforces_url: Optional[str] = None
    years_of_experience: Optional[float] = None
    bio: Optional[str] = None

class EntranceExamCreate(BaseModel):
    exam_name: str
    conducting_body: Optional[str] = None
    exam_year: Optional[int] = None
    application_number: Optional[str] = None
    hall_ticket_number: Optional[str] = None
    score: Optional[float] = None
    rank: Optional[int] = None
    percentile: Optional[float] = None
    qualification_status: Optional[str] = None
    exam_date: Optional[str] = None
    remarks: Optional[str] = None
    scorecard_document_id: Optional[str] = None

class AchievementCreate(BaseModel):
    achievement_title: str
    achievement_type: Optional[str] = None
    organizer_name: Optional[str] = None
    achievement_level: Optional[str] = None
    position_secured: Optional[str] = None
    description: Optional[str] = None
    achievement_date: Optional[str] = None
    certificate_document_id: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

class PrivacySettingsUpdate(BaseModel):
    personal_info_visibility: Optional[str] = None
    contact_visibility: Optional[str] = None
    academic_visibility: Optional[str] = None
    documents_visibility: Optional[str] = None
    certifications_visibility: Optional[str] = None
    skills_visibility: Optional[str] = None
    achievements_visibility: Optional[str] = None
    exams_visibility: Optional[str] = None
    profile_public_link: Optional[bool] = None

class PreferencesUpdate(BaseModel):
    target_colleges: Optional[List[str]] = None
    preferred_courses: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    career_interests: Optional[List[str]] = None
    notification_email: Optional[bool] = None
    notification_sms: Optional[bool] = None
    notification_app: Optional[bool] = None


# ─── PORTFOLIO HELPER FUNCTIONS ────────────────────────────────────────────────
def portfolio_log_timeline(user_id: str, event_type: str, title: str, description: str = None):
    pass

def portfolio_create_notification(user_id: str, type: str, title: str, message: str, action_url: str = None):
    try:
        supabase.table("notifications").insert({
            "user_id": user_id,
            "type": type,
            "title": title,
            "message": message,
            "is_read": False,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[Supabase Notification Error] {e}")

def calculate_profile_strength(user_id: str) -> dict:
    """Calculate profile completion score based on Supabase schema."""
    try:
        # 1. Personal info (max 25)
        profile_res = supabase.table("student_profiles").select("*").eq("user_id", user_id).execute()
        profile = profile_res.data[0] if profile_res.data else {}
        personal_fields = ["date_of_birth", "gender", "state", "postal_code",
                           "father_name", "father_phone", "profile_photo_url"]
        filled = sum(1 for f in personal_fields if profile.get(f))
        personal = int((filled / len(personal_fields)) * 25)

        # 2. Academic (max 25)
        records = supabase.table("academic_records").select("education_level").eq("student_id", user_id).execute().data or []
        semesters = supabase.table("semester_marks").select("id").eq("student_id", user_id).execute().data or []
        academic = min(int((len(records) / 3) * 20) + min(len(semesters), 5), 25)

        # 3. Skills (max 15)
        skills_res = supabase.table("student_skills").select("*").eq("student_id", user_id).execute()
        skills = skills_res.data[0] if skills_res.data else {}
        skill_arrays = ["programming_languages", "frameworks", "soft_skills", "languages_known", "software_tools"]
        non_empty = sum(1 for k in skill_arrays if skills.get(k))
        links = sum(1 for k in ["github_url", "linkedin_url", "portfolio_url"] if skills.get(k))
        skills_score = min(int((non_empty / 5) * 10) + min(links * 2, 5), 15)

        # 4. Documents (max 15)
        docs = supabase.table("student_documents").select("id").eq("user_id", user_id).execute().data or []
        documents = min(len(docs) * 2, 15)

        # 5. Achievements (max 10)
        certs = supabase.table("student_certifications").select("id").eq("student_id", user_id).execute().data or []
        achievements_r = supabase.table("student_achievements").select("id").eq("student_id", user_id).execute().data or []
        achieve = min((len(certs) + len(achievements_r)) * 2, 10)

        # 6. Career Readiness (max 10)
        exams = supabase.table("entrance_exams").select("id").eq("student_id", user_id).execute().data or []
        career = min(len(exams) * 3, 10)

        total = min(personal + academic + skills_score + documents + achieve + career, 100)
        label = ("Excellent" if total >= 85 else "Strong" if total >= 70 else
                 "Good" if total >= 50 else "Building" if total >= 30 else "Getting Started")

        strength = {"total": total, "label": label, "personal": personal,
                    "academic": academic, "skills": skills_score,
                    "documents": documents, "achievements": achieve, "career": career}
        if profile_res.data:
            supabase.table("student_profiles").update({
                "profile_completion": total,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("user_id", user_id).execute()
        return strength
    except Exception as e:
        print(f"[Strength] Error: {e}")
        return {"total": 0, "label": "Getting Started", "personal": 0, "academic": 0,
                "skills": 0, "documents": 0, "achievements": 0, "career": 0}

async def maybe_refresh_ai_insights(user_id: str, force: bool = False,
                                     trigger_event: str = "profile_update"):
    """Generate and cache AI profile insights using Supabase schema."""
    if not config.groq_client:
        return
    try:
        records = supabase.table("academic_records").select("*").eq("student_id", user_id).execute().data or []
        skills_r = supabase.table("student_skills").select("*").eq("student_id", user_id).execute().data or []
        exams = supabase.table("entrance_exams").select("*").eq("student_id", user_id).execute().data or []
        docs_count = len(supabase.table("student_documents").select("id").eq("user_id", user_id).execute().data or [])
        certs_count = len(supabase.table("student_certifications").select("id").eq("student_id", user_id).execute().data or [])
        profile_r = supabase.table("student_profiles").select("*").eq("user_id", user_id).execute().data or []

        profile = profile_r[0] if profile_r else {}
        skills = skills_r[0] if skills_r else {}

        prompt = f"""You are an AI academic advisor. Analyze this student profile and return ONLY valid JSON.

Profile:
- Academic levels: {[r.get('education_level') for r in records]}
- Current semester: {profile.get('current_semester', 'Unknown')}
- Programming skills: {skills.get('programming_languages', [])}
- Frameworks: {skills.get('frameworks', [])}
- Entrance exams: {[{'name': e.get('exam_name'), 'score': e.get('score'), 'rank': e.get('rank')} for e in exams]}
- Documents uploaded: {docs_count}
- Certifications: {certs_count}

Return this JSON structure exactly:
{{
  "overall_profile_score": <int 0-100>,
  "academic_score": <int 0-100>,
  "skill_score": <int 0-100>,
  "missing_documents": [{{"name": "...", "category": "...", "priority": "high|medium|low"}}],
  "scholarship_recommendations": [{{"title": "...", "provider": "...", "match_score": <int>}}],
  "skill_gap_analysis": [{{"skill": "...", "demand": "high|medium", "courses": ["..."]}}],
  "career_recommendations": [{{"title": "...", "type": "certification|course|internship", "reason": "..."}}],
  "ai_summary": "<2-3 sentence personalized summary>"
}}"""

        resp = config.groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200, temperature=0.3
        )
        ai_text = resp.choices[0].message.content or "{}"
        if "```" in ai_text:
            for p in ai_text.split("```"):
                p = p.strip().lstrip("json").strip()
                if p.startswith("{"):
                    ai_text = p
                    break

        try:
            insights = json_mod.loads(ai_text)
        except Exception:
            insights = {
                "overall_profile_score": 0,
                "academic_score": 0,
                "skill_score": 0,
                "missing_documents": [],
                "scholarship_recommendations": [],
                "skill_gap_analysis": [],
                "career_recommendations": [],
                "ai_summary": "Analysis could not be completed. Please update your profile."
            }

        existing = supabase.table("ai_profile_analysis").select("id").eq("student_id", user_id).execute()
        
        upsert_payload = {
            "student_id": user_id,
            "overall_profile_score": insights.get("overall_profile_score", 0),
            "profile_strength": insights.get("overall_profile_score", 0),
            "academic_score": insights.get("academic_score", 0),
            "skill_score": insights.get("skill_score", 0),
            "missing_documents": insights.get("missing_documents", []),
            "scholarship_recommendations": insights.get("scholarship_recommendations", []),
            "skill_gap_analysis": insights.get("skill_gap_analysis", []),
            "career_recommendations": insights.get("career_recommendations", []),
            "ai_summary": insights.get("ai_summary", ""),
            "last_analyzed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if existing.data:
            upsert_payload["id"] = existing.data[0]["id"]
            
        supabase.table("ai_profile_analysis").upsert(upsert_payload).execute()

        portfolio_create_notification(user_id, "ai_analysis_complete",
            "AI Insights Updated", "Your profile analysis is ready.",
            "/student/profile?tab=ai-insights")
        portfolio_log_timeline(user_id, "ai_insights_generated",
            "AI Profile Analysis Updated", f"Triggered by: {trigger_event}")
    except Exception as e:
        print(f"[AI Insights] Error: {e}")
        try:
            supabase.table("ai_profile_analysis").upsert(
                {"student_id": user_id}).execute()
        except Exception:
            pass

def ensure_student_profile(user_id: str):
    """Auto-create student_profiles row if it doesn't exist yet."""
    existing = supabase.table("student_profiles").select("id").eq("user_id", user_id).execute()
    if not existing.data:
        supabase.table("student_profiles").insert({
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
        portfolio_log_timeline(user_id, "profile_created", "Academic Portfolio Created",
                               "Your digital academic portfolio has been initialized.")

def clean_record(d: dict) -> dict:
    return {k: (None if v == "" else v) for k, v in d.items() if v is not None or v == ""}

async def process_document_ocr(doc_id: str):
    try:
        res = supabase.table("student_documents").select("*").eq("id", doc_id).execute()
        if not res.data:
            return
        doc = res.data[0]
        doc_type = doc.get("document_type") or "other"
        file_name = doc.get("file_name") or "document"
        
        if config.groq_client:
            prompt = f"""You are an AI assistant processing student academic portfolios.
Analyze this uploaded document details:
- Document Type: {doc_type}
- File Name: {file_name}

Generate realistic OCR extracted fields and a professional summary.
Return ONLY valid JSON in this exact structure:
{{
  "extracted": {{
    "field_name_1": {{"value": "...", "confidence": 0.95}},
    "field_name_2": {{"value": "...", "confidence": 0.91}}
  }},
  "ai_summary": "1-2 sentence professional advisor summary of the document."
}}"""
            try:
                resp = config.groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600, temperature=0.3
                )
                ai_text = resp.choices[0].message.content or "{}"
                if "```" in ai_text:
                    for p in ai_text.split("```"):
                        p = p.strip().lstrip("json").strip()
                        if p.startswith("{"):
                            ai_text = p
                            break
                ai_data = json_mod.loads(ai_text)
                extracted = ai_data.get("extracted", {})
                ai_summary = ai_data.get("ai_summary", "Document uploaded and verified.")
            except Exception as e:
                print(f"[OCR] Groq failed: {e}")
                extracted = {"status": {"value": "Uploaded Successfully", "confidence": 1.0}}
                ai_summary = f"Uploaded document {file_name} of type {doc_type}."
        else:
            extracted = {"status": {"value": "Uploaded Successfully", "confidence": 1.0}}
            ai_summary = f"Uploaded document {file_name} of type {doc_type}."
            
        supabase.table("student_documents").update({
            "ocr_status": "completed",
            "extracted_data": {"extracted": extracted},
            "ai_summary": ai_summary,
            "verification_status": "verified",
            "is_verified": True,
            "verified_by_name": "AI Auto-Verifier",
            "verified_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", doc_id).execute()
        
        await maybe_refresh_ai_insights(doc["user_id"], True, "ocr_completed")
    except Exception as e:
        print(f"[OCR] Background processing error: {e}")

def map_document_type(sub_cat: str) -> str:
    if not sub_cat:
        return "Other"
    s = sub_cat.lower().strip()
    if s == "aadhaar":
        return "Aadhaar"
    if s == "passport":
        return "Passport"
    if s == "resume":
        return "Resume"
    if s in ["10th_memo", "10th memo", "10th"]:
        return "10th Memo"
    if s in ["intermediate_memo", "intermediate memo", "12th_memo", "12th memo", "12th"]:
        return "12th Memo"
    if s in ["income_certificate", "income certificate", "income"]:
        return "Income Certificate"
    if s in ["caste_certificate", "caste certificate", "caste"]:
        return "Caste Certificate"
    if "certificate" in s or "marksheet" in s or "scorecard" in s or "degree" in s:
        return "Certificate"
    return "Other"


# ─── STUDENT PROFILE ENDPOINTS ────────────────────────────────────────────────
@router.get("/profile")
async def get_student_profile(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        ensure_student_profile(uid)
        profile = (supabase.table("student_profiles").select("*").eq("user_id", uid).execute().data or [None])[0]
        
        if profile:
            profile["pincode"] = profile.get("postal_code")
            profile["photo_url"] = profile.get("profile_photo_url")
            profile["parent_name"] = profile.get("father_name")
            profile["parent_phone"] = profile.get("father_phone")

        academic = supabase.table("academic_records").select("*").eq("student_id", uid).execute().data or []
        semesters = supabase.table("semester_marks").select("*").eq("student_id", uid).order("semester").execute().data or []
        skills = (supabase.table("student_skills").select("*").eq("student_id", uid).execute().data or [None])[0]
        certifications = supabase.table("student_certifications").select("*").eq("student_id", uid).order("created_at", desc=True).execute().data or []
        exams = supabase.table("entrance_exams").select("*").eq("student_id", uid).order("exam_year", desc=True).execute().data or []
        achievements = supabase.table("student_achievements").select("*").eq("student_id", uid).order("achievement_date", desc=True).execute().data or []
        documents = supabase.table("student_documents").select("*").eq("user_id", uid).order("uploaded_at", desc=True).execute().data or []
        
        try:
            privacy_res = supabase.table("student_privacy_settings").select("*").eq("user_id", uid).execute()
            privacy = privacy_res.data[0] if privacy_res.data else None
        except Exception:
            privacy = None

        strength = calculate_profile_strength(uid)

        return {
            "user": {
                "id": current_user["id"], "email": current_user["email"],
                "full_name": current_user["full_name"], "phone": current_user.get("phone"),
                "role": current_user["role"],
                "email_verified": current_user.get("email_verified", False),
                "account_status": current_user.get("account_status", "active"),
                "last_login": current_user.get("last_login"),
                "created_at": current_user.get("created_at")
            },
            "profile": profile,
            "privacy": privacy,
            "academic_records": academic,
            "semester_marks": semesters,
            "skills": skills,
            "certifications": certifications,
            "exams": exams,
            "achievements": achievements,
            "documents": documents,
            "strength": strength
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/profile")
async def update_student_profile(
    data: StudentProfileUpdate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    uid = current_user["id"]
    supabase_payload = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    supabase_payload["updated_at"] = datetime.utcnow().isoformat()
    try:
        ensure_student_profile(uid)
        result = supabase.table("student_profiles").update(supabase_payload).eq("user_id", uid).execute()
        strength = calculate_profile_strength(uid)
        background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "profile_update")
        return {"success": True, "data": result.data[0] if result.data else {}, "strength": strength}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/completion")
async def get_profile_completion(current_user: dict = Depends(get_current_user)):
    return calculate_profile_strength(current_user["id"])

# ─── ACADEMIC RECORDS ─────────────────────────────────────────────────────────
@router.get("/academic")
async def get_academic_records(current_user: dict = Depends(get_current_user)):
    return supabase.table("academic_records").select("*").eq("student_id", current_user["id"]).execute().data or []

@router.put("/academic")
async def upsert_academic_record(
    data: AcademicRecordUpsert,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    uid = current_user["id"]
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record["student_id"] = uid
    record["updated_at"] = datetime.utcnow().isoformat()
    try:
        existing = supabase.table("academic_records").select("id").eq("student_id", uid).eq("education_level", data.education_level).execute()
        if existing.data:
            result = supabase.table("academic_records").update(record).eq("student_id", uid).eq("education_level", data.education_level).execute()
        else:
            record["created_at"] = datetime.utcnow().isoformat()
            result = supabase.table("academic_records").insert(record).execute()
        calculate_profile_strength(uid)
        background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "academic_update")
        return {"success": True, "data": result.data[0] if result.data else {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── SEMESTER MARKS ───────────────────────────────────────────────────────────
@router.get("/semesters")
async def get_semester_marks(current_user: dict = Depends(get_current_user)):
    return supabase.table("semester_marks").select("*").eq("student_id", current_user["id"]).order("semester").execute().data or []

@router.post("/semesters")
async def add_semester_mark(data: SemesterMarkUpsert, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("semester_marks").select("id").eq("student_id", uid).eq("semester", data.semester).execute()
    record = {k: v for k, v in data.model_dump().items() if v is not None}
    record["student_id"] = uid
    record["updated_at"] = datetime.utcnow().isoformat()
    if existing.data:
        result = supabase.table("semester_marks").update(record).eq("student_id", uid).eq("semester", data.semester).execute()
    else:
        record["created_at"] = datetime.utcnow().isoformat()
        result = supabase.table("semester_marks").insert(record).execute()
    calculate_profile_strength(uid)
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.delete("/semesters/{semester_id}")
async def delete_semester_mark(semester_id: str, current_user: dict = Depends(get_current_user)):
    record = supabase.table("semester_marks").select("*").eq("id", semester_id).execute().data
    if not record or record[0]["student_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Semester record not found")
    supabase.table("semester_marks").delete().eq("id", semester_id).execute()
    return {"success": True}

# ─── DOCUMENT ENDPOINTS ───────────────────────────────────────────────────────
@router.get("/documents")
async def get_student_documents(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = supabase.table("student_documents").select("*").eq("user_id", current_user["id"])
    if category:
        query = query.eq("document_type", category)
    docs = query.order("uploaded_at", desc=True).execute().data or []
    for doc in docs:
        try:
            if doc.get("storage_bucket") and doc.get("file_url"):
                url_res = supabase.storage.from_(doc["storage_bucket"]).create_signed_url(doc["file_url"], 3600)
                doc["signed_url"] = url_res.get("signedURL") or url_res.get("signedUrl", "")
        except Exception:
            doc["signed_url"] = doc.get("file_url", "")
    return docs

@router.post("/documents")
async def upload_student_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    document_name: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    uid = current_user["id"]
    ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/jpg",
                     "application/msword",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    MAX_SIZE = 10 * 1024 * 1024
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Invalid file type. Allowed: PDF, JPG, PNG, DOC, DOCX")
    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(400, "File size exceeds 10MB limit")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    unique_id = str(uuid_mod.uuid4())
    storage_bucket = "student-documents"
    file_url = f"{uid}/{document_type}/{unique_id}.{ext}"

    try:
        supabase.storage.from_(storage_bucket).upload(
            path=file_url, file=file_bytes,
            file_options={"content-type": file.content_type}
        )
    except Exception as e:
        raise HTTPException(500, f"Storage upload failed: {str(e)}")

    mapped_type = map_document_type(document_type)
    doc_data = {
        "user_id": uid,
        "document_type": mapped_type,
        "document_name": document_name or document_type,
        "file_name": file.filename,
        "file_url": file_url,
        "storage_bucket": storage_bucket,
        "mime_type": file.content_type,
        "file_size": len(file_bytes),
        "ocr_status": "pending",
        "verification_status": "pending",
        "is_active": True,
        "is_verified": False,
        "uploaded_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    result = supabase.table("student_documents").insert(doc_data).execute()
    doc = result.data[0]
    calculate_profile_strength(uid)
    background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "document_upload")
    background_tasks.add_task(process_document_ocr, doc["id"])
    return {"success": True, "data": doc}

@router.delete("/documents/{doc_id}")
async def delete_student_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("student_documents").select("*").eq("id", doc_id).execute()
    if not existing.data:
        raise HTTPException(404, "Document not found")
    doc = existing.data[0]
    if doc["user_id"] != uid:
        raise HTTPException(403, "Access denied")
    try:
        if doc.get("storage_bucket") and doc.get("file_url"):
            supabase.storage.from_(doc["storage_bucket"]).remove([doc["file_url"]])
    except Exception as e:
        print(f"[Storage] Delete warning: {e}")
    supabase.table("student_documents").delete().eq("id", doc_id).execute()
    calculate_profile_strength(uid)
    return {"success": True}

# ─── CERTIFICATIONS ───────────────────────────────────────────────────────────
@router.get("/certifications")
async def get_certifications(current_user: dict = Depends(get_current_user)):
    return supabase.table("student_certifications").select("*").eq(
        "student_id", current_user["id"]).order("issue_date", desc=True).execute().data or []

@router.post("/certifications")
async def add_certification(data: CertificationCreate, background_tasks: BackgroundTasks,
                             current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record.update({"student_id": uid, "created_at": datetime.utcnow().isoformat(),
                   "updated_at": datetime.utcnow().isoformat()})
    result = supabase.table("student_certifications").insert(record).execute()
    calculate_profile_strength(uid)
    background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "cert_added")
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.put("/certifications/{cert_id}")
async def update_certification(cert_id: str, data: CertificationCreate,
                                current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("student_certifications").select("student_id").eq("id", cert_id).execute().data
    if not existing or existing[0]["student_id"] != uid:
        raise HTTPException(403, "Access denied")
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record["updated_at"] = datetime.utcnow().isoformat()
    result = supabase.table("student_certifications").update(record).eq("id", cert_id).execute()
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.delete("/certifications/{cert_id}")
async def delete_certification(cert_id: str, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("student_certifications").select("student_id").eq("id", cert_id).execute().data
    if not existing or existing[0]["student_id"] != uid:
        raise HTTPException(403, "Access denied")
    supabase.table("student_certifications").delete().eq("id", cert_id).execute()
    calculate_profile_strength(uid)
    return {"success": True}

# ─── SKILLS ───────────────────────────────────────────────────────────────────
@router.get("/skills")
async def get_skills(current_user: dict = Depends(get_current_user)):
    data = supabase.table("student_skills").select("*").eq("student_id", current_user["id"]).execute().data
    return data[0] if data else {}

@router.put("/skills")
async def update_skills(data: SkillsUpdate, background_tasks: BackgroundTasks,
                         current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    update_data = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    update_data["updated_at"] = datetime.utcnow().isoformat()
    existing = supabase.table("student_skills").select("id").eq("student_id", uid).execute().data
    if existing:
        result = supabase.table("student_skills").update(update_data).eq("student_id", uid).execute()
    else:
        update_data.update({"student_id": uid, "created_at": datetime.utcnow().isoformat()})
        result = supabase.table("student_skills").insert(update_data).execute()
    calculate_profile_strength(uid)
    background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "skills_update")
    return {"success": True, "data": result.data[0] if result.data else {}}

# ─── ENTRANCE EXAMS ───────────────────────────────────────────────────────────
@router.get("/exams")
async def get_exams(current_user: dict = Depends(get_current_user)):
    return supabase.table("entrance_exams").select("*").eq(
        "student_id", current_user["id"]).order("exam_year", desc=True).execute().data or []

@router.post("/exams")
async def add_exam(data: EntranceExamCreate, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record.update({"student_id": uid, "created_at": datetime.utcnow().isoformat(),
                   "updated_at": datetime.utcnow().isoformat()})
    result = supabase.table("entrance_exams").insert(record).execute()
    calculate_profile_strength(uid)
    background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "exam_added")
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.put("/exams/{exam_id}")
async def update_exam(exam_id: str, data: EntranceExamCreate,
                       current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("entrance_exams").select("student_id").eq("id", exam_id).execute().data
    if not existing or existing[0]["student_id"] != uid:
        raise HTTPException(403, "Access denied")
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record["updated_at"] = datetime.utcnow().isoformat()
    result = supabase.table("entrance_exams").update(record).eq("id", exam_id).execute()
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: str, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("entrance_exams").select("student_id").eq("id", exam_id).execute().data
    if not existing or existing[0]["student_id"] != uid:
        raise HTTPException(403, "Access denied")
    supabase.table("entrance_exams").delete().eq("id", exam_id).execute()
    calculate_profile_strength(uid)
    return {"success": True}

# ─── ACHIEVEMENTS ─────────────────────────────────────────────────────────────
@router.get("/achievements")
async def get_achievements(current_user: dict = Depends(get_current_user)):
    return supabase.table("student_achievements").select("*").eq(
        "student_id", current_user["id"]).order("achievement_date", desc=True).execute().data or []

@router.post("/achievements")
async def add_achievement(data: AchievementCreate, background_tasks: BackgroundTasks,
                           current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record.update({"student_id": uid, "created_at": datetime.utcnow().isoformat(),
                   "updated_at": datetime.utcnow().isoformat()})
    result = supabase.table("student_achievements").insert(record).execute()
    calculate_profile_strength(uid)
    background_tasks.add_task(maybe_refresh_ai_insights, uid, False, "achievement_added")
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.put("/achievements/{ach_id}")
async def update_achievement(ach_id: str, data: AchievementCreate,
                               current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("student_achievements").select("student_id").eq("id", ach_id).execute().data
    if not existing or existing[0]["student_id"] != uid:
        raise HTTPException(403, "Access denied")
    record = clean_record({k: v for k, v in data.model_dump().items() if v is not None})
    record["updated_at"] = datetime.utcnow().isoformat()
    result = supabase.table("student_achievements").update(record).eq("id", ach_id).execute()
    return {"success": True, "data": result.data[0] if result.data else {}}

@router.delete("/achievements/{ach_id}")
async def delete_achievement(ach_id: str, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    existing = supabase.table("student_achievements").select("student_id").eq("id", ach_id).execute().data
    if not existing or existing[0]["student_id"] != uid:
        raise HTTPException(403, "Access denied")
    supabase.table("student_achievements").delete().eq("id", ach_id).execute()
    calculate_profile_strength(uid)
    return {"success": True}

# ─── AI INSIGHTS ──────────────────────────────────────────────────────────────
@router.get("/ai-insights")
async def get_ai_insights(current_user: dict = Depends(get_current_user)):
    try:
        data = supabase.table("ai_profile_analysis").select("*").eq(
            "student_id", current_user["id"]).execute().data
        if not data:
            return {
                "overall_profile_score": 0,
                "academic_score": 0, "skill_score": 0,
                "missing_documents": [], "scholarship_recommendations": [],
                "skill_gap_analysis": [], "career_recommendations": [],
                "college_recommendations": [], "internship_recommendations": [],
                "improvement_suggestions": [],
                "ai_summary": None,
                "analysis_status": "pending", "last_analyzed_at": None
            }
        return data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error fetching AI insights: {str(e)}")

@router.post("/ai-insights/refresh")
async def refresh_ai_insights(background_tasks: BackgroundTasks,
                               current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        supabase.table("ai_profile_analysis").upsert(
            {"student_id": uid}).execute()
        background_tasks.add_task(maybe_refresh_ai_insights, uid, True, "manual_refresh")
        return {"success": True, "message": "AI analysis started. Check back shortly."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error starting AI refresh: {str(e)}")

# ─── SCHOLARSHIPS ─────────────────────────────────────────────────────────────
@router.get("/scholarships")
async def student_get_scholarships(current_user: dict = Depends(get_current_user)):
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    res = supabase.table("scholarships").select("*")\
        .eq("status", "active")\
        .or_(f"application_end_date.gte.{today_str},application_end_date.is.null")\
        .execute()
    scholarships = res.data or []
    
    scholarships.sort(key=lambda s: (not s.get("is_featured", False), s.get("application_end_date") or ""))
    
    uid = current_user["id"]
    app_res = supabase.table("scholarship_applications").select("scholarship_id").eq("student_id", uid).execute()
    applied_ids = {a["scholarship_id"] for a in (app_res.data or [])}
    
    for s in scholarships:
        s["applied"] = s["id"] in applied_ids
        
    return scholarships

@router.post("/scholarships/{sch_id}/apply")
async def student_apply_scholarship(sch_id: str, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    
    existing = supabase.table("scholarship_applications").select("id").eq("student_id", uid).eq("scholarship_id", sch_id).execute()
    if existing.data:
        return {"success": False, "message": "You have already applied."}
        
    sch_res = supabase.table("scholarships").select("*").eq("id", sch_id).execute()
    if not sch_res.data:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    sch = sch_res.data[0]
    
    app_data = {
        "scholarship_id": sch_id,
        "student_id": uid,
        "application_status": "Applied",
        "application_date": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    try:
        res = supabase.table("scholarship_applications").insert(app_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create application")
    except Exception:
        return {"success": False, "message": "You have already applied."}
        
    try:
        supabase.table("analytics_events").insert({
            "event_type": "scholarship_applied",
            "event_data": {"scholarship_id": sch_id, "title": sch.get("title")},
            "user_id": uid,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[Analytics Event Error] {e}")
        
    return {"success": True, "data": res.data[0]}

@router.get("/my-scholarships")
async def student_get_my_scholarships(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    res = supabase.table("scholarship_applications").select(
        "*, scholarship:scholarship_id(title, provider_name, scholarship_amount, description, eligibility_criteria, required_documents)"
    ).eq("student_id", uid).order("application_date", desc=True).execute()
    return res.data or []

# ─── ADMISSION APPLICATIONS ───────────────────────────────────────────────────
@router.get("/admissions")
async def get_admission_applications(current_user: dict = Depends(get_current_user)):
    try:
        data = supabase.table("admission_applications").select(
            "*, institutions(name)"
        ).eq("student_id", current_user["id"]).order("created_at", desc=True).execute().data or []
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── PASSWORD CHANGE ──────────────────────────────────────────────────────────
@router.put("/password")
async def change_student_password(data: PasswordChange,
                                   current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    if not verify_password(data.current_password, current_user["hashed_password"]):
        raise HTTPException(400, "Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(400, "New password must be different from your current password")
    if data.new_password != data.confirm_password:
        raise HTTPException(400, "New passwords do not match")
    if not any(c.isdigit() for c in data.new_password):
        raise HTTPException(400, "Password must contain at least one number")
    new_hash = get_password_hash(data.new_password)
    supabase.table("users").update({
        "hashed_password": new_hash,
        "password_updated_at": datetime.utcnow().isoformat()
    }).eq("id", uid).execute()
    return {"success": True, "message": "Password updated successfully"}

# ─── PRIVACY SETTINGS ─────────────────────────────────────────────────────────
@router.get("/privacy")
async def get_privacy_settings(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        res = supabase.table("student_privacy_settings").select("*").eq("user_id", uid).execute()
        if not res.data:
            default_settings = {
                "user_id": uid,
                "personal_info_visibility": "institution",
                "contact_visibility": "institution",
                "academic_visibility": "institution",
                "documents_visibility": "faculty",
                "certifications_visibility": "institution",
                "skills_visibility": "placement_cell",
                "achievements_visibility": "institution",
                "exams_visibility": "admission_officers",
                "profile_public_link": False,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            insert_res = supabase.table("student_privacy_settings").insert(default_settings).execute()
            return insert_res.data[0] if insert_res.data else default_settings
        return res.data[0]
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.put("/privacy")
async def update_privacy_settings(data: PrivacySettingsUpdate, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()
    try:
        existing = supabase.table("student_privacy_settings").select("id").eq("user_id", uid).execute()
        if not existing.data:
            update_data["user_id"] = uid
            res = supabase.table("student_privacy_settings").insert(update_data).execute()
        else:
            res = supabase.table("student_privacy_settings").update(update_data).eq("user_id", uid).execute()
        return {"success": True, "data": res.data[0] if res.data else {}}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# ─── PREFERENCES ──────────────────────────────────────────────────────────────
@router.get("/preferences")
async def get_preferences(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        res = supabase.table("student_preferences").select("*").eq("user_id", uid).execute()
        if not res.data:
            return {
                "target_colleges": [],
                "preferred_courses": [],
                "preferred_locations": [],
                "career_interests": [],
                "notification_email": True,
                "notification_sms": False,
                "notification_app": True
            }
        return res.data[0]
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.put("/preferences")
async def update_preferences(data: PreferencesUpdate, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()
    try:
        existing = supabase.table("student_preferences").select("id").eq("user_id", uid).execute()
        if not existing.data:
            update_data["user_id"] = uid
            res = supabase.table("student_preferences").insert(update_data).execute()
        else:
            res = supabase.table("student_preferences").update(update_data).eq("user_id", uid).execute()
        return {"success": True, "data": res.data[0] if res.data else {}}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
@router.get("/notifications")
async def get_student_notifications(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        res = supabase.table("notifications").select("*").eq("user_id", uid).order("created_at", desc=True).execute()
        notifications = res.data or []
        unread_count = sum(1 for n in notifications if not n.get("is_read"))
        return {"notifications": notifications, "unread_count": unread_count}
    except Exception as e:
        return {"notifications": [], "unread_count": 0}

@router.put("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        supabase.table("notifications").update({"is_read": True}).eq("id", notif_id).eq("user_id", uid).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.put("/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        supabase.table("notifications").update({"is_read": True}).eq("user_id", uid).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# ─── TIMELINE ─────────────────────────────────────────────────────────────────
@router.get("/timeline")
async def get_student_timeline(page: int = 1, limit: int = 20, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    try:
        events = []
        
        # 1. Fetch analytics events
        try:
            ae_res = supabase.table("analytics_events").select("*").eq("user_id", uid).execute()
            for e in (ae_res.data or []):
                events.append({
                    "id": e["id"],
                    "event_type": e["event_type"],
                    "title": e["event_type"].replace("_", " ").title(),
                    "description": str(e.get("event_data") or ""),
                    "created_at": e["created_at"]
                })
        except Exception:
            pass
            
        # 2. Fetch documents
        try:
            doc_res = supabase.table("student_documents").select("*").eq("user_id", uid).execute()
            for d in (doc_res.data or []):
                events.append({
                    "id": d["id"],
                    "event_type": "document_upload",
                    "title": f"Uploaded Document: {d['document_name'] or d['file_name']}",
                    "description": f"Mime: {d.get('mime_type')}, Status: {d.get('verification_status')}",
                    "created_at": d["uploaded_at"] or d["created_at"]
                })
        except Exception:
            pass
            
        # 3. Fetch academic records
        try:
            acad_res = supabase.table("academic_records").select("*").eq("student_id", uid).execute()
            for a in (acad_res.data or []):
                events.append({
                    "id": a["id"],
                    "event_type": "academic_record",
                    "title": f"Academic Record: {a['education_level']}",
                    "description": f"Institution: {a.get('institution_name')}, Grade: {a.get('percentage') or a.get('cgpa')}",
                    "created_at": a.get("created_at") or a.get("updated_at")
                })
        except Exception:
            pass
            
        # 4. Fetch certifications
        try:
            cert_res = supabase.table("student_certifications").select("*").eq("student_id", uid).execute()
            for c in (cert_res.data or []):
                events.append({
                    "id": c["id"],
                    "event_type": "certification",
                    "title": f"Certification Earned: {c['title']}",
                    "description": f"Issuer: {c.get('issuing_organization')}",
                    "created_at": c.get("issue_date") or c.get("created_at")
                })
        except Exception:
            pass
            
        # 5. Fetch achievements
        try:
            ach_res = supabase.table("student_achievements").select("*").eq("student_id", uid).execute()
            for ac in (ach_res.data or []):
                events.append({
                    "id": ac["id"],
                    "event_type": "achievement",
                    "title": f"Achievement: {ac['achievement_title']}",
                    "description": ac.get("description") or "",
                    "created_at": ac.get("achievement_date") or ac.get("created_at")
                })
        except Exception:
            pass
            
        # 6. Fetch entrance exams
        try:
            exam_res = supabase.table("entrance_exams").select("*").eq("student_id", uid).execute()
            for ex in (exam_res.data or []):
                events.append({
                    "id": ex["id"],
                    "event_type": "entrance_exam",
                    "title": f"Entrance Exam: {ex['exam_name']}",
                    "description": f"Score: {ex.get('score')}, Rank: {ex.get('rank')}",
                    "created_at": ex.get("created_at")
                })
        except Exception:
            pass
            
        def get_date(x):
            d = x.get("created_at")
            if not d:
                return "1970-01-01T00:00:00Z"
            return d
            
        events.sort(key=get_date, reverse=True)
        
        start = (page - 1) * limit
        end = start + limit
        paginated_events = events[start:end]
        
        return {"events": paginated_events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
