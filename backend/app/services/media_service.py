"""
Media orchestration service.
Coordinates TTS, financial data extraction, chart generation, caption synchronization,
and FFmpeg composition into the final video output.
"""
import os
import shutil
import random
from typing import Dict, Any, List
from backend.app.services.google_tts import TTSService
from backend.app.services.pexels_service import PexelsService
from backend.app.services.financial_extractor import FinancialExtractor
from backend.app.video.chart_generator import ChartGenerator
from backend.app.video.caption_generator import CaptionGenerator
from backend.app.video.ffmpeg_renderer import FFmpegRenderer
from PIL import Image, ImageDraw


class MediaService:
    def __init__(self):
        self.tts = TTSService()
        self.pexels = PexelsService()
        self.charts = ChartGenerator()
        self.captions = CaptionGenerator()
        self.ffmpeg = FFmpegRenderer()
        self.extractor = FinancialExtractor()
        
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.temp_dir = os.path.join(base_dir, "media", "temp")
        self.audio_dir = os.path.join(base_dir, "media", "audio")
        self.chart_dir = os.path.join(base_dir, "media", "charts")
        self.rendered_dir = os.path.join(base_dir, "media", "rendered")
        
        # Ensure all directories exist
        for d in [self.temp_dir, self.audio_dir, self.chart_dir, self.rendered_dir]:
            os.makedirs(d, exist_ok=True)

    def generate_gradient_image(self, color1: tuple, color2: tuple, width: int, height: int, output_path: str):
        """Generates a smooth vertical gradient image for beautiful fallbacks."""
        base = Image.new("RGB", (width, height), color1)
        top = Image.new("RGB", (width, height), color2)
        mask = Image.new("L", (width, height))
        mask_draw = ImageDraw.Draw(mask)
        
        for y in range(height):
            alpha = int(255 * (y / height))
            mask_draw.line([(0, y), (width, y)], fill=alpha)
            
        gradient = Image.composite(top, base, mask)
        gradient.save(output_path)

    def get_fallback_clips(self, count: int) -> List[str]:
        """Generates beautiful colored gradient images as fallbacks."""
        paths = []
        gradients = [
            ((10, 18, 36), (24, 44, 68)),     # Deep Navy gradient
            ((8, 24, 48), (16, 36, 64)),       # Dark Blue
            ((12, 16, 28), (28, 40, 56)),      # Charcoal Navy
            ((6, 20, 40), (20, 48, 72)),       # Ocean Blue
            ((14, 22, 38), (32, 52, 76))       # Steel Blue
        ]
        
        for i in range(count):
            filename = f"fallback_grad_{i}.jpg"
            filepath = os.path.join(self.temp_dir, filename)
            c1, c2 = gradients[i % len(gradients)]
            self.generate_gradient_image(c1, c2, 1080, 1920, filepath)
            paths.append(filepath)
            
        return paths

    async def generate_video(self, article: Dict[str, Any], script_data: Dict[str, Any], job_id: str, stage_callback: Any = None) -> str:
        """
        Full video generation pipeline:
        1. Extract financial data from article
        2. Generate TTS audio with word-level timestamps
        3. Generate synchronized captions
        4. Generate data-driven visual overlays
        5. Fetch/generate background visuals
        6. Compose final video with FFmpeg
        """
        import time

        # Define output file paths
        job_audio_path = os.path.join(self.audio_dir, f"narration_{job_id}.mp3")
        job_srt_path = os.path.join(self.temp_dir, f"subtitles_{job_id}.srt")
        
        headline_card_path = os.path.join(self.chart_dir, f"headline_{job_id}.png")
        chart_card_path = os.path.join(self.chart_dir, f"chart_{job_id}.mp4")
        badge_card_path = os.path.join(self.chart_dir, f"badge_{job_id}.png")
        
        final_video_path = os.path.join(self.rendered_dir, f"short_{job_id}.mp4")
        
        # === STEP 1: Extract Financial Data ===
        print("MediaService: Extracting financial data from article...")
        financial_data = self.extractor.extract(article)
        print(f"MediaService: Extracted data - Company: {financial_data.company_name}, "
              f"Type: {financial_data.headline_type}, "
              f"Change: {financial_data.price_change_pct}, "
              f"Figures: {len(financial_data.key_figures)}")
        
        # === STEP 2: Generate TTS Audio with Timestamps ===
        script_text = script_data.get("script", "")
        print("MediaService: Generating TTS audio with word-level timestamps...")
        t_audio_start = time.time()
        if stage_callback:
            stage_callback("GENERATING_AUDIO", "INFO", "Synthesizing narration audio with neural voice...")
        
        try:
            audio_path, word_timestamps = await self.tts.generate_narration_with_timestamps(
                script_text, job_audio_path
            )
            print(f"MediaService: Got {len(word_timestamps)} word timestamps from TTS")
        except Exception as tts_err:
            print(f"MediaService: Timestamp TTS failed, falling back: {tts_err}")
            await self.tts.generate_narration(script_text, job_audio_path)
            word_timestamps = []
        
        # Get exact audio duration
        duration = self.ffmpeg.get_audio_duration(job_audio_path)
        print(f"MediaService: Audio duration is {duration} seconds.")

        # === STEP 3: Generate Synchronized Captions ===
        print("MediaService: Generating synchronized captions...")
        self.captions.generate_srt(
            script_text, duration, job_srt_path,
            word_timestamps=word_timestamps
        )
        t_audio_dur = time.time() - t_audio_start
        if stage_callback:
            stage_callback("GENERATING_AUDIO", "SUCCESS", f"Generated narration ({duration:.1f}s) & sync captions", duration=t_audio_dur)

        # === STEP 4: Generate Data-Driven Visual Overlays ===
        t_vis_start = time.time()
        if stage_callback:
            stage_callback("GENERATING_VISUALS", "INFO", "Creating dynamic financial charts and visual cards...")

        title = script_data.get("title", article.get("title", ""))
        clean_headline = title.split(" | ")[0]
        company = financial_data.company_name or article.get("company") or script_data.get("company", "N/A")
        sector = article.get("sector") or script_data.get("sector", "N/A")
        
        # Create headline card with extracted data
        self.charts.generate_headline_card(
            headline=financial_data.short_headline or clean_headline,
            company=company,
            sector=sector,
            output_path=headline_card_path,
            price_change=financial_data.price_change_pct,
            headline_type=financial_data.headline_type
        )
        
        # Create data-driven stock chart (uses actual percentage, not random)
        self.charts.generate_stock_chart(
            company if company != "N/A" else "Market Index",
            financial_data.price_change_pct,
            chart_card_path
        )
        
        # Create percentage badge from actual extracted data
        badge_value = financial_data.price_change_pct
        if not badge_value:
            # Use first key figure's change if available
            for fig in financial_data.key_figures:
                if fig.change:
                    badge_value = fig.change
                    break
        
        if badge_value:
            self.charts.generate_percentage_badge(badge_value, badge_card_path)
        else:
            # Generate a clean info badge instead of a random percentage
            self.charts.generate_percentage_badge("0%", badge_card_path)
        
        # Generate metric card sequence from extracted figures
        metric_card_paths = self.charts.generate_data_card_sequence(
            financial_data, self.chart_dir, job_id
        )
        print(f"MediaService: Generated {len(metric_card_paths)} metric cards from extracted data")

        # === STEP 5: Background Visuals ===
        search_query = "stock market"
        if company and company not in ["N/A", "Market"]:
            search_query = f"{company} finance"
        elif sector and sector != "N/A":
            search_query = f"{sector} technology"
            
        print(f"MediaService: Fetching visuals for query: {search_query}")
        
        clip_dur = 15.0
        clips_needed = int(duration // clip_dur) + 1
        visuals = await self.pexels.search_and_download_videos(search_query, limit=clips_needed, output_dir=self.temp_dir)
        
        if not visuals:
            print("MediaService: Pexels API returned zero results. Using custom gradient backgrounds.")
            visuals = self.get_fallback_clips(clips_needed)

        # === STEP 6: Standardize Clips ===
        std_clips = []
        for i, path in enumerate(visuals):
            try:
                std_path = self.ffmpeg.standardize_clip(path, i, self.temp_dir, duration=clip_dur)
                std_clips.append(std_path)
            except Exception as e:
                print(f"MediaService: Failed to standardize clip {path}: {e}")

        if not std_clips:
            fallbacks = self.get_fallback_clips(clips_needed)
            for i, path in enumerate(fallbacks):
                std_path = self.ffmpeg.standardize_clip(path, i, self.temp_dir, duration=clip_dur)
                std_clips.append(std_path)

        # === STEP 7: Concatenate Background ===
        bg_video_path = os.path.join(self.temp_dir, f"concat_bg_{job_id}.mp4")
        self.ffmpeg.build_concatenated_video(std_clips, bg_video_path)

        t_vis_dur = time.time() - t_vis_start
        if stage_callback:
            stage_callback("GENERATING_VISUALS", "SUCCESS", f"Generated financial cards and {len(std_clips)} background clips", duration=t_vis_dur)

        # === STEP 8: Final Composition ===
        t_rend_start = time.time()
        if stage_callback:
            stage_callback("RENDERING", "INFO", "Compositing video layers and burning subtitles with FFmpeg...")

        try:
            self.ffmpeg.assemble_final_short(
                bg_video_path=bg_video_path,
                audio_path=job_audio_path,
                srt_path=job_srt_path,
                headline_card=headline_card_path,
                chart_card=chart_card_path,
                badge_card=badge_card_path,
                output_path=final_video_path,
                metric_cards=metric_card_paths
            )
            t_rend_dur = time.time() - t_rend_start
            if stage_callback:
                stage_callback("RENDERING", "SUCCESS", f"Assembled 1080x1920 Short video at {final_video_path}", duration=t_rend_dur)
        finally:
            # === STEP 9: Cleanup Temporary Files ===
            print("MediaService: Cleaning up temporary assets...")
            temp_files = [bg_video_path] + std_clips
            
            # Add metric card temp files
            temp_files.extend(metric_card_paths)
            
            for f in temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as clean_err:
                        print(f"MediaService: Failed to delete temp file {f}: {clean_err}")
            
            # Clean pexels downloads
            for p in visuals:
                if p.startswith(self.temp_dir) and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            
            # Clean fallback gradient images
            for f in os.listdir(self.temp_dir):
                if f.startswith("fallback_grad_"):
                    try:
                        os.remove(os.path.join(self.temp_dir, f))
                    except Exception:
                        pass

        print(f"MediaService: Rendering finished. Output short saved to {final_video_path}")
        return final_video_path
