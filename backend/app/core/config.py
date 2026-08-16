import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys
    GEMINI_API_KEY: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REFRESH_TOKEN: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    GOOGLE_TTS_SERVICE_ACCOUNT_JSON: str = ""
    NEWS_API_KEY: str = ""
    GNEWS_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    PEXELS_API_KEY: str = ""

    # System Configuration
    SETTINGS_ENCRYPTION_KEY: str = ""
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    NODE_ENV: str = "development"

    # Encription cipher
    _cipher: Optional[Fernet] = None

    def get_cipher(self) -> Fernet:
        if self._cipher is None:
            if not self.SETTINGS_ENCRYPTION_KEY:
                # Fallback if not configured
                key = Fernet.generate_key()
                self._cipher = Fernet(key)
            else:
                try:
                    self._cipher = Fernet(self.SETTINGS_ENCRYPTION_KEY.encode())
                except Exception:
                    # If invalid key, fallback to a local one
                    key = Fernet.generate_key()
                    self._cipher = Fernet(key)
        return self._cipher

    def encrypt(self, val: str) -> str:
        if not val:
            return ""
        cipher = self.get_cipher()
        return cipher.encrypt(val.encode()).decode()

    def decrypt(self, val: str) -> str:
        if not val:
            return ""
        cipher = self.get_cipher()
        try:
            return cipher.decrypt(val.encode()).decode()
        except Exception:
            return ""

# Initialize global settings
settings = Settings()
