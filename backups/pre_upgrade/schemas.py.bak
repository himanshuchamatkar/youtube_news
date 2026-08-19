from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class SettingsUpdate(BaseModel):
    daily_video_time: str = "11:00 AM"
    videos_per_day: int = 1
    target_duration: str = "30-60 sec"
    language: str = "English"
    youtube_privacy: str = "public"
    news_providers: List[str] = ["newsapi", "gnews", "finnhub", "rss"]
    minimum_news_score: int = 70
    auto_upload: bool = True
    auto_voice: bool = True
    default_tts_voice: str = "en-IN-Wavenet-C"

class GeminiKeyTest(BaseModel):
    api_key: str

class GeminiKeySave(BaseModel):
    api_key: str

class GeminiKeySelectRequest(BaseModel):
    key_id: str

class GeminiKeyTestRequest(BaseModel):
    key_value: str

class LogEntry(BaseModel):
    id: str
    timestamp: datetime
    stage: str
    status: str
    message: str
    duration: float
    error: Optional[str] = None

class JobStatusResponse(BaseModel):
    id: str
    job_date: str
    status: str
    progress: int
    current_stage: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    logs: Optional[List[LogEntry]] = None
