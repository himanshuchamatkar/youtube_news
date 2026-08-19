import os
import asyncio
import edge_tts
from typing import List, Dict, Tuple

class TTSService:
    def __init__(self):
        print("TTS Service: Initialized using Edge-TTS (Free Neural Voices).")

    async def generate_narration(self, text: str, output_path: str, voice_name: str = "en-IN-Wavenet-C", speaking_rate: float = 1.05) -> str:
        """Generate narration audio file. Returns the output path."""
        print(f"TTS Service: Synthesizing narration to {output_path}...")
        
        edge_voice, rate_str = self._resolve_voice(voice_name, speaking_rate)
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            await communicate.save(output_path)
            print(f"TTS Service: Generated audio file successfully at {output_path} using voice: {edge_voice} (Rate: {rate_str})")
            return output_path
        except Exception as e:
            print(f"TTS Service: Speech synthesis failed: {e}")
            raise e

    async def generate_narration_with_timestamps(self, text: str, output_path: str, voice_name: str = "en-IN-Wavenet-C", speaking_rate: float = 1.05) -> Tuple[str, List[Dict]]:
        """
        Generate narration audio AND extract word-level timestamps from Edge-TTS.
        Returns (audio_path, word_timestamps) where word_timestamps is a list of
        {"text": str, "start_ms": float, "end_ms": float}.
        """
        print(f"TTS Service: Synthesizing narration with timestamps to {output_path}...")
        
        edge_voice, rate_str = self._resolve_voice(voice_name, speaking_rate)
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        word_timestamps = []
        
        try:
            # Use the SubMaker approach to capture word boundaries
            submaker = edge_tts.SubMaker()
            
            with open(output_path, "wb") as audio_file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        # Capture word or sentence boundary events
                        word_timestamps.append({
                            "text": chunk["text"],
                            "type": chunk["type"],
                            "start_ms": chunk["offset"] / 10000.0,  # Convert from 100-nanosecond units to ms
                            "end_ms": (chunk["offset"] + chunk["duration"]) / 10000.0,
                        })
            
            print(f"TTS Service: Generated audio with {len(word_timestamps)} word timestamps at {output_path}")
            print(f"TTS Service: Voice: {edge_voice} | Rate: {rate_str}")
            return output_path, word_timestamps
            
        except Exception as e:
            print(f"TTS Service: Timestamped synthesis failed: {e}")
            # Fallback: generate without timestamps
            print("TTS Service: Falling back to standard synthesis...")
            try:
                communicate2 = edge_tts.Communicate(text, edge_voice, rate=rate_str)
                await communicate2.save(output_path)
                return output_path, []
            except Exception as e2:
                print(f"TTS Service: Fallback also failed: {e2}")
                raise e2

    def _resolve_voice(self, voice_name: str, speaking_rate: float) -> Tuple[str, str]:
        """Map voice name to Edge-TTS voice and compute rate string."""
        # Map Google/Generic voice to Edge-TTS Indian English voices
        # Prabhat (Male), Neerja (Female)
        edge_voice = "en-IN-NeerjaNeural"
        voice_lower = voice_name.lower()
        if "wavenet-b" in voice_lower or "neural2-b" in voice_lower or "male" in voice_lower or "prabhat" in voice_lower:
            edge_voice = "en-IN-PrabhatNeural"

        # Calculate rate percent for edge-tts
        rate_percent = int((speaking_rate - 1.0) * 100)
        rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
        
        return edge_voice, rate_str
