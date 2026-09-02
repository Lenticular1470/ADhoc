import os
import tempfile
import httpx
from typing import Dict, List
import config

class CareerGuidanceEngine:
    def __init__(self):
        self.conversations: Dict[str, List[Dict[str, str]]] = {}

    def get_conversation(
            self,
            session_id: str,
            system_prompt: str = config.CAREER_SYSTEM_PROMPT,
            ) -> List[Dict[str, str]]:
        if session_id not in self.conversations:
            self.conversations[session_id] = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        return self.conversations[session_id]

    async def process_text(
            self,
            text: str,
            session_id: str,
            system_prompt: str = config.CAREER_SYSTEM_PROMPT,
            ) -> str:
        conversation = self.get_conversation(
            session_id,
            system_prompt,
            )
        conversation.append({"role": "user", "content": text})

        if len(conversation) > 12:
            conversation = [conversation[0]] + conversation[-11:]
            self.conversations[session_id] = conversation

        if not config.groq_client:
            return "I'm sorry, the AI service is currently unavailable. Please try again later."

        messages_for_groq: List[Dict[str, str]] = []
        for msg in conversation:
            messages_for_groq.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        response = config.groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages_for_groq,  # type: ignore
            temperature=0.7,
            max_tokens=512,
            top_p=0.9
        )

        ai_text = response.choices[0].message.content or "I'm sorry, I didn't understand that."
        conversation.append({"role": "assistant", "content": ai_text})
        return ai_text

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribe audio using Groq Whisper - accepts raw PCM 16-bit mono 16kHz"""
        if not config.groq_client:
            return ""

        import wave
        tmp_path = tempfile.mktemp(suffix=".wav")
        try:
            with wave.open(tmp_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio_bytes)

            with open(tmp_path, 'rb') as audio_file:
                transcript = config.groq_client.audio.transcriptions.create(
                    file=("audio.wav", audio_file),
                    model="whisper-large-v3-turbo",
                    response_format="text"
                )
            return str(transcript) if transcript else ""
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech - Deepgram primary, ElevenLabs backup"""
        # Try Deepgram first (free tier, fast, reliable)
        if config.DEEPGRAM_API_KEY:
            try:
                url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&sample_rate=24000&channels=1"
                headers = {
                    "Authorization": f"Token {config.DEEPGRAM_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {"text": text}

                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=payload, timeout=60)
                    if response.status_code == 200:
                        print(f"Deepgram TTS: {len(response.content)} bytes")
                        return response.content
                    else:
                        print(f"Deepgram error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Deepgram TTS failed: {e}")

        # Fallback to ElevenLabs
        if config.ELEVENLABS_API_KEY:
            try:
                url = "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL/stream"
                headers = {
                    "xi-api-key": config.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                }
                payload = {
                    "text": text,
                    "model_id": "eleven_turbo_v2_5",
                    "output_format": "pcm_24000"
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=payload, timeout=60)
                    if response.status_code == 200:
                        print(f"ElevenLabs TTS: {len(response.content)} bytes")
                        return response.content
                    else:
                        print(f"ElevenLabs error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"ElevenLabs TTS failed: {e}")

        return b""

guidance_engine = CareerGuidanceEngine()
