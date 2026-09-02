"""
Agent Orchestrator — Shared config for voice AI personality
Used by both FastRTC (primary) and manual WebSocket (failsafe) paths
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os

@dataclass
class AgentToneConfig:
    """Configure agent personality, temperature, and speech pace"""
    # LLM personality
    system_prompt: str = """You are CareerGuide AI, an expert career counselor and college admission advisor for Indian students. 

CRITICAL RULES:
1. ALWAYS respond in the SAME language the user used. If they speak English, respond in English. If they speak Hindi, respond in Hindi. If they mix (Hinglish), respond in Hinglish.
2. NEVER switch languages on your own. Do not "helpfully" translate to Hindi if the user is speaking English.
3. Keep responses concise but informative (2-4 sentences max for voice). 
4. Be empathetic, encouraging, and data-driven. Ask clarifying questions to give better advice.
5. Help with: college admissions, entrance exams (JEE, NEET, CAT, etc.), scholarships, course selection, job market trends in India.
6. If you don't know specific current data, be honest and guide the student on where to find it.

Current context: You are speaking with a student who needs guidance. Be conversational and natural."""

    # LLM parameters
    temperature: float = 0.7
    max_tokens: int = 256
    top_p: float = 0.9

    # TTS pace control (affects sentence splitting and pause insertion)
    speech_pace: float = 1.0  # 0.5 = slow, 1.0 = normal, 1.5 = fast

    # TTS voice selection (Groq PlayAI voices)
    tts_voice: str = "Celeste-PlayAI"  # Options: Celeste-PlayAI, Atlas-PlayAI, etc.
    tts_model: str = "playai-tts"

    # VAD / Turn-taking
    vad_speech_threshold: float = 0.60
    vad_started_talking_threshold: float = 0.40
    vad_audio_chunk_duration: float = 0.8
    vad_min_silence_ms: int = 1800  # Silence before considering turn over

    # Barge-in / interruption
    can_interrupt: bool = True
    interrupt_threshold: int = 5  # Consecutive loud chunks to trigger interrupt

    # Audio format
    input_sample_rate: int = 16000  # FastRTC expects 16kHz
    output_sample_rate: int = 24000  # Groq TTS outputs 24kHz

    def to_groq_messages(self, conversation_history: list) -> list:
        """Format conversation for Groq API"""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(conversation_history)
        return messages

    def apply_pace(self, text: str) -> str:
        """Adjust text pacing by adding/removing pauses"""
        if self.speech_pace <= 0.8:
            # Slower: add more pauses
            text = text.replace(". ", ". ... ")
            text = text.replace("? ", "? ... ")
        elif self.speech_pace >= 1.3:
            # Faster: minimize pauses, use shorter sentences
            text = text.replace("...", ".")
            text = text.replace("  ", " ")
        return text


# Global config instance — modify this to change agent behavior
agent_config = AgentToneConfig()

# Preset configurations for different scenarios
AGENT_PRESETS: Dict[str, AgentToneConfig] = {
    "default": AgentToneConfig(),
    "warm_counselor": AgentToneConfig(
        temperature=0.8,
        speech_pace=0.9,
        system_prompt="""You are a warm, patient career counselor. Speak slowly and reassuringly. 
Use encouraging language. Always validate the student's concerns before giving advice."""
    ),
    "urgent_advisor": AgentToneConfig(
        temperature=0.5,
        speech_pace=1.2,
        max_tokens=150,
        system_prompt="""You are a direct, efficient admission advisor. Be concise and action-oriented.
Focus on deadlines, requirements, and next steps. Minimize pleasantries."""
    ),
    "detailed_explainer": AgentToneConfig(
        temperature=0.6,
        speech_pace=0.85,
        max_tokens=400,
        system_prompt="""You are a thorough academic advisor. Provide detailed explanations with examples.
Break down complex topics into digestible parts. Use analogies when helpful."""
    ),
}


def get_agent_preset(name: str = "default") -> AgentToneConfig:
    """Get a preset configuration by name"""
    return AGENT_PRESETS.get(name, AGENT_PRESETS["default"])


def update_agent_config(**kwargs) -> AgentToneConfig:
    """Update the global agent config"""
    global agent_config
    for key, value in kwargs.items():
        if hasattr(agent_config, key):
            setattr(agent_config, key, value)
    return agent_config
