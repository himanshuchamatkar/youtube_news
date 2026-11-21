import os
import json
from datetime import datetime, date, timezone
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional

# Import monkeypatched Supabase client first
from backend.app.core.supabase_client import get_supabase_client
from backend.app.core.config import settings
from backend.app.core.security import verify_token, create_access_token
from backend.app.models.schemas import (
    LoginRequest, TokenResponse, SettingsUpdate, GeminiKeyTest, GeminiKeySave, JobStatusResponse,
    GeminiKeySelectRequest, GeminiKeyTestRequest
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
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    video_path = os.path.join(base_dir, "media", "rendered", f"short_{id}.mp4")
    if os.path.exists(video_path):
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=f"short_{id}.mp4"
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found or still rendering.")

@app.post("/api/jobs/{id}/cancel")
def cancel_job_execution(id: str, username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        # 1. Update job status in database
        supabase.table("video_jobs").update({
            "status": "CANCELLED",
            "error_message": "Cancelled by user"
        }).eq("id", id).execute()
        
        # 2. Add log entry
        supabase.table("job_logs").insert({
            "job_id": id,
            "stage": "COMPLETED",
            "status": "CANCELLED",
            "message": "Job cancelled and terminated by user from dashboard.",
            "duration": 0
        }).execute()
        
        # 3. Call job manager cancellation
        job_manager.cancel_job(id)
        
        # 4. Cleanup temp files
        job_manager.cleanup_temp_files(id)
        
        return {"success": True, "message": "Job cancellation request sent successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/jobs")
def list_jobs(limit: int = 20, username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        res = supabase.table("video_jobs").select("*").order("started_at", desc=True).limit(limit).execute()
        jobs = res.data or []
        # Pre-attach logs to recent jobs for instant visual workflow rendering without delays
        for job in jobs[:5]:
            logs_res = supabase.table("job_logs").select("*").eq("job_id", job["id"]).order("timestamp", desc=False).execute()
            job["logs"] = logs_res.data or []
        return jobs
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
        
        # Fetch associated video details if present
        video_res = supabase.table("videos").select("*").eq("job_id", id).execute()
        if video_res.data:
            video = video_res.data[0]
            job["youtube_url"] = video["youtube_url"]
            job["youtube_video_id"] = video["youtube_video_id"]
            job["video_title"] = video["title"]
        else:
            job["youtube_url"] = None
            job["youtube_video_id"] = None
            job["video_title"] = None
            
        return job
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- DELETE ENDPOINTS ---

@app.delete("/api/jobs/{id}")
def delete_job(id: str, username: str = Depends(verify_token)):
    """Delete a job and its associated logs, videos, and temp files."""
    try:
        supabase = get_supabase_client()
        
        # Check job exists and is not actively running
        job_res = supabase.table("video_jobs").select("*").eq("id", id).execute()
        if not job_res.data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = job_res.data[0]
        active_statuses = ["RUNNING", "FETCHING_NEWS", "ANALYZING", "SCRIPTING", 
                           "GENERATING_AUDIO", "GENERATING_VISUALS", "RENDERING",
                           "VALIDATING", "UPLOADING", "QUEUED"]
        if job["status"] in active_statuses:
            raise HTTPException(status_code=400, detail="Cannot delete an actively running job. Cancel it first.")
        
        # Delete associated video records
        supabase.table("videos").delete().eq("job_id", id).execute()
        
        # Delete associated logs
        supabase.table("job_logs").delete().eq("job_id", id).execute()
        
        # Delete the job itself
        supabase.table("video_jobs").delete().eq("id", id).execute()
        
        # Cleanup any remaining temp files
        job_manager.cleanup_temp_files(id)
        
        # Also try to remove rendered video
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        video_path = os.path.join(base_dir, "media", "rendered", f"short_{id}.mp4")
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass
        
        return {"success": True, "message": f"Job and all associated records deleted.", "deleted_job_id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/videos/{id}")
def delete_video(id: str, username: str = Depends(verify_token)):
    """Delete a video record from the database."""
    try:
        supabase = get_supabase_client()
        
        vid_res = supabase.table("videos").select("*").eq("id", id).execute()
        if not vid_res.data:
            raise HTTPException(status_code=404, detail="Video not found")
        
        supabase.table("videos").delete().eq("id", id).execute()
        
        return {"success": True, "message": f"Video deleted.", "deleted_video_id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs/bulk-delete")
def bulk_delete_jobs(action: str = "failed", username: str = Depends(verify_token)):
    """Bulk delete jobs by category: failed, cancelled, test, old, all_finished."""
    try:
        supabase = get_supabase_client()
        deleted_count = 0
        
        active_statuses = ["RUNNING", "FETCHING_NEWS", "ANALYZING", "SCRIPTING",
                           "GENERATING_AUDIO", "GENERATING_VISUALS", "RENDERING",
                           "VALIDATING", "UPLOADING", "QUEUED"]
        
        # Get all jobs
        jobs_res = supabase.table("video_jobs").select("id, status, is_test, started_at").execute()
        job_ids = []
        
        for job in (jobs_res.data or []):
            # Never delete actively running jobs
            if job["status"] in active_statuses:
                continue
            
            if action == "failed" and job["status"] != "FAILED":
                continue
            elif action == "cancelled" and job["status"] != "CANCELLED":
                continue
            elif action == "test" and not job.get("is_test", False):
                continue
            elif action == "old":
                from datetime import timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                if job.get("started_at", "") > cutoff:
                    continue
            elif action == "all_finished":
                if job["status"] not in ["COMPLETED", "FAILED", "CANCELLED", "SKIPPED"]:
                    continue
            elif action not in ["failed", "cancelled", "test", "old", "all_finished"]:
                raise HTTPException(status_code=400, detail=f"Unknown bulk action: {action}")
            
            job_ids.append(job["id"])
        
        for jid in job_ids:
            try:
                supabase.table("videos").delete().eq("job_id", jid).execute()
                supabase.table("job_logs").delete().eq("job_id", jid).execute()
                supabase.table("video_jobs").delete().eq("id", jid).execute()
                job_manager.cleanup_temp_files(jid)
                deleted_count += 1
            except Exception:
                pass
        
        return {"success": True, "deleted_count": deleted_count, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/job-logs/bulk-delete")
def bulk_delete_logs(action: str = "all", username: str = Depends(verify_token)):
    """Clear old/unwanted log entries. Actions: all, failed, old."""
    try:
        supabase = get_supabase_client()
        
        if action == "failed":
            supabase.table("job_logs").delete().eq("status", "FAILED").execute()
        elif action == "all":
            # Delete logs for completed/failed/cancelled jobs only (preserve running job logs)
            jobs_res = supabase.table("video_jobs").select("id, status").execute()
            for job in (jobs_res.data or []):
                if job["status"] in ["COMPLETED", "FAILED", "CANCELLED", "SKIPPED"]:
                    supabase.table("job_logs").delete().eq("job_id", job["id"]).execute()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown log cleanup action: {action}")
        
        return {"success": True, "message": f"Log cleanup ({action}) completed."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
def get_channel_analytics(refresh: bool = False, filter: str = Query("all", regex="^(public|test|all)$")):
    try:
        supabase = get_supabase_client()
        
        # 1. Try fetching real-time video list directly from YouTube API first
        videos = youtube_service.fetch_channel_videos()
        
        if videos:
            # Filter based on YouTube live privacy status
            if filter == "public":
                filtered_vids = [v for v in videos if not v["is_test"]]
            elif filter == "test":
                filtered_vids = [v for v in videos if v["is_test"]]
            else:
                filtered_vids = videos
                
            total_views = sum(v.get("views", 0) for v in filtered_vids)
            total_videos = len(filtered_vids)
            
            # Fetch subscriber count (use cache if < 10 mins old and not refresh)
            subscriber_count = 0
            cache_res = supabase.table("channel_metrics").select("*").order("captured_at", desc=True).limit(1).execute()
            
            use_cache = False
            if not refresh and cache_res.data:
                cached_stat = cache_res.data[0]
                try:
                    date_str = cached_stat["captured_at"]
                    if "T" not in date_str and " " in date_str:
                        date_str = date_str.replace(" ", "T")
                    if "+" not in date_str and "-" not in date_str[-6:] and "Z" not in date_str:
                        date_str += "+00:00"
                    cap_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    age_mins = (datetime.now(timezone.utc) - cap_dt).total_seconds() / 60.0
                    if age_mins < 10.0:
                        subscriber_count = cached_stat.get("subscriber_count", 0)
                        use_cache = True
                except Exception as dt_err:
                    print(f"YouTube Service: Failed to parse captured_at '{cached_stat.get('captured_at')}': {dt_err}")
                    
            if not use_cache:
                stats = youtube_service.fetch_channel_metrics()
                subscriber_count = stats.get("subscriber_count", 0)
                # Save to cache
                try:
                    overall_views = sum(v.get("views", 0) for v in videos)
                    supabase.table("channel_metrics").insert({
                        "subscriber_count": subscriber_count,
                        "total_views": overall_views,
                        "total_likes": 0,
                        "total_comments": 0
                    }).execute()
                except Exception:
                    pass
                    
            return {
                "subscriber_count": subscriber_count,
                "total_views": total_views,
                "total_videos": total_videos,
                "total_likes": 0,
                "total_comments": 0,
                "success": True
            }
            
        # 2. Fallback to local SQLite Database if YouTube API is unconfigured
        if filter == "public":
            vids_res = supabase.table("videos").select("youtube_video_id").eq("is_test", False).execute()
        elif filter == "test":
            vids_res = supabase.table("videos").select("youtube_video_id").eq("is_test", True).execute()
        else:
            vids_res = supabase.table("videos").select("youtube_video_id").execute()
            
        video_ids = [v["youtube_video_id"] for v in vids_res.data if v.get("youtube_video_id")] if vids_res.data else []
        total_videos = len(vids_res.data) if vids_res.data else 0
        
        # Check cache
        if not refresh:
            cache_res = supabase.table("channel_metrics").select("*").order("captured_at", desc=True).limit(1).execute()
            if cache_res.data:
                cached_stat = cache_res.data[0]
                try:
                    date_str = cached_stat["captured_at"]
                    if "T" not in date_str and " " in date_str:
                        date_str = date_str.replace(" ", "T")
                    if "+" not in date_str and "-" not in date_str[-6:] and "Z" not in date_str:
                        date_str += "+00:00"
                    cap_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    age_mins = (datetime.now(timezone.utc) - cap_dt).total_seconds() / 60.0
                    if age_mins < 10.0:
                        return {
                            "subscriber_count": cached_stat.get("subscriber_count", 0),
                            "total_views": cached_stat.get("total_views", 0),
                            "total_videos": total_videos,
                            "total_likes": 0,
                            "total_comments": 0,
                            "success": True
                        }
                except Exception as dt_err:
                    print(f"YouTube Service: Failed to parse captured_at '{cached_stat.get('captured_at')}': {dt_err}")
        
        total_views = 0
        if video_ids:
            metrics_dict = youtube_service.fetch_multiple_videos_metrics(video_ids)
            total_views = sum(m.get("views", 0) for m in metrics_dict.values())
            
        stats = youtube_service.fetch_channel_metrics()
        subscriber_count = stats.get("subscriber_count", 0)
        
        try:
            supabase.table("channel_metrics").insert({
                "subscriber_count": subscriber_count,
                "total_views": total_views,
                "total_likes": 0,
                "total_comments": 0
            }).execute()
        except Exception:
            pass
            
        return {
            "subscriber_count": subscriber_count,
            "total_views": total_views,
            "total_videos": total_videos,
            "total_likes": 0,
            "total_comments": 0,
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/videos")
def get_videos_analytics(filter: str = Query("all", regex="^(public|test|all)$")):
    try:
        videos = youtube_service.fetch_channel_videos()
        
        # If API failed or returned empty list (e.g. no key), fallback to SQLite database
        if not videos:
            supabase = get_supabase_client()
            if filter == "public":
                videos_res = supabase.table("videos").select("id, title, published_at, youtube_video_id, youtube_url, is_test, status").eq("is_test", False).execute()
            elif filter == "test":
                videos_res = supabase.table("videos").select("id, title, published_at, youtube_video_id, youtube_url, is_test, status").eq("is_test", True).execute()
            else:
                videos_res = supabase.table("videos").select("id, title, published_at, youtube_video_id, youtube_url, is_test, status").execute()
            
            video_ids = [v["youtube_video_id"] for v in videos_res.data if v.get("youtube_video_id")] if videos_res.data else []
            metrics_dict = {}
            if video_ids:
                metrics_dict = youtube_service.fetch_multiple_videos_metrics(video_ids)
                
            analytics_list = []
            for vid in videos_res.data:
                yt_id = vid.get("youtube_video_id")
                stats = metrics_dict.get(yt_id, {"views": 0, "likes": 0, "comments": 0}) if yt_id else {"views": 0, "likes": 0, "comments": 0}
                
                analytics_list.append({
                    "id": vid["id"],
                    "title": vid["title"],
                    "published_at": vid["published_at"],
                    "youtube_url": vid["youtube_url"],
                    "views": stats["views"],
                    "likes": stats["likes"],
                    "comments": stats["comments"],
                    "is_test": vid.get("is_test", False),
                    "status": vid.get("status", "unknown")
                })
            return analytics_list
            
        # Apply filter on API list
        if filter == "public":
            filtered = [v for v in videos if not v["is_test"]]
        elif filter == "test":
            filtered = [v for v in videos if v["is_test"]]
        else:
            filtered = videos
            
        return filtered
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

@app.get("/api/settings/gemini-keys")
def list_gemini_keys(username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        
        # Load env keys
        keys_list = [
            {"id": "default", "name": "Primary Gemini Key (Env)", "value": settings.GEMINI_API_KEY},
            {"id": "backup_1", "name": "Backup Gemini Key 1 (Env)", "value": settings.GEMINI_BACKUP_API_KEY},
            {"id": "backup_2", "name": "Backup Gemini Key 2 (Env)", "value": settings.GEMINI_BACKUP_API_KEY_2},
            {"id": "ollama", "name": "Local Ollama (Qwen-2.5)", "value": "http://localhost:11434"}
        ]
        
        # Check custom DB key
        db_key = gemini_service.get_db_key()
        if db_key:
            keys_list.append({"id": "db_key", "name": "Custom Gemini Key (DB)", "value": db_key})
            
        # Get selected active key ID from DB settings
        active_id = "default"
        res = supabase.table("settings").select("value").eq("key", "active_gemini_key_id").execute()
        if res.data:
            active_id = res.data[0]["value"]
            
        # Redact actual key values for presentation, but keep raw value for testing
        formatted_keys = []
        for k in keys_list:
            val = k["value"] or ""
            masked = "Not Configured"
            if k["id"] == "ollama":
                masked = "Local Service (HTTP)"
            elif val:
                masked = val[:8] + "..." + val[-6:] if len(val) > 14 else "********"
            
            formatted_keys.append({
                "id": k["id"],
                "name": k["name"],
                "masked": masked,
                "value": val
            })
            
        return {
            "keys": formatted_keys,
            "active_id": active_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/gemini-keys/test")
def test_specific_gemini_key(req: GeminiKeyTestRequest, username: str = Depends(verify_token)):
    if not req.key_value:
        return {"status": "error", "message": "Key value is empty."}
        
    # Check if this is an Ollama test
    if req.key_value == "http://localhost:11434" or req.key_value.startswith("http://localhost:"):
        try:
            import httpx
            res = httpx.get(f"{req.key_value}/api/tags", timeout=2.0)
            if res.status_code == 200:
                models = [m["name"] for m in res.json().get("models", [])]
                model_str = ", ".join(models)
                return {"status": "active", "message": f"Ollama is running! Models: {model_str or 'None'}"}
            return {"status": "invalid", "message": f"Ollama returned status {res.status_code}"}
        except Exception as e:
            return {"status": "invalid", "message": f"Ollama not running: {e}"}

    try:
        import google.generativeai as genai
        genai.configure(api_key=req.key_value)
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content("Hello. Reply with 'OK'.")
        if response.text:
            return {"status": "active", "message": "Key is active and working!"}
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
            return {"status": "limit_reached", "message": "API key works, but Rate Limit (429) / Quota is exceeded."}
        return {"status": "invalid", "message": f"Validation failed: {err_msg}"}
    return {"status": "invalid", "message": "Empty response from Gemini."}

@app.post("/api/settings/gemini-keys/select")
def select_active_gemini_key(req: GeminiKeySelectRequest, username: str = Depends(verify_token)):
    try:
        supabase = get_supabase_client()
        supabase.table("settings").upsert({
            "key": "active_gemini_key_id",
            "value": req.key_id,
            "is_encrypted": False
        }).execute()
        return {"success": True, "message": f"Gemini key '{req.key_id}' selected as primary for video generation."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save key selection: {e}")

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

# --- STATIC FRONTEND SERVING ---
FRONTEND_DIST = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    print(f"FastAPI: Serving compiled frontend from {FRONTEND_DIST}")
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    
    @app.get("/{catchall:path}")
    def serve_frontend(catchall: str):
        # Serve index.html for all non-api routes
        if catchall.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build missing index.html")
