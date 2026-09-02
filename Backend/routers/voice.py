import os
import json
import time
import base64
import math
import tempfile
import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any
import numpy as np
import httpx
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from database import supabase
from auth_utils import get_current_user
from guidance_engine import guidance_engine
from agent_orchestrator import (
    agent_config, 
    AgentToneConfig, 
    get_agent_preset, 
    update_agent_config,
    AGENT_PRESETS,
)
from fastrtc_handler import create_fastrtc_stream, launch_fastphone, cleanup_all_sessions
import config
from routers.calls import broadcast_call_status

router = APIRouter(prefix="", tags=["voice"])

class TTSRequest(BaseModel):
    text: str

class AgentConfigUpdate(BaseModel):
    preset: Optional[str] = None
    temperature: Optional[float] = None
    speech_pace: Optional[float] = None
    tts_voice: Optional[str] = None
    system_prompt: Optional[str] = None
    can_interrupt: Optional[bool] = None

class FastPhoneRequest(BaseModel):
    huggingface_token: Optional[str] = None

_fastrtc_stream = None

def get_fastrtc_stream():
    """Lazy initialization of FastRTC stream"""
    global _fastrtc_stream
    if _fastrtc_stream is None and config.FASTRTC_AVAILABLE:
        _fastrtc_stream = create_fastrtc_stream(
            guidance_engine,
            agent_config
        )
    return _fastrtc_stream

# ─── FALSE POSITIVE FILTER ──────────────────────────────────────────────────
FALSE_POSITIVE_WORDS = {
    '.', '..', '...', '....', '.....',
    'thank you', 'thanks', 'thank', 'thx',
    'gracias', 'merci', 'danke', 'arigato', 'shukran',
    'amen', 'hallelujah', 'praise', 'lord',
    'okay', 'ok', 'k', 'kk', 'okie', 'okie dokie',
    'hmm', 'hm', 'hmmm', 'uh', 'uhh', 'um', 'umm', 'ah', 'ahh', 'oh', 'ohh', 'eh',
    'yeah', 'yea', 'yep', 'yup', 'yes', 'yess', 'no', 'nope', 'nah',
    'right', 'alright', 'aight', 'ight',
    'hello', 'hi', 'hey', 'heya', 'hiya', 'yo',
    'what', 'when', 'where', 'who', 'how', 'why',
    'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall',
    'can', "can't", 'cant', 'dont', "don't", 'wont', "won't",
    'isnt', "isn't", 'arent', "aren't", 'wasnt', "wasn't",
    'werent', "weren't", 'hasnt', "hasn't", 'havent', "haven't",
    'hadnt', "hadn't", 'doesnt', "doesn't", 'didnt', "didn't",
    'wouldnt', "wouldn't", 'shouldnt', "shouldn't", 'couldnt', "couldn't",
    'mustnt', "mustn't", 'shant', "shan't", 'mightnt', "mightn't",
    'neednt', "needn't", 'darent', "daren't", 'oughtnt', "oughtn't",
    'aint', "ain't", 'gonna', 'wanna', 'gotta',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
    'up', 'about', 'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'between', 'among', 'within', 'without',
    'against', 'under', 'over', 'again', 'further', 'then', 'once',
    'here', 'there', 'everywhere', 'anywhere', 'somewhere', 'nowhere',
    'this', 'that', 'these', 'those', 'such', 'same', 'other',
    'another', 'each', 'every', 'all', 'both', 'few', 'more', 'most',
    'some', 'any', 'none', 'neither', 'either',
    'much', 'many', 'little', 'less', 'least', 'fewer', 'fewest',
    'enough', 'quite', 'rather', 'very', 'too', 'so', 'just', 'only',
    'even', 'also', 'as', 'than', 'like', 'unlike', 'despite',
    'although', 'though', 'while', 'whereas', 'unless', 'until',
    'since', 'because', 'once', 'when', 'whenever',
    'where', 'wherever', 'if', 'whether', 'either', 'or', 'nor', 'not',
    'both', 'and', 'but', 'yet', 'still', 'however',
    'therefore', 'thus', 'hence', 'consequently', 'accordingly',
    'meanwhile', 'otherwise', 'instead', 'besides', 'furthermore',
    'moreover', 'nevertheless', 'nonetheless', 'notwithstanding',
    'm', 're', 's', 'll', 'd', 've', 't',
    'good', 'great', 'nice', 'cool', 'awesome', 'amazing', 'wow',
    'please', 'pls', 'plz', 'sorry', 'excuse', 'pardon',
    'bye', 'goodbye', 'see', 'later', 'cya', 'ttyl',
    'lol', 'lmao', 'rofl', 'omg', 'wtf', 'haha', 'hehe',
    'stop', 'wait', 'hold', 'pause', 'continue', 'go', 'proceed',
    'next', 'previous', 'back', 'forward', 'up', 'down', 'left', 'right',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'first', 'second', 'third', 'last', 'final',
    'new', 'old', 'young', 'big', 'small', 'large', 'tiny', 'huge',
    'good', 'bad', 'better', 'best', 'worse', 'worst',
    'happy', 'sad', 'angry', 'mad', 'glad', 'upset',
    'today', 'tomorrow', 'yesterday', 'now', 'then', 'soon', 'later',
    'morning', 'afternoon', 'evening', 'night', 'day', 'time',
    'man', 'woman', 'boy', 'girl', 'guy', 'dude', 'bro', 'sis',
    'sir', 'maam', 'madam', 'miss', 'mister', 'mr', 'mrs', 'ms', 'dr',
    'yes sir', 'yes maam', 'no sir', 'no maam',
    'i see', 'i know', 'i think', 'i guess', 'i suppose',
    'you know', 'you see', 'i mean', 'like', 'literally',
    'actually', 'basically', 'seriously', 'honestly', 'frankly',
    'probably', 'maybe', 'perhaps', 'possibly', 'likely', 'definitely',
    'absolutely', 'certainly', 'surely', 'obviously', 'clearly',
    'apparently', 'supposedly', 'reportedly', 'allegedly',
    'well', 'so', 'then', 'now', 'anyway', 'anyways', 'whatever',
    'fine', 'whatever', 'alright', 'okay then', 'ok then',
    'got it', 'gotcha', 'understood', 'roger', 'copy', 'affirmative',
    'negative', 'correct', 'incorrect', 'true', 'false',
    'exactly', 'precisely', 'indeed', 'certainly', 'definitely',
    'totally', 'completely', 'absolutely', 'entirely', 'fully',
    'partially', 'somewhat', 'kinda', 'sorta', 'sort of', 'kind of',
    'more or less', 'pretty much', 'pretty well', 'pretty good',
    'not bad', 'not good', 'not sure', 'not really', 'not exactly',
    'i dont know', 'idk', 'dunno', 'no idea', 'beats me',
    'who knows', 'god knows', 'heaven knows',
    'tell me', 'show me', 'help me', 'assist me',
    'repeat', 'again', 'say again', 'come again', 'pardon me',
    'what was that', 'what did you say', 'i didnt catch that',
    'speak up', 'louder', 'quieter', 'slower', 'faster',
    'one more time', 'one more', 'once more', 'one again',
}

def is_valid_transcription(text: str) -> bool:
    """Filter out noise, silence markers, and false transcriptions"""
    if not text:
        return False

    text_stripped = text.strip()
    if len(text_stripped) < 3:
        return False

    if all(c in '.,;:!?-…\'"()[]{}' for c in text_stripped):
        return False

    text_lower = text_stripped.lower().replace('\n', ' ').strip()
    if text_lower in FALSE_POSITIVE_WORDS:
        return False

    words = text_lower.split()
    if len(words) == 1 and words[0] in FALSE_POSITIVE_WORDS:
        return False

    if len(set(text_stripped)) <= 2 and len(text_stripped) > 2:
        return False

    alpha_count = sum(1 for c in text_stripped if c.isalpha())
    if alpha_count < 2:
        return False

    return True

# ─── AUDIO UTILITIES ────────────────────────────────────────────────────────
def ensure_16bit_aligned(audio_bytes: bytes) -> bytes:
    """Ensure audio bytes are aligned to 16-bit samples (even length)"""
    if len(audio_bytes) % 2 != 0:
        return audio_bytes[:-1]
    return audio_bytes

def strip_wav_header(audio_bytes: bytes) -> bytes:
    """Remove WAV RIFF header if present, return raw PCM"""
    if len(audio_bytes) < 12:
        return audio_bytes
    if audio_bytes[:4] == b'RIFF' and audio_bytes[8:12] == b'WAVE':
        idx = audio_bytes.find(b'data', 12)
        if idx > 0 and idx + 8 <= len(audio_bytes):
            return audio_bytes[idx + 8:]
    return audio_bytes

def add_wav_header(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    import struct
    header = bytearray(44)
    struct.pack_into('<4s', header, 0, b'RIFF')
    struct.pack_into('<I', header, 4, 36 + len(pcm_data))
    struct.pack_into('<4s', header, 8, b'WAVE')
    struct.pack_into('<4s', header, 12, b'fmt ')
    struct.pack_into('<I', header, 16, 16)
    struct.pack_into('<H', header, 20, 1)
    struct.pack_into('<H', header, 22, 1)
    struct.pack_into('<I', header, 24, sample_rate)
    struct.pack_into('<I', header, 28, sample_rate * 2)
    struct.pack_into('<H', header, 32, 2)
    struct.pack_into('<H', header, 34, 16)
    struct.pack_into('<4s', header, 36, b'data')
    struct.pack_into('<I', header, 40, len(pcm_data))
    return bytes(header) + pcm_data

def pcm_rms(pcm_data: bytes) -> float:
    """Calculate the Root Mean Square (RMS) of raw 16-bit PCM audio data"""
    if not pcm_data:
        return 0.0
    audio_array = np.frombuffer(pcm_data, dtype=np.int16)
    if len(audio_array) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio_array.astype(np.float64)**2)))

# ─── AUDIO UTILITIES FOR TELEPHONY ──────────────────────────────────────────
def _make_mulaw_table():
    table = []
    for i in range(256):
        val = ~i & 0xFF
        sign = 1 if (val & 0x80) else -1
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F
        sample = sign * ((1 << exponent) * (mantissa * 2 + 33) - 33)
        table.append(sample)
    return table

MULAW_TABLE = _make_mulaw_table()

def mulaw_rms(mulaw_data: bytes) -> float:
    if not mulaw_data:
        return 0.0
    sqsum = 0.0
    for b in mulaw_data:
        val = MULAW_TABLE[b]
        sqsum += val * val
    return math.sqrt(sqsum / len(mulaw_data))

def pcm_24k_to_mulaw_8k(pcm_data: bytes) -> bytes:
    import audioop
    resampled, _ = audioop.ratecv(pcm_data, 2, 1, 24000, 8000, None)
    mulaw_data = audioop.lin2ulaw(resampled, 2)
    return mulaw_data

def mulaw_8k_to_pcm_16k(mulaw_bytes: bytes) -> bytes:
    import audioop
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
    return pcm_16k

async def stream_audio_to_twilio(websocket: WebSocket, stream_sid: str, mulaw_data: bytes, state: dict):
    chunk_size = 160
    delay = 0.02
    state["abort_playback"] = False
    for i in range(0, len(mulaw_data), chunk_size):
        if state.get("abort_playback"):
            print("Playback aborted")
            break
        chunk = mulaw_data[i:i+chunk_size]
        payload = base64.b64encode(chunk).decode('utf-8')
        message = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload}
        }
        try:
            await websocket.send_json(message)
        except Exception:
            break
        await asyncio.sleep(delay)

async def broadcast_monitor_message(call_id: str, message: dict):
    if call_id in config.active_monitors:
        disconnected = []
        for ws in config.active_monitors[call_id]:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            try:
                config.active_monitors[call_id].remove(ws)
            except ValueError:
                pass

async def generate_and_send_greeting(websocket: WebSocket, call_id: str, stream_sid: str, system_prompt: str, student_name: str, student_details: dict, state: dict):
    state["is_ai_speaking"] = True
    await broadcast_monitor_message(call_id, {"type": "status", "status": "thinking"})
    
    greeting_text = "Hello! I am your AI career assistant. How can I help you today?"
    if config.groq_client:
        try:
            start = time.time()
            print("Generating greeting with Groq...")
            prompt = system_prompt + f"\n\nStudent's name is {student_name}. Write a short, welcoming phone greeting (1-2 sentences max) to start the call. Do not output anything other than the greeting text."
            response = config.groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "system", "content": prompt}],
                max_tokens=60,
                temperature=0.7
            )
            print(f"Groq greeting generated in {time.time()-start:.2f} sec")
            greeting_text = response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            print(f"Greeting gen failed: {e}")
            
    print(f"Greeting: {greeting_text}")
    
    conversation = guidance_engine.get_conversation(call_id)
    conversation[0] = {"role": "system", "content": system_prompt}
    conversation.append({"role": "assistant", "content": greeting_text})
    
    await broadcast_monitor_message(call_id, {"type": "transcript", "role": "Agent", "text": greeting_text})
    await broadcast_monitor_message(call_id, {"type": "status", "status": "ai_speaking"})
    
    start = time.time()
    audio_bytes = await guidance_engine.text_to_speech(greeting_text)
    print(f"Greeting TTS took {time.time()-start:.2f} sec")

    if audio_bytes:
        pcm_data = strip_wav_header(audio_bytes)
        pcm_data = ensure_16bit_aligned(pcm_data)
        mulaw_data = pcm_24k_to_mulaw_8k(pcm_data)
        await stream_audio_to_twilio(websocket, stream_sid, mulaw_data, state)
        
    state["is_ai_speaking"] = False
    await broadcast_monitor_message(call_id, {"type": "status", "status": "listening"})

async def generate_post_call_summary(call_id: str):
    conversation = guidance_engine.get_conversation(call_id)
    transcript_lines = []
    for msg in conversation:
        if msg["role"] == "user":
            transcript_lines.append(f"Student: {msg['content']}")
        elif msg["role"] == "assistant":
            transcript_lines.append(f"AI: {msg['content']}")
            
    transcript_text = "\n".join(transcript_lines)
    summary = "No conversation took place."
    sentiment = "neutral"
    outcome = "No answer or disconnected immediately."
    interested = "Not Interested"
    follow_up = False
    
    if transcript_lines and config.groq_client:
        try:
            analysis_prompt = f"""You are an AI analyst. Analyze the following conversation between an AI Career Counselor and a student.

Conversation Transcript:
{transcript_text}

Provide your analysis in a valid JSON format with the following keys:
- "summary": A brief summary of the conversation.
- "sentiment": Overall sentiment (positive, neutral, negative).
- "outcome": Outcome of the call.
- "interested": "Interested" or "Not Interested" based on the student's responses.
- "follow_up": true or false (boolean, indicating if a follow-up call/action is required).

Output ONLY the JSON object. Do not include any markdown styling, code blocks, or explanatory text."""
            response = config.groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "user", "content": analysis_prompt}],
                max_tokens=500,
                temperature=0.3
            )
            analysis_json_str = response.choices[0].message.content.strip()
            import re
            match = re.search(r'\{.*\}', analysis_json_str, re.DOTALL)
            if match:
                analysis_json_str = match.group(0)
            analysis_data = json.loads(analysis_json_str)
            summary = analysis_data.get("summary") or summary
            sentiment = analysis_data.get("sentiment") or sentiment
            outcome = analysis_data.get("outcome") or outcome
            interested = analysis_data.get("interested") or interested
            follow_up = bool(analysis_data.get("follow_up"))
        except Exception as e:
            print(f"Post call analysis failed: {e}")
            
    transcript_payload = {
        "transcript": transcript_text,
        "summary": summary,
        "sentiment": sentiment,
        "outcome": outcome,
        "interested": interested,
        "follow_up_required": follow_up
    }
    
    try:
        supabase.table("calls").update({
            "status": "completed",
            "ended_at": datetime.utcnow().isoformat(),
            "sentiment": sentiment,
            "transcript": json.dumps(transcript_payload)
        }).eq("id", call_id).execute()
    except Exception as e:
        print(f"Failed to update calls DB: {e}")

# ─── WEBSOCKET VOICE HANDLER ────────────────────────────────────────────────
@router.websocket("/ws/voice/{session_id}")
async def websocket_voice(websocket: WebSocket, session_id: str):
    print(f"VOICE WEBSOCKET CONNECTED - Session: {session_id}")
    await websocket.accept()
    print(f"WebSocket connected: {session_id}")

    is_twilio = False
    call_id = session_id
    call = None
    student_name = "Student"
    student_details = {}
    system_prompt = config.CAREER_SYSTEM_PROMPT
    stream_sid = None

    try:
        call_res = supabase.table("calls").select("*, ai_agents(*)").eq("id", call_id).execute()
        if call_res.data:
            call = call_res.data[0]
            is_twilio = True
            agent = call.get("ai_agents")
            if isinstance(agent, list) and agent:
                agent = agent[0]
            if isinstance(agent, dict):
                system_prompt = agent.get("system_prompt") or config.CAREER_SYSTEM_PROMPT
            
            if call.get("user_id"):
                user_res = supabase.table("users").select("*").eq("id", call["user_id"]).execute()
                if user_res.data:
                    student_name = user_res.data[0].get("full_name") or "Student"
                    profile_res = supabase.table("student_profiles").select("*").eq("user_id", call["user_id"]).execute()
                    if profile_res.data:
                        p_data = profile_res.data[0]
                        student_details = {
                            "interested_course": p_data.get("interested_course") or "Not Specified",
                            "application_status": p_data.get("application_status") or "Not Applied",
                            "lead_status": p_data.get("lead_status") or "New"
                        }
    except Exception as e:
        print(f"Error reading call meta: {e}")

    # Set system prompt
    conversation = guidance_engine.get_conversation(session_id)
    pers_prompt = f"\n\nStudent Information:\n- Name: {student_name}\n- Phone: {call.get('phone_number') if call else 'Unknown'}\n- Interested Course: {student_details.get('interested_course')}\n- Application Status: {student_details.get('application_status')}\n- Lead Status: {student_details.get('lead_status')}\n\nUse these details naturally to personalize your conversation. Keep responses short and conversational, suitable for a phone call."
    conversation[0] = {"role": "system", "content": system_prompt + pers_prompt}

    state = {
        "is_ai_speaking": False,
        "is_user_speaking": False,
        "pending_audio_buffer": bytearray(),
        "silence_duration_ms": 0,
        "abort_playback": False,
    }

    # If browser, send default greeting
    if not is_twilio:
        greeting = "Hello! I am your CareerGuide AI. Ask me anything about colleges, courses, or careers!"
        try:
            await websocket.send_json({"type": "ai_response", "text": greeting})
            if config.ELEVENLABS_API_KEY or config.DEEPGRAM_API_KEY:
                audio_bytes = await guidance_engine.text_to_speech(greeting)
                if audio_bytes:
                    pcm_data = strip_wav_header(audio_bytes)
                    pcm_data = ensure_16bit_aligned(pcm_data)
                    audio_b64 = base64.b64encode(pcm_data).decode('utf-8')
                    await websocket.send_json({"type": "audio", "data": audio_b64})
        except Exception as e:
            print(f"Browser greeting failed: {e}")

    audio_buffer = bytearray()
    RMS_THRESHOLD = 600
    SILENCE_THRESHOLD_MS = 1200
    consecutive_loud_chunks = 0
    is_connected = True

    try:
        while is_connected:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                is_connected = False
                break
            except Exception:
                is_connected = False
                break

            if "bytes" in message:
                # Browser mode binary bytes (PCM 16k mono 16-bit)
                data = message["bytes"]
                rms = pcm_rms(data)

                if rms >= RMS_THRESHOLD:
                    if state["is_ai_speaking"]:
                        consecutive_loud_chunks += 1
                        if consecutive_loud_chunks >= 3: # ~150ms of talking
                            state["abort_playback"] = True
                    else:
                        consecutive_loud_chunks = 0

                    audio_buffer.extend(data)
                    if not state["is_user_speaking"]:
                        state["is_user_speaking"] = True
                    state["silence_duration_ms"] = 0
                else:
                    if state["is_user_speaking"]:
                        # Calculate duration of this chunk of silence
                        # 16kHz 16-bit mono PCM is 32000 bytes per second
                        chunk_duration_ms = (len(data) / 32000.0) * 1000.0
                        state["silence_duration_ms"] += chunk_duration_ms
                        
                        if state["silence_duration_ms"] >= SILENCE_THRESHOLD_MS:
                            state["is_user_speaking"] = False
                            state["silence_duration_ms"] = 0
                            
                            # Process the speech buffer
                            if len(audio_buffer) >= 16000:
                                asyncio.create_task(process_audio_buffer(
                                    websocket, session_id, bytes(audio_buffer), state, is_twilio, stream_sid
                                ))
                            audio_buffer = bytearray()
                    
            elif "text" in message:
                try:
                    text_data = json.loads(message["text"])
                    if is_twilio:
                        event = text_data.get("event")
                        if event == "start":
                            stream_sid = text_data.get("streamSid")
                            await broadcast_call_status(call_id, "answered")
                            asyncio.create_task(generate_and_send_greeting(
                                websocket, call_id, stream_sid, system_prompt, student_name, student_details, state
                            ))
                        elif event == "media":
                            payload = text_data["media"]["payload"]
                            chunk_bytes = base64.b64decode(payload)
                            rms = mulaw_rms(chunk_bytes)
                            
                            if rms >= RMS_THRESHOLD:
                                if state["is_ai_speaking"]:
                                    consecutive_loud_chunks += 1
                                    if consecutive_loud_chunks >= 5: # 100ms
                                        state["abort_playback"] = True
                                else:
                                    consecutive_loud_chunks = 0
                                    
                                audio_buffer.extend(chunk_bytes)
                                if not state["is_user_speaking"]:
                                    state["is_user_speaking"] = True
                                    await broadcast_monitor_message(call_id, {"type": "status", "status": "student_speaking"})
                                state["silence_duration_ms"] = 0
                            else:
                                if state["is_user_speaking"]:
                                    state["silence_duration_ms"] += 20
                                    if state["silence_duration_ms"] >= SILENCE_THRESHOLD_MS:
                                        state["is_user_speaking"] = False
                                        state["silence_duration_ms"] = 0
                                        pcm_data = mulaw_8k_to_pcm_16k(bytes(audio_buffer))
                                        print(f"PCM bytes: {len(pcm_data)}")
                                        audio_buffer = bytearray()
                                        if len(pcm_data) >= 16000:
                                            asyncio.create_task(process_audio_buffer(
                                                websocket, session_id, pcm_data, state, is_twilio, stream_sid
                                            ))
                    else:
                        if text_data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                except Exception:
                    pass

    except Exception as e:
        print(f"WS voice error: {e}")
    finally:
        print(f"Voice session ended: {session_id}")
        if is_twilio:
            await broadcast_call_status(call_id, "completed")
            await generate_post_call_summary(call_id)

async def process_audio_buffer(websocket: WebSocket, session_id: str, 
                                audio_bytes: bytes, state: dict, is_twilio: bool = False, stream_sid: str = None):
    if state["is_ai_speaking"]:
        return

    if len(audio_bytes) < 16000:
        return

    if is_twilio:
        await broadcast_monitor_message(session_id, {"type": "status", "status": "thinking"})

    start = time.time()
    print(f"Received audio: {len(audio_bytes)} bytes")
    print("Transcribing...")
    transcript = await guidance_engine.transcribe_audio(audio_bytes)
    print(f"Transcript: {transcript}")
    print(f"Transcription took {time.time()-start:.2f} sec")

    if not transcript or not transcript.strip() or not is_valid_transcription(transcript):
        if is_twilio:
            await broadcast_monitor_message(session_id, {"type": "status", "status": "listening"})
        return

    print(f"User: '{transcript}'")
    
    if is_twilio:
        await broadcast_monitor_message(session_id, {"type": "transcript", "role": "Student", "text": transcript})

    state["is_ai_speaking"] = True
    if is_twilio:
        await broadcast_monitor_message(session_id, {"type": "status", "status": "thinking"})
    else:
        # Send live user transcript to browser client
        await websocket.send_json({"type": "transcript", "text": transcript})

    try:
        start = time.time()
        ai_response = await guidance_engine.process_text(transcript, session_id)
        print(f"LLM took {time.time()-start:.2f} sec")
        print(f"AI: {ai_response}")
        
        if is_twilio:
            await broadcast_monitor_message(session_id, {"type": "transcript", "role": "Agent", "text": ai_response})
            await broadcast_monitor_message(session_id, {"type": "status", "status": "ai_speaking"})
        else:
            await websocket.send_json({"type": "ai_response", "text": ai_response})

        start = time.time()

        audio_bytes_tts = await guidance_engine.text_to_speech(ai_response)

        print(f"Reply TTS took {time.time()-start:.2f} sec")
        
        if audio_bytes_tts:
            pcm_data = strip_wav_header(audio_bytes_tts)
            pcm_data = ensure_16bit_aligned(pcm_data)

            if is_twilio and stream_sid:
                mulaw_data = pcm_24k_to_mulaw_8k(pcm_data)
                await stream_audio_to_twilio(websocket, stream_sid, mulaw_data, state)
            elif not is_twilio:
                audio_b64 = base64.b64encode(pcm_data).decode('utf-8')
                await websocket.send_json({"type": "audio", "data": audio_b64})
    except Exception as e:
        print(f"Error in process_audio_buffer: {e}")
    finally:
        state["is_ai_speaking"] = False
        if is_twilio:
            await broadcast_monitor_message(session_id, {"type": "status", "status": "listening"})

@router.websocket("/ws/calls/monitor/{call_id}")
async def websocket_call_monitor(websocket: WebSocket, call_id: str):
    await websocket.accept()
    if call_id not in config.active_monitors:
        config.active_monitors[call_id] = []
    config.active_monitors[call_id].append(websocket)
    print(f"Monitor connected to call {call_id}")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        print(f"Monitor disconnected from call {call_id}")
    finally:
        if call_id in config.active_monitors and websocket in config.active_monitors[call_id]:
            config.active_monitors[call_id].remove(websocket)

# ─── CHAT ENDPOINT ──────────────────────────────────────────────────────────
@router.post("/api/chat")
async def text_chat(message: Dict[str, str], current_user: dict = Depends(get_current_user)):
    session_id = message.get("session_id", f"session_{datetime.utcnow().timestamp()}")
    user_message = message.get("message", "")

    ai_response = await guidance_engine.process_text(user_message, session_id)

    return {
        "session_id": session_id,
        "response": ai_response,
        "timestamp": datetime.utcnow().isoformat()
    }

# ─── VOICE CONFIG & STATUS ──────────────────────────────────────────────────
@router.post("/api/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)):
    """Transcribe user audio using Deepgram, fallback to Groq Whisper"""
    audio_bytes = await file.read()
    
    if config.DEEPGRAM_API_KEY:
        try:
            url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
            headers = {
                "Authorization": f"Token {config.DEEPGRAM_API_KEY}",
                "Content-Type": file.content_type or "audio/webm"
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, content=audio_bytes, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
                    if transcript:
                        return {"text": transcript}
                else:
                    print(f"Deepgram STT error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Deepgram STT failed: {e}")
            
    # Fallback to Groq Whisper
    try:
        tmp_path = tempfile.mktemp(suffix=".webm")
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        try:
            with open(tmp_path, "rb") as f:
                transcript = config.groq_client.audio.transcriptions.create(
                    file=("audio.webm", f),
                    model="whisper-large-v3-turbo",
                    response_format="text"
                )
            return {"text": str(transcript) if transcript else ""}
        except Exception as groq_err:
            print(f"Groq transcription error: {groq_err}")
            return {"text": ""}
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    except Exception as e:
        print(f"Groq transcription fallback failed: {e}")
        return {"text": ""}

@router.post("/api/voice/tts")
async def voice_tts(request: TTSRequest):
    """Convert text to speech using ElevenLabs, fallback to Deepgram"""
    audio_bytes = b""
    is_mp3 = False
    
    if config.ELEVENLABS_API_KEY:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL/stream"
            headers = {
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "text": request.text,
                "model_id": "eleven_turbo_v2_5",
                "output_format": "mp3_44100_128"
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60)
                if response.status_code == 200:
                    audio_bytes = response.content
                    is_mp3 = True
        except Exception as e:
            print(f"ElevenLabs TTS failed: {e}")
            
    if not audio_bytes:
        try:
            pcm_bytes = await guidance_engine.text_to_speech(request.text)
            if pcm_bytes:
                audio_bytes = add_wav_header(pcm_bytes, 24000)
        except Exception as e:
            print(f"Fallback TTS failed: {e}")
            
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate speech audio")
        
    media_type = "audio/mpeg" if is_mp3 else "audio/wav"
    return Response(content=audio_bytes, media_type=media_type)

@router.get("/api/voice/agent-config")
async def get_agent_config(current_user: dict = Depends(get_current_user)):
    """Get current agent configuration"""
    return {
        "current": {
            "temperature": agent_config.temperature,
            "speech_pace": agent_config.speech_pace,
            "tts_voice": agent_config.tts_voice,
            "can_interrupt": agent_config.can_interrupt,
            "vad_speech_threshold": agent_config.vad_speech_threshold,
        },
        "available_presets": list(AGENT_PRESETS.keys()),
        "available_voices": ["Celeste-PlayAI", "Atlas-PlayAI"],
    }

@router.post("/api/voice/agent-config")
async def update_agent_config_endpoint(
    data: AgentConfigUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update agent tone, temperature, pace, or voice"""
    if current_user["role"] not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Admin/Faculty access required")

    updates = {}
    if data.preset and data.preset in AGENT_PRESETS:
        preset = AGENT_PRESETS[data.preset]
        updates = {
            "temperature": preset.temperature,
            "speech_pace": preset.speech_pace,
            "system_prompt": preset.system_prompt,
            "tts_voice": preset.tts_voice,
        }

    if data.temperature is not None:
        updates["temperature"] = max(0.0, min(2.0, data.temperature))
    if data.speech_pace is not None:
        updates["speech_pace"] = max(0.5, min(2.0, data.speech_pace))
    if data.tts_voice is not None:
        updates["tts_voice"] = data.tts_voice
    if data.system_prompt is not None:
        updates["system_prompt"] = data.system_prompt
    if data.can_interrupt is not None:
        updates["can_interrupt"] = data.can_interrupt

    update_agent_config(**updates)

    return {
        "success": True,
        "config": {
            "temperature": agent_config.temperature,
            "speech_pace": agent_config.speech_pace,
            "tts_voice": agent_config.tts_voice,
            "can_interrupt": agent_config.can_interrupt,
        }
    }

@router.get("/api/voice/fastrtc-status")
async def fastrtc_status_endpoint():
    """Check if FastRTC primary layer is available"""
    stream = get_fastrtc_stream()
    return {
        "available": config.FASTRTC_AVAILABLE,
        "stream_ready": stream is not None,
        "primary_path": "fastrtc" if config.FASTRTC_AVAILABLE else "manual_websocket",
        "features": {
            "vad": config.FASTRTC_AVAILABLE,
            "barge_in": config.FASTRTC_AVAILABLE and agent_config.can_interrupt,
            "turn_taking": config.FASTRTC_AVAILABLE,
            "fastphone": config.FASTRTC_AVAILABLE,
        },
        "agent_config": {
            "temperature": agent_config.temperature,
            "speech_pace": agent_config.speech_pace,
            "tts_voice": agent_config.tts_voice,
        }
    }

@router.post("/api/voice/fastphone")
async def launch_fastphone_endpoint(
    data: FastPhoneRequest,
    current_user: dict = Depends(get_current_user)
):
    """Launch FastPhone — get a free temporary phone number for testing."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not config.FASTRTC_AVAILABLE:
        raise HTTPException(status_code=503, detail="fastrtc not installed")

    try:
        import threading
        hf_token = data.huggingface_token or os.getenv("HUGGINGFACE_FASTRTC_PHONE_CALL_TOKEN")

        def run_fastphone():
            launch_fastphone(engine=guidance_engine, token=hf_token, host="0.0.0.0", port=7860)

        thread = threading.Thread(target=run_fastphone, daemon=True)
        thread.start()

        return {
            "success": True,
            "message": "FastPhone launched on port 7860",
            "note": "Check server logs for phone number and connection code",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FastPhone failed: {str(e)}")

# ─── HEALTH CHECK ───────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    stream = get_fastrtc_stream()
    return {
        "status": "ok",
        "services": {
            "supabase": "connected" if supabase else "error",
            "groq": "connected" if config.groq_client else "not_configured",
            "deepgram_tts": "connected" if config.DEEPGRAM_API_KEY else "not_configured",
            "elevenlabs_tts": "connected" if config.ELEVENLABS_API_KEY else "not_configured",
            "deepgram_stt": "connected" if config.DEEPGRAM_API_KEY else "not_configured",
            "twilio": "connected" if config.TWILIO_SID else "not_configured",
            "fastrtc": "connected" if (config.FASTRTC_AVAILABLE and stream) else "not_configured",
            "fastrtc_primary": config.FASTRTC_AVAILABLE and stream is not None,
        },
        "voice_paths": {
            "primary": "fastrtc" if (config.FASTRTC_AVAILABLE and stream) else "manual_websocket",
            "failsafe": "manual_websocket (/ws/voice/{session_id})",
            "fastphone_available": config.FASTRTC_AVAILABLE,
        },
        "timestamp": datetime.utcnow().isoformat()
    }
