#!/usr/bin/env python3
"""
Voice Handler for Iron Man Mode
Captures text input (keyboard or OS dictation) and provides TTS output
Uses direct text capture instead of audio processing for speed and simplicity
"""

import subprocess
import platform
import json
import os
from datetime import datetime

class VoiceHandler:
    """Handles text input/output for Iron Man Mode voice interface"""

    def __init__(self):
        self.tts_enabled = True
        self.last_command = None
        self.command_history = []

    def capture_command(self, prompt="Command: "):
        """
        Gets text input directly
        User can type OR use OS-level dictation (macOS Fn+Fn, Windows Win+H)

        Args:
            prompt: Input prompt text

        Returns:
            str: User command text
        """
        try:
            command = input(prompt).strip()

            if command:
                self.last_command = command
                self.command_history.append({
                    "command": command,
                    "timestamp": datetime.now().isoformat()
                })

            return command

        except (KeyboardInterrupt, EOFError):
            return None

    def speak(self, text):
        """
        Platform-agnostic text-to-speech output

        Args:
            text: Text to speak
        """
        if not self.tts_enabled:
            return

        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                subprocess.run(["say", text], check=False)
            elif system == "Linux":
                subprocess.run(["espeak", text], check=False)
            elif system == "Windows":
                ps_command = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
                subprocess.run(["powershell", "-c", ps_command], check=False)
        except Exception as e:
            print(f"TTS Error: {e}")

    def parse_voice_command(self, transcript):
        """
        Routes voice input to appropriate action type

        Args:
            transcript: User command text

        Returns:
            dict: Action type and parameters
        """
        transcript_lower = transcript.lower()

        # Task assignment patterns
        task_keywords = ["create", "build", "write", "summarize", "analyze", "generate", "make"]
        if any(kw in transcript_lower for kw in task_keywords):
            return {
                "type": "task_assignment",
                "description": transcript
            }

        # Status check patterns
        status_keywords = ["status", "what's happening", "show me", "tasks", "list"]
        if any(kw in transcript_lower for kw in status_keywords):
            return {
                "type": "status_query",
                "query": transcript
            }

        # Tool execution patterns
        if "run" in transcript_lower or "execute" in transcript_lower:
            return {
                "type": "direct_execution",
                "command": transcript
            }

        # Exit patterns
        if "exit" in transcript_lower or "quit" in transcript_lower or "stop" in transcript_lower:
            return {
                "type": "exit",
                "text": transcript
            }

        # Default: Q&A with Claude
        return {
            "type": "question",
            "text": transcript
        }

    def toggle_tts(self):
        """Enable/disable text-to-speech"""
        self.tts_enabled = not self.tts_enabled
        return self.tts_enabled

    def get_history(self, limit=10):
        """Get recent command history"""
        return self.command_history[-limit:]

    def save_history(self, filepath="data/ironman_command_history.json"):
        """Save command history to file"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(self.command_history, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def load_history(self, filepath="data/ironman_command_history.json"):
        """Load command history from file"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    self.command_history = json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")


# CLI testing
if __name__ == "__main__":
    print("Voice Handler Test")
    print("=" * 50)

    handler = VoiceHandler()

    # Test TTS
    handler.speak("Voice handler initialized")

    # Test command capture
    while True:
        command = handler.capture_command("\nEnter command (or 'quit'): ")

        if not command:
            continue

        parsed = handler.parse_voice_command(command)
        print(f"Parsed: {parsed}")

        if parsed["type"] == "exit":
            handler.speak("Goodbye")
            break

        handler.speak(f"Received {parsed['type']}")

    # Save history
    handler.save_history()
    print(f"\nCommand history saved ({len(handler.command_history)} commands)")
