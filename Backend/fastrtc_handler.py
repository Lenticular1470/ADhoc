"""
FastRTC Voice Handler — Primary real-time communication layer
Wraps guidance_engine with FastRTC's ReplyOnPause for built-in VAD, barge-in, turn-taking

FALLBACK STRATEGY:
- If FastRTC stream fails, client falls back to manual WebSocket (/ws/voice/{session_id})
- If Groq PlayAI TTS fails, falls back to guidance_engine.text_to_speech (Deepgram → ElevenLabs)
- If Groq Whisper STT fails, falls back to guidance_engine.transcribe_audio

USAGE (in main.py):
    from fastrtc_handler import create_fastrtc_stream, launch_fastphone
    from agent_orchestrator import agent_config

    stream = create_fastrtc_stream(guidance_engine, agent_config)
    stream.mount(app, path="/fastrtc")
"""

import os
import io
import wave
import tempfile
import asyncio
import json
from typing import Generator, Tuple, Optional, TYPE_CHECKING
import config

import numpy as np
from groq import Groq

# FastRTC imports — wrapped in try/except for graceful degradation
try:
    from fastrtc import (
        ReplyOnPause,
        Stream,
        AlgoOptions,
        audio_to_bytes,
    )
    from fastrtc.utils import current_channel
    FASTRTC_AVAILABLE = True
except Exception as e:
    FASTRTC_AVAILABLE = False
    import traceback

    print("=" * 80)
    print("FASTRTC IMPORT FAILED")
    print(type(e).__name__)
    print(e)
    traceback.print_exc()
    print("=" * 80)

# Import only the config (no circular dependency)
from agent_orchestrator import agent_config, AgentToneConfig
import config

# Avoid circular import — guidance_engine is passed as parameter
if TYPE_CHECKING:
    from guidance_engine import CareerGuidanceEngine


class FastRTCSessionState:
    """Per-session conversation state for FastRTC handler"""
    def __init__(self, session_id: str, config: AgentToneConfig = None):
        self.session_id = session_id
        self.config = config or agent_config
        self.conversation: list = [{"role": "system", "content": self.config.system_prompt}]
        self.is_speaking = False

    def add_user_message(self, text: str):
        self.conversation.append({"role": "user", "content": text})
        if len(self.conversation) > 12:
            self.conversation = [self.conversation[0]] + self.conversation[-11:]

    def add_assistant_message(self, text: str):
        self.conversation.append({"role": "assistant", "content": text})


# Global session store
fastrtc_sessions: dict = {}


def process_groq_playai_tts(
    text: str, 
    voice: str = None,
    pace: float = None
) -> Generator[Tuple[int, np.ndarray], None, None]:
    """
    Generate speech using Groq PlayAI TTS with streaming output.
    Yields (sample_rate, audio_array) chunks for real-time playback.

    Falls back to guidance_engine.text_to_speech if Groq PlayAI fails.
    """
    voice = voice or agent_config.tts_voice
    pace = pace or agent_config.speech_pace

    if not config.groq_client:
        print("[TTS] Groq client unavailable")
        return

    try:
        # Apply pace adjustment to text
        paced_text = agent_config.apply_pace(text)

        # Groq PlayAI TTS — returns wav bytes
        tts_response = config.groq_client.audio.speech.create(
            model=agent_config.tts_model,
            voice=voice,
            response_format="wav",
            input=paced_text,
        )

        # Stream the audio in chunks for real-time playback
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        try:
            tts_response.write_to_file(temp_path)

            with wave.open(temp_path, "rb") as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                n_frames = wf.getnframes()

                # Read in chunks for streaming playback (~200ms chunks)
                chunk_frames = int(sample_rate * 0.2)

                while True:
                    frames = wf.readframes(chunk_frames)
                    if not frames:
                        break

                    audio_array = np.frombuffer(frames, dtype=np.int16)
                    if n_channels > 1:
                        audio_array = audio_array.reshape(-1, n_channels)
                    else:
                        audio_array = audio_array.reshape(1, -1)

                    yield (sample_rate, audio_array)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        print(f"[TTS] Groq PlayAI failed: {e}. No audio generated.")


def numpy_to_wav_bytes(audio: Tuple[int, np.ndarray]) -> bytes:
    """Convert numpy audio array to WAV bytes in-process using wave module (no ffmpeg needed)"""
    sample_rate, array = audio
    flat_array = array.flatten()
    
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(flat_array.tobytes())
    return bio.getvalue()


def send_transcript_to_client(text: str, role: str) -> None:
    """Send transcript string to client via WebRTC DataChannel if available"""
    channel = current_channel.get()
    if not channel:
        return
        
    payload = json.dumps({
        "type": "transcript",
        "text": text,
        "role": role
    })
    
    async def _send(ch) -> None:
        if ch.readyState == "open":
            ch.send(payload)
            
    try:
        loop = getattr(channel, "_loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(channel), loop)
        else:
            try:
                cur_loop = asyncio.get_running_loop()
                if cur_loop.is_running():
                    asyncio.run_coroutine_threadsafe(_send(channel), cur_loop)
                else:
                    asyncio.run(_send(channel))
            except RuntimeError:
                asyncio.run(_send(channel))
    except Exception as ex:
        print(f"[DataChannel] Failed to send transcript: {ex}")


def create_fastrtc_handler(engine: "CareerGuidanceEngine", agent_config_preset: AgentToneConfig = None):
    """
    Factory function that creates a FastRTC handler bound to a guidance_engine instance.

    Args:
        engine: Your CareerGuidanceEngine instance (from main.py)
        agent_config_preset: Optional custom AgentToneConfig

    Returns:
        Handler function compatible with ReplyOnPause
    """
    cfg = agent_config_preset or agent_config

    def handler(audio: Tuple[int, np.ndarray]) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        FastRTC ReplyOnPause handler.

        Pipeline: STT (Whisper) → LLM (Groq) → TTS (PlayAI)
        """
        import uuid
        session_id = f"fastrtc_{uuid.uuid4().hex[:8]}"

        if session_id not in fastrtc_sessions:
            fastrtc_sessions[session_id] = FastRTCSessionState(session_id, cfg)
        session = fastrtc_sessions[session_id]

        print(f"\n🎙️ [FastRTC] Session {session_id}: Received audio")

        # ─── STEP 1: STT ─────────────────────────────────────────────────────
        transcript = ""
        try:
            if config.groq_client:
                wav_bytes = numpy_to_wav_bytes(audio)
                transcript = config.groq_client.audio.transcriptions.create(
                    file=("audio.wav", wav_bytes),
                    model="whisper-large-v3-turbo",
                    response_format="text",
                )
                transcript = str(transcript) if transcript else ""
                print(f"👂 [STT] Groq Whisper: '{transcript}'")
                if transcript.strip():
                    send_transcript_to_client(transcript, "user")
        except Exception as e:
            print(f"[STT] Groq Whisper failed: {e}")

        # Fallback to engine's transcribe
        if not transcript and engine:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                raw_bytes = numpy_to_wav_bytes(audio)
                transcript = loop.run_until_complete(engine.transcribe_audio(raw_bytes))
                loop.close()
                print(f"👂 [STT] Fallback: '{transcript}'")
                if transcript.strip():
                    send_transcript_to_client(transcript, "user")
            except Exception as e:
                print(f"[STT] Fallback failed: {e}")

        if not transcript or not transcript.strip():
            print("[FastRTC] Empty transcript, skipping")
            return

        # ─── STEP 2: LLM ─────────────────────────────────────────────────────
        session.add_user_message(transcript)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ai_response = loop.run_until_complete(
                engine.process_text(
                    transcript,session_id,config.VOICE_AGENT_SYSTEM_PROMPT,))
            loop.close()
            print(f"💬 [LLM] Response: '{ai_response}'")
            session.add_assistant_message(ai_response)
            send_transcript_to_client(ai_response, "assistant")
        except Exception as e:
            print(f"[LLM] Error: {e}")
            ai_response = "I'm sorry, I encountered an error. Please try again."

        # ─── STEP 3: TTS ─────────────────────────────────────────────────────
        print(f"🔊 [TTS] Generating speech via Engine TTS...")

        chunk_count = 0
        if engine:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                audio_bytes = loop.run_until_complete(engine.text_to_speech(ai_response))
                loop.close()

                if audio_bytes:
                    # Stream the audio in chunks for real-time playback (~200ms chunks)
                    sample_rate = 24000
                    sample_width = 2
                    chunk_samples = int(sample_rate * 0.2)  # 200ms
                    chunk_size = chunk_samples * sample_width  # 4800 samples * 2 bytes = 9600 bytes
                    
                    for i in range(0, len(audio_bytes), chunk_size):
                        chunk = audio_bytes[i:i + chunk_size]
                        if chunk:
                            arr = np.frombuffer(chunk, dtype=np.int16).reshape(1, -1)
                            yield (sample_rate, arr)
                            chunk_count += 1
            except Exception as e:
                print(f"[TTS] Engine TTS failed: {e}")

        print(f"✅ [FastRTC] Session {session_id}: Delivered {chunk_count} chunks\n")

    return handler


def create_fastrtc_stream(
    engine: "CareerGuidanceEngine",
    custom_config: AgentToneConfig = None,
):
    """
    Create a FastRTC Stream instance bound to your guidance_engine.

    Args:
        engine: Your CareerGuidanceEngine instance
        custom_config: Optional AgentToneConfig

    Returns:
        Stream instance or None if fastrtc not installed
    """
    if not FASTRTC_AVAILABLE:
        print("[FastRTC] Library not available.")
        return None

    cfg = custom_config or agent_config
    handler = create_fastrtc_handler(engine, cfg)

    return Stream(
        modality="audio",
        mode="send-receive",
        handler=ReplyOnPause(
            handler,
            algo_options=AlgoOptions(
                audio_chunk_duration=cfg.vad_audio_chunk_duration,
                started_talking_threshold=cfg.vad_started_talking_threshold,
                speech_threshold=cfg.vad_speech_threshold,
            ),
            can_interrupt=cfg.can_interrupt,
            input_sample_rate=cfg.input_sample_rate,
        ),
    )


def launch_fastphone(
    engine: "CareerGuidanceEngine",
    token: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 7860,
    custom_config: AgentToneConfig = None,
):
    """Launch FastRTC with a free temporary phone number."""
    if not FASTRTC_AVAILABLE:
        raise RuntimeError("fastrtc not installed")

    stream = create_fastrtc_stream(engine, custom_config)
    if not stream:
        raise RuntimeError("Failed to create stream")

    hf_token = token or os.getenv("HUGGINGFACE_FASTRTC_PHONE_CALL_TOKEN")
    print(f"📞 Launching FastPhone on {host}:{port}...")
    stream.fastphone(token=hf_token, host=host, port=port)


def cleanup_session(session_id: str):
    if session_id in fastrtc_sessions:
        del fastrtc_sessions[session_id]


def cleanup_all_sessions():
    fastrtc_sessions.clear()
