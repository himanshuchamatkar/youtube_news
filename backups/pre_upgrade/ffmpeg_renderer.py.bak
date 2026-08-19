import os
import subprocess
import json
from typing import List, Dict, Any

class FFmpegRenderer:
    def __init__(self):
        pass

    def get_audio_duration(self, audio_path: str) -> float:
        # Use ffprobe to get the exact duration of the audio file
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"FFmpegRenderer: Failed to get audio duration: {e}")
            # Return a default fallback
            return 45.0

    def standardize_clip(self, input_path: str, index: int, output_dir: str, duration: float = 5.0) -> str:
        # Standardize video or image clip to 1080x1920, 30fps, H.264
        filename = f"std_clip_{index}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        is_image = input_path.lower().endswith(('.jpg', '.jpeg', '.png'))
        
        # FFmpeg command to scale (crop to fill) 1080x1920
        # "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        scale_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        
        if is_image:
            cmd = [
                "ffmpeg", "-y", "-nostdin", "-threads", "1", "-loop", "1", "-i", input_path,
                "-t", str(duration), "-r", "30", "-pix_fmt", "yuv420p",
                "-vf", scale_filter, "-c:v", "libx264", "-preset", "superfast", output_path
            ]
        else:
            # Strip audio from video and force standard format
            cmd = [
                "ffmpeg", "-y", "-nostdin", "-threads", "1", "-ss", "0", "-i", input_path,
                "-t", str(duration), "-r", "30", "-an", "-pix_fmt", "yuv420p",
                "-vf", scale_filter, "-c:v", "libx264", "-preset", "superfast", output_path
            ]
            
        import sys
        if sys.platform != "win32":
            cmd = ["nice", "-n", "19"] + cmd

        try:
            print(f"FFmpegRenderer: Standardizing clip {index}: {input_path} -> {output_path}")
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return output_path
        except Exception as e:
            print(f"FFmpegRenderer: Error standardizing clip {index}: {e}")
            raise e

    def build_concatenated_video(self, clip_paths: List[str], output_path: str) -> str:
        # Concatenate standardized video files using FFmpeg demuxer
        list_file_path = os.path.join(os.path.dirname(output_path), "concat_list.txt")
        
        with open(list_file_path, "w", encoding="utf-8") as f:
            for path in clip_paths:
                # FFmpeg concat file paths require forward slashes and escaped single quotes
                formatted_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{formatted_path}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file_path,
            "-c", "copy", output_path
        ]
        
        try:
            print(f"FFmpegRenderer: Concatenating {len(clip_paths)} clips into {output_path}...")
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            # Remove temporary list file
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
            return output_path
        except Exception as e:
            print(f"FFmpegRenderer: Concat failed: {e}")
            raise e

    def assemble_final_short(
        self,
        bg_video_path: str,
        audio_path: str,
        srt_path: str,
        headline_card: str,
        chart_card: str,
        badge_card: str,
        output_path: str
    ) -> str:
        # Get target duration from audio
        duration = self.get_audio_duration(audio_path)
        print(f"FFmpegRenderer: Assembling video. Duration = {duration}s")
        
        inputs = [
            "-i", bg_video_path,
            "-i", audio_path,
            "-i", headline_card
        ]
        
        # Watermark logo
        logo_path = "D:/youtube_news/logo/logo.png"
        inputs.append("-i")
        inputs.append(logo_path)
        logo_input_index = 3
        
        # CTA Subscribe overlay (Solid overlay, scaled to full-screen and placed before subtitles)
        cta_path = "D:/youtube_news/logo/cta_subscribe.jpg"
        inputs.append("-i")
        inputs.append(cta_path)
        cta_input_index = 4
        
        # Check optional overlays
        has_chart = os.path.exists(chart_card) if chart_card else False
        has_badge = os.path.exists(badge_card) if badge_card else False
        
        input_index = 5
        chart_input_index = -1
        if has_chart:
            # Use -itsoffset 15 to shift the chart animation timeline natively
            inputs.append("-itsoffset")
            inputs.append("15")
            inputs.append("-i")
            inputs.append(chart_card)
            chart_input_index = input_index
            input_index += 1
            
        badge_input_index = -1
        if has_badge:
            inputs.append("-i")
            inputs.append(badge_card)
            badge_input_index = input_index
            input_index += 1
            
        # Build filter complex overlay sequence:
        # 1. Scale logo watermark to 100x100 and overlay it top-right (x=920, y=40)
        # 2. Overlay headline card near top (x=60, y=120)
        filter_complex = f"[3:v] scale=100:100 [logo]; [0:v][2:v] overlay=60:120 [v1]; [v1][logo] overlay=920:40 [v2]"
        current_out = "v2"
        
        # 3. Overlay the delayed animated chart video below headline (x=40, y=420) from t=15 to 30
        if has_chart:
            filter_complex += f"; [{current_out}][{chart_input_index}:v] overlay=40:420:enable='between(t,15,30)' [v3]"
            current_out = "v3"
            
        # 4. Overlay the brand badge bottom-left (x=60, y=1450) from t=5 to 15
        if has_badge:
            filter_complex += f"; [{current_out}][{badge_input_index}:v] overlay=60:1450:enable='between(t,5,15)' [v4]"
            current_out = "v4"
            
        # 5. Scale the solid CTA image to full-screen 1080x1920 and overlay it during the last 3 seconds
        cta_start = max(0.0, duration - 3.0)
        filter_complex += f"; [4:v] scale=1080:1920 [cta_scaled]"
        filter_complex += f"; [{current_out}][cta_scaled] overlay=0:0:enable='between(t,{cta_start},{duration})' [v_cta]"
        current_out = "v_cta"
        
        # 6. Burn in subtitles as the final most front layer (Arial Bold, Yellow color, Outline, elevated with MarginV=130)
        srt_rel = os.path.basename(srt_path)
        srt_dir = os.path.dirname(srt_path)
        style = "Alignment=2,FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,MarginV=130"
        filter_complex += f"; [{current_out}] subtitles='{srt_rel}':force_style='{style}' [v_final]"
        
        # Assemble full command
        cmd = [
            "ffmpeg", "-y", "-nostdin", "-threads", "1",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v_final]",
            "-map", "1:a",
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "superfast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        import sys
        if sys.platform != "win32":
            cmd = ["nice", "-n", "19"] + cmd
            
        try:
            print("FFmpegRenderer: Rendering final short video...")
            subprocess.run(cmd, check=True, cwd=srt_dir)
            print(f"FFmpegRenderer: Video rendered successfully at {output_path}")
            return output_path
        except Exception as e:
            print(f"FFmpegRenderer: Failed to render final video: {e}")
            raise e
