"""
Professional FFmpeg video composition engine for finance news shorts.
Supports multi-card sequencing, dynamic timing, and smooth transitions.
All timings are derived from actual audio duration — never hardcoded.
"""
import os
import subprocess
import json
from typing import List, Dict, Any, Optional


class FFmpegRenderer:
    def __init__(self):
        # Use relative paths from project root
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.logo_path = os.path.join(self.base_dir, "logo", "logo.png")
        self.cta_path = os.path.join(self.base_dir, "logo", "cta_subscribe.jpg")

    def get_audio_duration(self, audio_path: str) -> float:
        """Use ffprobe to get the exact duration of the audio file."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"FFmpegRenderer: Failed to get audio duration: {e}")
            return 45.0

    def standardize_clip(self, input_path: str, index: int, output_dir: str, duration: float = 5.0) -> str:
        """Standardize video or image clip to 1080x1920, 30fps, H.264."""
        filename = f"std_clip_{index}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        is_image = input_path.lower().endswith(('.jpg', '.jpeg', '.png'))
        scale_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        
        if is_image:
            cmd = [
                "ffmpeg", "-y", "-nostdin", "-threads", "1", "-loop", "1", "-i", input_path,
                "-t", str(duration), "-r", "30", "-pix_fmt", "yuv420p",
                "-vf", scale_filter, "-c:v", "libx264", "-preset", "superfast", output_path
            ]
        else:
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
        """Concatenate standardized video files using FFmpeg demuxer."""
        list_file_path = os.path.join(os.path.dirname(output_path), "concat_list.txt")
        
        with open(list_file_path, "w", encoding="utf-8") as f:
            for path in clip_paths:
                formatted_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{formatted_path}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file_path,
            "-c", "copy", output_path
        ]
        
        try:
            print(f"FFmpegRenderer: Concatenating {len(clip_paths)} clips into {output_path}...")
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
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
        output_path: str,
        metric_cards: Optional[List[str]] = None
    ) -> str:
        """
        Assemble the final short video with professional multi-card sequencing.
        All timings are computed dynamically from the actual audio duration.
        """
        # Get target duration from audio
        duration = self.get_audio_duration(audio_path)
        print(f"FFmpegRenderer: Assembling video. Total Duration = {duration}s")
        
        # === COMPUTE DYNAMIC TIMING ===
        # CTA window: last 3 seconds
        cta_start = max(0.0, duration - 3.0)
        
        # Content window: everything before CTA
        content_duration = cta_start
        
        # Headline: first 20% of content
        headline_start = 0.0
        headline_end = min(content_duration * 0.2, 8.0)
        
        # Chart: 25% to 55% of content
        chart_start = content_duration * 0.25
        chart_end = min(content_duration * 0.55, chart_start + 12.0)
        
        # Badge: 15% to 35% of content (overlaps briefly with headline and chart)
        badge_start = content_duration * 0.15
        badge_end = min(content_duration * 0.35, badge_start + 10.0)
        
        # Metric cards: distributed evenly through 40%-90% of content
        metric_slots = []
        if metric_cards:
            n_metrics = len(metric_cards)
            metric_zone_start = content_duration * 0.40
            metric_zone_end = content_duration * 0.90
            metric_zone_dur = metric_zone_end - metric_zone_start
            slot_dur = metric_zone_dur / max(n_metrics, 1)
            
            for i in range(n_metrics):
                m_start = metric_zone_start + i * slot_dur
                m_end = m_start + slot_dur
                metric_slots.append((m_start, m_end))
        
        print(f"FFmpegRenderer: Timing plan:")
        print(f"  Headline: {headline_start:.1f}s - {headline_end:.1f}s")
        print(f"  Badge:    {badge_start:.1f}s - {badge_end:.1f}s")
        print(f"  Chart:    {chart_start:.1f}s - {chart_end:.1f}s")
        for i, (ms, me) in enumerate(metric_slots):
            print(f"  Metric {i}: {ms:.1f}s - {me:.1f}s")
        print(f"  CTA:      {cta_start:.1f}s - {duration:.1f}s")
        
        # === BUILD INPUT LIST ===
        inputs = [
            "-i", bg_video_path,      # [0] Background video
            "-i", audio_path,          # [1] Audio narration
            "-i", headline_card,       # [2] Headline card image
        ]
        
        # Logo watermark [3]
        inputs.extend(["-i", self.logo_path])
        logo_idx = 3
        
        # CTA overlay [4]
        inputs.extend(["-i", self.cta_path])
        cta_idx = 4
        
        next_idx = 5
        
        # Chart video (with time offset for animated start)
        has_chart = os.path.exists(chart_card) if chart_card else False
        chart_idx = -1
        if has_chart:
            inputs.extend(["-itsoffset", str(chart_start), "-i", chart_card])
            chart_idx = next_idx
            next_idx += 1
        
        # Badge image
        has_badge = os.path.exists(badge_card) if badge_card else False
        badge_idx = -1
        if has_badge:
            inputs.extend(["-i", badge_card])
            badge_idx = next_idx
            next_idx += 1
        
        # Metric card images
        metric_indices = []
        if metric_cards:
            for mc_path in metric_cards:
                if os.path.exists(mc_path):
                    inputs.extend(["-i", mc_path])
                    metric_indices.append(next_idx)
                    next_idx += 1
        
        # === BUILD FILTER COMPLEX ===
        filters = []
        current_out = "v0"
        
        # 1. Scale logo to 120x120 (slightly larger, professional)
        filters.append(f"[{logo_idx}:v] scale=120:120 [logo]")
        
        # 2. Overlay headline card with fade-in at top (x=60, y=100)
        filters.append(f"[2:v] format=rgba,fade=in:st=0:d=0.5:alpha=1,fade=out:st={headline_end-0.5}:d=0.5:alpha=1 [headline_f]")
        filters.append(f"[0:v][headline_f] overlay=60:100:enable='between(t,{headline_start},{headline_end})' [{current_out}]")
        
        # 3. Overlay logo (top-right, subtle, always visible before CTA)
        prev_out = current_out
        current_out = "v1"
        filters.append(f"[{prev_out}][logo] overlay=920:40:enable='lt(t,{cta_start})' [{current_out}]")
        
        # 4. Overlay badge (bottom-left area) with fade
        if has_badge:
            prev_out = current_out
            current_out = "v2"
            filters.append(f"[{badge_idx}:v] format=rgba,fade=in:st=0:d=0.3:alpha=1,fade=out:st={badge_end-badge_start-0.3}:d=0.3:alpha=1 [badge_f]")
            filters.append(f"[{prev_out}][badge_f] overlay=60:1400:enable='between(t,{badge_start},{badge_end})' [{current_out}]")
        
        # 5. Overlay animated chart (center zone, x=40, y=500)
        if has_chart:
            prev_out = current_out
            current_out = "v3"
            filters.append(f"[{chart_idx}:v] format=rgba [chart_f]")
            filters.append(f"[{prev_out}][chart_f] overlay=40:500:enable='between(t,{chart_start},{chart_end})' [{current_out}]")
        
        # 6. Overlay metric cards in sequence (center, x=90, y=700)
        for i, m_idx in enumerate(metric_indices):
            if i < len(metric_slots):
                ms, me = metric_slots[i]
                prev_out = current_out
                current_out = f"vm{i}"
                # Fade in/out for each metric card
                fade_dur = min(0.4, (me - ms) * 0.15)
                filters.append(f"[{m_idx}:v] format=rgba,fade=in:st=0:d={fade_dur}:alpha=1,fade=out:st={me-ms-fade_dur}:d={fade_dur}:alpha=1 [mc{i}_f]")
                filters.append(f"[{prev_out}][mc{i}_f] overlay=90:750:enable='between(t,{ms},{me})' [{current_out}]")
        
        # 7. Scale and overlay CTA during final 3 seconds (full-screen)
        prev_out = current_out
        current_out = "v_cta"
        filters.append(f"[{cta_idx}:v] scale=1080:1920 [cta_scaled]")
        filters.append(f"[{prev_out}][cta_scaled] overlay=0:0:enable='between(t,{cta_start},{duration})' [{current_out}]")
        
        # 8. Burn in subtitles as the topmost layer
        srt_rel = os.path.basename(srt_path)
        srt_dir = os.path.dirname(srt_path)
        # Professional subtitle style: large white text with black outline, positioned in lower third
        style = "Alignment=2,FontName=Arial,FontSize=24,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=2,MarginV=180"
        
        prev_out = current_out
        current_out = "v_final"
        filters.append(f"[{prev_out}] subtitles='{srt_rel}':force_style='{style}' [{current_out}]")
        
        filter_complex = "; ".join(filters)
        
        # === ASSEMBLE COMMAND ===
        cmd = [
            "ffmpeg", "-y", "-nostdin", "-threads", "1",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current_out}]",
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
            print("FFmpegRenderer: Rendering final short video with multi-card composition...")
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                cwd=srt_dir
            )
            if result.returncode != 0:
                error_msg = f"FFmpeg exited with code {result.returncode}.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
                print(f"FFmpegRenderer Error: {error_msg}")
                raise RuntimeError(error_msg)
            print(f"FFmpegRenderer: Video rendered successfully at {output_path}")
            return output_path
        except Exception as e:
            print(f"FFmpegRenderer: Failed to render final video: {e}")
            raise e
