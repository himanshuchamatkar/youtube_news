import os
import json
from datetime import datetime, date, timezone
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional

# Import monkeypatched Supabase client first
from backend.app.core.supabase_client import get_supabase_client
from backend.app.core.config import settings
from backend.app.core.security import verify_token, create_access_token
from backend.app.models.schemas import (
    LoginRequest, TokenResponse, SettingsUpdate, GeminiKeyTest, GeminiKeySave, JobStatusResponse
)
from backend.app.jobs.job_manager import JobManager
from backend.app.services.gemini_service import GeminiService
from backend.app.services.youtube_service import YouTubeService

app = FastAPI(
    title="Indian Stock Market daily Shorts Factory API",
    description="Automated YouTube Shorts pipeline for Indian financial market updates",
    version="1.0.0"
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev/deploy staging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_manager = JobManager()
gemini_service = GeminiService()
youtube_service = YouTubeService()

@app.on_event("startup")
async def startup_db_check():
    print("FastAPI: Running database startup checks...")
    try:
        supabase = get_supabase_client()
        # Verify table access
        tables = ["settings", "news_articles", "daily_selections", "scripts", "video_jobs", "videos", "job_logs"]
        missing_tables = []
        for t in tables:
            try:
                supabase.table(t).select("*").limit(1).execute()
            except Exception:
                missing_tables.append(t)
                
        if missing_tables:
            print(f"FastAPI: WARNING! The following database tables are missing: {missing_tables}")
            print("Please run D:/youtube_news/database/migrations/01_init.sql in your Supabase SQL Editor!")
        else:
            print("FastAPI: Database connection and schema validated successfully.")
            
            # Seed default settings in Settings table if empty
            default_config = {
                "daily_video_time": "11:00 AM",
                "videos_per_day": "1",
                "target_duration": "30-60 sec",
                "language": "English",
                "youtube_privacy": "public",
                "news_providers": json.dumps(["newsapi", "gnews", "finnhub", "rss"]),
                "minimum_news_score": "70",
                "auto_upload": "true",
                "auto_voice": "true",
                "default_tts_voice": "en-IN-Wavenet-C"
            }
            for key, val in default_config.items():
                try:
                    exists = supabase.table("settings").select("*").eq("key", key).execute()
                    if not exists.data:
                        supabase.table("settings").insert({"key": key, "value": val}).execute()
                except Exception:
                    pass
    except Exception as e:
        print(f"FastAPI: Failed to verify Supabase schema on startup: {e}")

# --- AUTHENTICATION ---

@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    if req.username == settings.ADMIN_USERNAME and req.password == settings.ADMIN_PASSWORD:
        access_token = create_access_token(data={"sub": req.username})
        return TokenResponse(access_token=access_token)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

# --- SYSTEM ENDPOINTS ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.post("/api/system/wake")
def system_wake():
    # Wake up endpoint, simple check
    try:
        supabase = get_supabase_client()
        # Verify db is responsive
        supabase.table("settings").select("*").limit(1).execute()
        db_ok = True
    except Exception:
        db_ok = False
        
    return {
        "status": "online",
        "database_connected": db_ok,
        "time": datetime.utcnow().isoformat()
    }

@app.get("/api/system/status")
def system_status(username: str = Depends(verify_token)):
    supabase = get_supabase_client()
    
    # Check Gemini key state
    gemini_configured = False
    try:
        res = supabase.table("settings").select("value").eq("key", "gemini_api_key").execute()
        if res.data and res.data[0]["value"]:
            gemini_configured = True
    except Exception:
        pass
    if not gemini_configured and settings.GEMINI_API_KEY:
        gemini_configured = True
        
    # Check YouTube config
    yt_configured = all([settings.YOUTUBE_CLIENT_ID, settings.YOUTUBE_CLIENT_SECRET, settings.YOUTUBE_REFRESH_TOKEN])

    return {
        "status": "online",
        "gemini_api_configured": gemini_configured,
        "youtube_api_configured": yt_configured,
        "environment": settings.NODE_ENV,
        "python_version": "3.11.9"
    }

# --- PIPELINE / JOB ROUTING ---

@app.post("/api/jobs/daily-news")
def trigger_daily_job(is_test: bool = False, username: str = Depends(verify_token)):
    try:
        job_id = job_manager.start_pipeline_job(is_test=is_test)
        return {"success": True, "job_id": job_id, "message": f"Daily News Short generation job ({'Test Mode' if is_test else 'Production Mode'}) started successfully."}
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start pipeline: {e}")

@app.get("/api/jobs/{id}/video")
def download_job_video(id: str):
    video_path = f"D:/youtube_news/media/rendered/short_{id}.mp4"
    if os.path.exists(video_path):
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=f"short_{id}.mp4"
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found or still rendering.")

@app.get("/api/jobs")
def list_jobs(limit: int = 20, username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        res = supabase.table("video_jobs").select("*").order("started_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/jobs/{id}")
def get_job_status(id: str, username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        # Fetch job parameters
        job_res = supabase.table("video_jobs").select("*").eq("id", id).execute()
        if not job_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        
        job = job_res.data[0]
        
        # Fetch job logs
        logs_res = supabase.table("job_logs").select("*").eq("job_id", id).order("timestamp", desc=False).execute()
        job["logs"] = logs_res.data
        
        return job
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- NEWS ROUTING ---

@app.get("/api/news")
def list_news(limit: int = 50):
    try:
        supabase = get_supabase_client()
        # Retrieve raw and scored articles
        res = supabase.table("news_articles").select("*").order("published_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/news/{id}")
def get_news_detail(id: str):
    try:
        supabase = get_supabase_client()
        res = supabase.table("news_articles").select("*").eq("id", id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="News article not found")
        return res.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- VIDEOS HISTORY ---

@app.get("/api/videos")
def list_videos(limit: int = 50):
    try:
        supabase = get_supabase_client()
        res = supabase.table("videos").select("*").order("published_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/videos/{id}")
def get_video_detail(id: str):
    try:
        supabase = get_supabase_client()
        res = supabase.table("videos").select("*").eq("id", id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Video details not found")
            
        video = res.data[0]
        
        # Add script information
        script_res = supabase.table("scripts").select("*").eq("news_article_id", video["source_urls"][0] if video["source_urls"] else None).execute()
        video["script_details"] = script_res.data[0] if script_res.data else None
        
        return video
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- ANALYTICS ---

@app.get("/api/analytics/channel")
def get_channel_analytics():
    try:
        supabase = get_supabase_client()
        
        # 1. Fetch channel statistics from cache
        cache_res = supabase.table("channel_metrics").select("*").order("captured_at", desc=True).limit(1).execute()
        
        # If cache contains recent data, return it
        if cache_res.data:
            cached_stat = cache_res.data[0]
            # Calculate duration in hours
            cap_dt = datetime.fromisoformat(cached_stat["captured_at"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - cap_dt).total_seconds() / 3600.0
            if age_hours < 2.0:
                # Return cache
                return cached_stat

        # 2. Fetch fresh stats from YouTube
        stats = youtube_service.fetch_channel_metrics()
        if stats.get("success", False):
            # Cache statistics
            supabase.table("channel_metrics").insert({
                "subscriber_count": stats["subscriber_count"],
                "total_views": stats["total_views"],
                "total_likes": 0,
                "total_comments": 0
            }).execute()
            
            # Fetch total count of videos uploaded
            vid_count = supabase.table("videos").select("id", count="exact").execute()
            stats["total_videos"] = vid_count.count or 0
            return stats
            
        # Fallback to cache if YouTube fails
        if cache_res.data:
            return cache_res.data[0]
            
        return {"subscriber_count": 0, "total_views": 0, "total_likes": 0, "total_comments": 0, "total_videos": 0}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/videos")
def get_videos_analytics():
    try:
        supabase = get_supabase_client()
        videos_res = supabase.table("videos").select("id, title, published_at, youtube_video_id, youtube_url").execute()
        
        analytics_list = []
        for vid in videos_res.data:
            yt_id = vid.get("youtube_video_id")
            if not yt_id:
                continue
                
            # Fetch fresh video views/likes/comments
            metrics = youtube_service.fetch_video_metrics(yt_id)
            
            # Upsert cache
            supabase.table("video_metrics").insert({
                "video_id": vid["id"],
                "views": metrics["views"],
                "likes": metrics["likes"],
                "comments": metrics["comments"]
            }).execute()
            
            analytics_list.append({
                "id": vid["id"],
                "title": vid["title"],
                "published_at": vid["published_at"],
                "youtube_url": vid["youtube_url"],
                "views": metrics["views"],
                "likes": metrics["likes"],
                "comments": metrics["comments"]
            })
            
        return analytics_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SETTINGS MANAGEMENT ---

@app.get("/api/settings")
def get_system_settings(username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        res = supabase.table("settings").select("*").execute()
        
        # Format as key-value
        settings_dict = {}
        for row in res.data:
            k = row["key"]
            v = row["value"]
            if k == "gemini_api_key":
                # Do NOT return the key in plaintext! Return redacted format.
                settings_dict[k] = "********************"
            else:
                settings_dict[k] = v
                
        return settings_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/gemini")
def update_gemini_key(req: GeminiKeySave, username: str = Depends(verify_token)):
    try:
        # Encrypt the key
        encrypted_key = settings.encrypt(req.api_key)
        
        supabase = get_supabase_client()
        # Save encrypted value to DB
        supabase.table("settings").upsert({
            "key": "gemini_api_key",
            "value": encrypted_key,
            "is_encrypted": True
        }).execute()
        
        return {"success": True, "message": "Gemini API Key updated securely."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save Gemini key: {e}")

@app.post("/api/settings/gemini/test")
def test_gemini_key(req: GeminiKeyTest):
    # Publicly accessible, but doesn't modify config. Tests key validity.
    is_valid = gemini_service.test_key(req.api_key)
    return {"valid": is_valid}

@app.post("/api/settings")
def update_other_settings(req: SettingsUpdate, username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        data = req.dict()
        for k, v in data.items():
            val_str = json.dumps(v) if isinstance(v, list) else str(v)
            if isinstance(v, bool):
                val_str = "true" if v else "false"
            supabase.table("settings").upsert({"key": k, "value": val_str}).execute()
            
        return {"success": True, "message": "Settings updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {e}")
