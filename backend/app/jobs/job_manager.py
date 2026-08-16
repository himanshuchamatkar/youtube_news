import os
import time
import traceback
import threading
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.supabase_client import get_supabase_client
from backend.app.services.news_engine import NewsEngine
from backend.app.services.gemini_service import GeminiService
from backend.app.services.media_service import MediaService
from backend.app.services.youtube_service import YouTubeService

class JobManager:
    def __init__(self):
        self.news_engine = NewsEngine()
        self.gemini = GeminiService()
        self.media = MediaService()
        self.youtube = YouTubeService()

    def log_stage(self, supabase: Any, job_id: str, stage: str, status: str, message: str, duration: float = 0.0, error: Optional[str] = None):
        # Writes verbose logs to job_logs table
        try:
            supabase.table("job_logs").insert({
                "job_id": job_id,
                "stage": stage,
                "status": status,
                "message": message,
                "duration": duration,
                "error": error
            }).execute()
        except Exception as e:
            print(f"JobManager: Failed to write job log: {e}")

    def update_job_progress(self, supabase: Any, job_id: str, status: str, progress: int, current_stage: str, error_message: Optional[str] = None):
        # Updates progress parameters in video_jobs table
        update_data = {
            "status": status,
            "progress": progress,
            "current_stage": current_stage
        }
        if status == "COMPLETED":
            update_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        if error_message:
            update_data["error_message"] = error_message

        try:
            supabase.table("video_jobs").update(update_data).eq("id", job_id).execute()
        except Exception as e:
            print(f"JobManager: Failed to update job status: {e}")

    def acquire_job_lock(self, supabase: Any, today_date: str, is_test: bool = False) -> str:
        # Tries to insert a job for today. Enforces date-level unique lock ONLY for production runs.
        try:
            if is_test:
                # In test mode, bypass unique locks and insert a test job
                res = supabase.table("video_jobs").insert({
                    "job_date": today_date,
                    "status": "RUNNING",
                    "progress": 0,
                    "current_stage": "initialized",
                    "is_test": True
                }).execute()
                if res.data:
                    return res.data[0]["id"]
                raise ValueError("Failed to create test job row.")

            # Check if there is already a completed or running production job
            res = supabase.table("video_jobs").select("*").eq("job_date", today_date).eq("is_test", False).execute()
            if res.data:
                existing_job = res.data[0]
                status = existing_job["status"]
                
                if status in ["RUNNING", "COMPLETED"]:
                    raise ValueError(f"Today's production job already exists with status: {status}")
                
                # If job exists but was FAILED or SKIPPED, allow retry
                if status in ["FAILED", "SKIPPED"]:
                    job_id = existing_job["id"]
                    # Reset existing job to RUNNING
                    supabase.table("video_jobs").update({
                        "status": "RUNNING",
                        "progress": 0,
                        "current_stage": "initialized",
                        "error_message": None,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "completed_at": None
                    }).eq("id", job_id).execute()
                    
                    return job_id

            # Insert new production job row
            res = supabase.table("video_jobs").insert({
                "job_date": today_date,
                "status": "RUNNING",
                "progress": 0,
                "current_stage": "initialized",
                "is_test": False
            }).execute()
            
            if res.data:
                return res.data[0]["id"]
            raise ValueError("Failed to create production job row.")
            
        except Exception as e:
            # Re-raise if it's our own error, else check for unique constraint violation
            if "already exists" in str(e):
                raise e
            # Check if unique constraint error
            if "duplicate key" in str(e) or "23505" in str(e):
                raise ValueError("Today's production video job is already in progress or completed.")
            raise e

    def run_daily_pipeline(self, job_id: str, is_test: bool = False):
        # Worker function executing the entire News -> Script -> Render -> Upload pipeline
        supabase = get_supabase_client()
        start_time = time.time()
        
        try:
            print(f"JobManager: Starting pipeline execution for Job {job_id} (Test Mode: {is_test})...")
            
            # --- STAGE 1: FETCHING NEWS ---
            self.update_job_progress(supabase, job_id, "FETCHING_NEWS", 10, "Fetching raw news")
            self.log_stage(supabase, job_id, "FETCHING_NEWS", "INFO", "Started news ingestion from all providers.")
            s1_start = time.time()
            
            # Run news engine
            loop = threading.Event()
            # Run async news fetching
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                articles = loop.run_until_complete(self.news_engine.get_daily_news(is_test=is_test))
            finally:
                loop.close()
                
            s1_dur = time.time() - s1_start
            
            # Fallback for Test Mode on weekends / holiday market closures
            if not articles and is_test:
                print("JobManager: Test Mode found 0 articles. Injecting a mock Indian Stock Market news story for end-to-end testing.")
                articles = [{
                    "title": "Tata Motors Profit Surges 15% as Q1 Net Profit Reaches Rs 3,200 Crore",
                    "description": "Tata Motors reported strong quarterly earnings with its consolidated net profit jumping 15 percent to Rs 3,200 crore for the first quarter, driven by margin improvements in its JLR segment and strong passenger car sales in India. Operational revenue grew by 9.4 percent to Rs 1,02,236 crore. Brokerages maintain a buy rating.",
                    "url": "https://www.moneycontrol.com/news/business/markets/tata-motors-q1-net-profit-jumps-15-percent-1234567.html",
                    "source": "Moneycontrol",
                    "provider": "rss",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "company": "Tata Motors",
                    "sector": "Automobile",
                    "country": "India",
                    "relevance_score": 95,
                    "status": "raw"
                }]

            # Write fetched articles to database
            for art in articles:
                try:
                    supabase.table("news_articles").upsert({
                        "title": art["title"],
                        "description": art["description"],
                        "url": art["url"],
                        "source": art["source"],
                        "provider": art["provider"],
                        "published_at": art["published_at"],
                        "company": art["company"],
                        "sector": art["sector"],
                        "country": art["country"],
                        "relevance_score": art["relevance_score"],
                        "status": "raw"
                    }, on_conflict="url").execute()
                except Exception as db_err:
                    print(f"JobManager: Failed to save raw article to DB: {db_err}")

            self.log_stage(supabase, job_id, "FETCHING_NEWS", "SUCCESS", f"Ingested {len(articles)} candidate articles above score 70.", duration=s1_dur)

            if not articles:
                self.update_job_progress(supabase, job_id, "SKIPPED", 100, "Skipped - No qualified news")
                self.log_stage(supabase, job_id, "COMPLETED", "WARNING", "No qualified Indian news articles found (NO_QUALIFIED_NEWS). Job skipped.")
                return

            # --- STAGE 2: ANALYZING & SELECTING WINNER ---
            self.update_job_progress(supabase, job_id, "ANALYZING", 30, "Selecting best story via Gemini")
            self.log_stage(supabase, job_id, "ANALYZING", "INFO", "Starting Gemini evaluations on top articles.")
            s2_start = time.time()
            
            winner_article = None
            winner_evaluation = None
            
            for candidate in articles[:5]:
                try:
                    db_art = supabase.table("news_articles").select("id").eq("url", candidate["url"]).execute()
                    candidate_id = db_art.data[0]["id"] if db_art.data else None
                    candidate["id"] = candidate_id
                    
                    eval_result = self.gemini.evaluate_article(candidate)
                    print(f"Gemini Eval Title: {candidate['title'][:40]} | Selected: {eval_result.selected} | Score: {eval_result.score}")
                    
                    if eval_result.selected and eval_result.category == "INDIAN_STOCK_MARKET" and not eval_result.needs_verification:
                        if winner_article is None or eval_result.score > winner_evaluation.score:
                            winner_article = candidate
                            winner_evaluation = eval_result
                except Exception as eval_err:
                    print(f"JobManager: Failed to evaluate candidate: {eval_err}")

            s2_dur = time.time() - s2_start

            if not winner_article:
                self.update_job_progress(supabase, job_id, "SKIPPED", 100, "Skipped - No article selected by AI")
                self.log_stage(supabase, job_id, "COMPLETED", "WARNING", "Gemini did not select any article as qualified. Job skipped.", duration=s2_dur)
                return

            # Update winner article status in DB
            supabase.table("news_articles").update({"status": "selected"}).eq("id", winner_article["id"]).execute()
            
            # Insert into daily_selections
            supabase.table("daily_selections").insert({
                "news_article_id": winner_article["id"],
                "score": winner_evaluation.score,
                "selection_reason": winner_evaluation.reason,
                "is_test": is_test
            }).execute()

            self.log_stage(
                supabase, job_id, "ANALYZING", "SUCCESS", 
                f"Selected winner article: '{winner_article['title'][:60]}...' | Company: {winner_evaluation.company} | Sector: {winner_evaluation.sector}", 
                duration=s2_dur
            )

            # --- STAGE 3: SCRIPT GENERATING ---
            self.update_job_progress(supabase, job_id, "SCRIPT_GENERATING", 45, "Generating Shorts script")
            s3_start = time.time()
            
            script_data = self.gemini.generate_script(winner_article)
            
            supabase.table("scripts").insert({
                "news_article_id": winner_article["id"],
                "script": script_data.script,
                "title": script_data.title,
                "description": script_data.description,
                "hashtags": script_data.hashtags,
                "model": self.gemini.model_name
            }).execute()
            
            s3_dur = time.time() - s3_start
            self.log_stage(supabase, job_id, "SCRIPT_GENERATING", "SUCCESS", f"Generated Short script. Title: '{script_data.title}'", duration=s3_dur)

            # --- STAGE 4: MEDIA GENERATING ---
            self.update_job_progress(supabase, job_id, "VISUAL_GENERATING", 60, "Generating voice, charts & rendering video")
            s4_start = time.time()
            
            script_dict = {
                "script": script_data.script,
                "title": script_data.title,
                "company": winner_evaluation.company,
                "sector": winner_evaluation.sector
            }
            
            loop2 = asyncio.new_event_loop()
            asyncio.set_event_loop(loop2)
            try:
                rendered_video_path = loop2.run_until_complete(
                    self.media.generate_video(winner_article, script_dict, job_id)
                )
            finally:
                loop2.close()
                
            s4_dur = time.time() - s4_start
            self.log_stage(supabase, job_id, "VISUAL_GENERATING", "SUCCESS", f"Assembled 1080x1920 Short video at {rendered_video_path}", duration=s4_dur)

            # --- STAGE 5: QUALITY CHECK ---
            self.update_job_progress(supabase, job_id, "QUALITY_CHECK", 80, "Running video quality validation")
            s5_start = time.time()
            
            if not os.path.exists(rendered_video_path):
                raise FileNotFoundError("Rendered video file is missing.")
                
            v_size = os.path.getsize(rendered_video_path)
            if v_size < 1024 * 1024:
                raise ValueError("Rendered video file size is too small.")
                
            v_duration = self.media.ffmpeg.get_audio_duration(rendered_video_path)
            if not (28.0 <= v_duration <= 65.0):
                raise ValueError(f"Video duration ({v_duration}s) is outside the allowed 30-60 second boundary.")
                
            s5_dur = time.time() - s5_start
            self.log_stage(supabase, job_id, "QUALITY_CHECK", "SUCCESS", f"Video passed quality checks. Duration: {v_duration:.2f}s | Size: {v_size/1024/1024:.2f}MB", duration=s5_dur)

            # --- STAGE 6: UPLOADING / LOCAL SAVE ---
            if is_test:
                self.update_job_progress(supabase, job_id, "COMPLETED", 100, "Completed successfully (Test Mode)")
                self.log_stage(supabase, job_id, "UPLOADING", "SUCCESS", "Test mode: skipped YouTube upload. Video saved locally.", duration=0)
                
                # Save video record to database
                local_url = f"http://localhost:8000/api/jobs/{job_id}/video"
                supabase.table("videos").insert({
                    "job_id": job_id,
                    "title": script_data.title,
                    "description": script_data.description,
                    "youtube_video_id": None,
                    "youtube_url": local_url,
                    "duration": int(v_duration),
                    "source_urls": [winner_article["url"]],
                    "status": "test"
                }).execute()
                
                total_dur = time.time() - start_time
                self.log_stage(supabase, job_id, "COMPLETED", "SUCCESS", f"Pipeline completed in {total_dur:.2f}s. Test Video ready for preview!", duration=total_dur)
            else:
                self.update_job_progress(supabase, job_id, "UPLOADING", 90, "Uploading Short to YouTube")
                s6_start = time.time()
                
                upload_res = self.youtube.upload_short(
                    video_path=rendered_video_path,
                    title=script_data.title,
                    description=f"{script_data.description}\n\nSources:\n- {winner_article.get('source')}\n\nDisclaimer: {script_data.disclaimer}",
                    tags=script_data.hashtags
                )
                
                supabase.table("videos").insert({
                    "job_id": job_id,
                    "title": script_data.title,
                    "description": script_data.description,
                    "youtube_video_id": upload_res["video_id"],
                    "youtube_url": upload_res["youtube_url"],
                    "duration": int(v_duration),
                    "source_urls": [winner_article["url"]],
                    "status": "uploaded"
                }).execute()

                s6_dur = time.time() - s6_start
                self.log_stage(supabase, job_id, "UPLOADING", "SUCCESS", f"Uploaded successfully to YouTube: {upload_res['youtube_url']}", duration=s6_dur)

                # Clean up rendered video only for production runs
                if os.path.exists(rendered_video_path):
                    try:
                        os.remove(rendered_video_path)
                        print("JobManager: Temporary rendered video deleted successfully.")
                    except Exception as del_err:
                        print(f"JobManager: Failed to delete final video file: {del_err}")

                total_dur = time.time() - start_time
                self.update_job_progress(supabase, job_id, "COMPLETED", 100, "Completed successfully")
                self.log_stage(supabase, job_id, "COMPLETED", "SUCCESS", f"Pipeline completed in {total_dur:.2f}s. YouTube Video published!", duration=total_dur)

        except Exception as e:
            trace = traceback.format_exc()
            print(f"JobManager: Critical Pipeline Failure:\n{trace}")
            
            total_dur = time.time() - start_time
            self.update_job_progress(supabase, job_id, "FAILED", 100, "Failed", error_message=str(e))
            self.log_stage(supabase, job_id, "COMPLETED", "FAILED", f"Pipeline failed: {e}", duration=total_dur, error=trace)

    def start_pipeline_job(self, is_test: bool = False) -> str:
        # Starts the job in a background thread
        supabase = get_supabase_client()
        today_str = date.today().isoformat()
        
        # 1. Acquire lock
        job_id = self.acquire_job_lock(supabase, today_str, is_test)
        
        # 2. Run background thread
        thread = threading.Thread(target=self.run_daily_pipeline, args=(job_id, is_test))
        thread.daemon = True
        thread.start()
        
        return job_id
