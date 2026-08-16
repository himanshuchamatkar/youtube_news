import os
import json
from google.cloud import texttospeech
from backend.app.core.config import settings

class TTSService:
    def __init__(self):
        self._setup_credentials()

    def _setup_credentials(self):
        # Read the Google Cloud service-account JSON from settings
        cred_json = settings.GOOGLE_APPLICATION_CREDENTIALS if hasattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS') else settings.GOOGLE_TTS_SERVICE_ACCOUNT_JSON
        if not cred_json:
            # Fallback check
            cred_json = os.getenv("GOOGLE_TTS_SERVICE_ACCOUNT_JSON")

        if cred_json:
            try:
                # Validate it's valid JSON
                cred_dict = json.loads(cred_json)
                temp_cred_path = "D:/youtube_news/media/temp/tts_credentials.json"
                os.makedirs(os.path.dirname(temp_cred_path), exist_ok=True)
                with open(temp_cred_path, "w", encoding="utf-8") as f:
                    json.dump(cred_dict, f)
                # Point Google library to this credentials file
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(temp_cred_path)
                print("TTS Service: Google application credentials configured.")
            except Exception as e:
                print(f"TTS Service: Error writing credentials JSON: {e}")
        else:
            print("TTS Service: Google service account credentials are not set in environment.")

    def generate_narration(self, text: str, output_path: str, voice_name: str = "en-IN-Wavenet-C", speaking_rate: float = 1.05) -> str:
        # Check if credential env var exists
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            # Try to double check if we can fall back or raise
            raise ValueError("Google Cloud TTS credentials are not configured.")

        print(f"TTS Service: Synthesizing narration to {output_path}...")
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Indian English voices: en-IN-Wavenet-B (Male), en-IN-Wavenet-C (Female), en-IN-Neural2-B (Male)
        # Default is Indian English
        lang_code = "en-IN"
        if voice_name.startswith("en-US"):
            lang_code = "en-US"

        voice = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=voice_name
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=0.0
        )

        try:
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
                
            print(f"TTS Service: Generated audio file successfully at {output_path}")
            return output_path
        except Exception as e:
            print(f"TTS Service: Speech synthesis failed: {e}")
            raise e
