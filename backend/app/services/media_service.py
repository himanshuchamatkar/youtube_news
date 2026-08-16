import os
import shutil
import random
from typing import Dict, Any, List
from backend.app.services.google_tts import TTSService
from backend.app.services.pexels_service import PexelsService
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
        
        self.temp_dir = "D:/youtube_news/media/temp"
        self.audio_dir = "D:/youtube_news/media/audio"
        self.chart_dir = "D:/youtube_news/media/charts"
        self.rendered_dir = "D:/youtube_news/media/rendered"
        
        # Ensure all directories exist
        for d in [self.temp_dir, self.audio_dir, self.chart_dir, self.rendered_dir]:
            os.makedirs(d, exist_ok=True)

    def generate_gradient_image(self, color1: tuple, color2: tuple, width: int, height: int, output_path: str):
        # Generates a smooth vertical gradient image for beautiful fallbacks
        base = Image.new("RGB", (width, height), color1)
        top = Image.new("RGB", (width, height), color2)
        mask = Image.new("L", (width, height))
        mask_draw = ImageDraw.Draw(mask)
        
        for y in range(height):
            # Proportional alpha
            alpha = int(255 * (y / height))
            mask_draw.line([(0, y), (width, y)], fill=alpha)
            
        gradient = Image.composite(top, base, mask)
        gradient.save(output_path)

    def get_fallback_clips(self, count: int) -> List[str]:
        # Generates beautiful colored gradient images as fallbacks
        paths = []
        gradients = [
            ((15, 32, 67), (44, 62, 80)),    # Deep Blue -> Navy
            ((24, 76, 120), (33, 47, 60)),   # Teal -> Dark Slate
            ((20, 20, 20), (50, 50, 50)),     # Slate -> Dark Grey
            ((40, 116, 101), (23, 32, 42)),  # Forest Green -> Black
            ((21, 67, 96), (28, 40, 51))     # Prussian Blue -> Charcoal
        ]
        
        for i in range(count):
            filename = f"fallback_grad_{i}.jpg"
            filepath = os.path.join(self.temp_dir, filename)
            c1, c2 = random.choice(gradients)
            self.generate_gradient_image(c1, c2, 1080, 1920, filepath)
            paths.append(filepath)
            
        return paths

    async def generate_video(self, article: Dict[str, Any], script_data: Dict[str, Any], job_id: str) -> str:
        # Define output file paths
        job_audio_path = os.path.join(self.audio_dir, f"narration_{job_id}.mp3")
        job_srt_path = os.path.join(self.temp_dir, f"subtitles_{job_id}.srt")
        
        headline_card_path = os.path.join(self.chart_dir, f"headline_{job_id}.png")
        chart_card_path = os.path.join(self.chart_dir, f"chart_{job_id}.png")
        badge_card_path = os.path.join(self.chart_dir, f"badge_{job_id}.png")
        
        final_video_path = os.path.join(self.rendered_dir, f"short_{job_id}.mp4")
        
        # 1. Synthesize Audio Narration
        script_text = script_data.get("script", "")
        await self.tts.generate_narration(script_text, job_audio_path)
        
        # Get exact audio duration
        duration = self.ffmpeg.get_audio_duration(job_audio_path)
        print(f"MediaService: Audio duration is {duration} seconds.")

        # 2. Generate Subtitles
        self.captions.generate_srt(script_text, duration, job_srt_path)

        # 3. Generate Visual Card Overlays
        title = script_data.get("title", article.get("title", ""))
        # Strip suffix for overlay visual presentation
        clean_headline = title.split(" | ")[0]
        company = article.get("company") or script_data.get("company", "N/A")
        sector = article.get("sector") or script_data.get("sector", "N/A")
        
        # Create headline card
        self.charts.generate_headline_card(clean_headline, company, sector, headline_card_path)
        
        # Create stock chart (Matplotlib)
        self.charts.generate_stock_chart(company if company != "N/A" else "Market Index", article.get("relevance_score", 85), chart_card_path)
        
        # Create mock percentage badge
        mock_pct = random.uniform(-6.0, 8.5)
        if mock_pct == 0.0:
            mock_pct = 2.5
        self.charts.generate_percentage_badge(mock_pct, badge_card_path)

        # 4. Search and download Pexels background visuals
        # Choose search keywords based on company / sector
        search_query = "stock market"
        if company and company != "N/A":
            search_query = f"{company} finance"
        elif sector and sector != "N/A":
            search_query = f"{sector} technology"
            
        print(f"MediaService: Fetching visuals for query: {search_query}")
        
        # Calculate how many 5-second clips we need
        clips_needed = int(duration // 5.0) + 2
        visuals = await self.pexels.search_and_download_videos(search_query, limit=clips_needed)
        
        # If no visuals downloaded, generate fallbacks
        if not visuals:
            print("MediaService: Pexels API returned zero results or key is missing. Using custom gradient background clips.")
            visuals = self.get_fallback_clips(clips_needed)

        # 5. Standardize all clips
        std_clips = []
        for i, path in enumerate(visuals):
            try:
                std_path = self.ffmpeg.standardize_clip(path, i, self.temp_dir, duration=5.0)
                std_clips.append(std_path)
            except Exception as e:
                print(f"MediaService: Failed to standardize clip {path}: {e}")

        if not std_clips:
            # Fallback if standardization failed
            fallbacks = self.get_fallback_clips(clips_needed)
            for i, path in enumerate(fallbacks):
                std_path = self.ffmpeg.standardize_clip(path, i, self.temp_dir, duration=5.0)
                std_clips.append(std_path)

        # 6. Concatenate background clips
        bg_video_path = os.path.join(self.temp_dir, f"concat_bg_{job_id}.mp4")
        self.ffmpeg.build_concatenated_video(std_clips, bg_video_path)

        # 7. Render final assembly
        try:
            self.ffmpeg.assemble_final_short(
                bg_video_path=bg_video_path,
                audio_path=job_audio_path,
                srt_path=job_srt_path,
                headline_card=headline_card_path,
                chart_card=chart_card_path,
                badge_card=badge_card_path,
                output_path=final_video_path
            )
        finally:
            # 8. Cleanup temporary files to save space
            print("MediaService: Cleaning up temporary assets...")
            temp_files = [bg_video_path] + std_clips
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

        print(f"MediaService: Rendering finished. Output short saved to {final_video_path}")
        return final_video_path
