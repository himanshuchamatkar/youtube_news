import os
import asyncio
import edge_tts

class TTSService:
    def __init__(self):
        print("TTS Service: Initialized using Edge-TTS (Free Neural Voices).")

    def generate_narration(self, text: str, output_path: str, voice_name: str = "en-IN-Wavenet-C", speaking_rate: float = 1.05) -> str:
        print(f"TTS Service: Synthesizing narration to {output_path}...")
        
        # Map Google/Generic voice to Edge-TTS Indian English voices
        # Prabhat (Male), Neerja (Female)
        edge_voice = "en-IN-NeerjaNeural"
        voice_lower = voice_name.lower()
        if "wavenet-b" in voice_lower or "neural2-b" in voice_lower or "male" in voice_lower or "prabhat" in voice_lower:
            edge_voice = "en-IN-PrabhatNeural"

        # Calculate rate percent for edge-tts
        rate_percent = int((speaking_rate - 1.0) * 100)
        rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

        async def run_synthesis():
            communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            await communicate.save(output_path)

        # Execute async task in a separate event loop
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(run_synthesis())
            print(f"TTS Service: Generated audio file successfully at {output_path} using voice: {edge_voice} (Rate: {rate_str})")
            return output_path
        except Exception as e:
            print(f"TTS Service: Speech synthesis failed: {e}")
            raise e
        finally:
            loop.close()
