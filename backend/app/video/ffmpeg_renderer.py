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
        
        # Build filter complex for overlays
        # Inputs: 
        # 0: bg_video
        # 1: audio (not used in filter complex, but merged in output)
        # 2: headline_card (always visible, x=40, y=120)
        # 3: chart_card (optional, visible between 15-30s, x=40, y=600)
        # 4: badge_card (optional, visible between 5-15s, x=380, y=600)
        
        filter_inputs = "[0:v][2:v]"
        overlay_steps = "overlay=40:120"
        current_out = "v1"
        
        inputs = [
            "-i", bg_video_path,
            "-i", audio_path,
            "-i", headline_card
        ]
        
        # Check optional overlays
        has_chart = os.path.exists(chart_card) if chart_card else False
        has_badge = os.path.exists(badge_card) if badge_card else False
        
        input_index = 3
        if has_chart:
            inputs.append("-i")
            inputs.append(chart_card)
            overlay_steps += f" [{current_out}]; [{current_out}][{input_index}:v] overlay=40:600:enable='between(t,15,30)'"
            current_out = f"v{input_index}"
            input_index += 1
            
        if has_badge:
            inputs.append("-i")
            inputs.append(badge_card)
            overlay_steps += f" [{current_out}]; [{current_out}][{input_index}:v] overlay=380:600:enable='between(t,5,15)'"
            current_out = f"v{input_index}"
            input_index += 1

        # Burn in subtitles
        # To avoid path formatting bugs in Windows, run the command in the directory containing the SRT file,
        # or format the path with forward slashes and escaped characters.
        srt_rel = os.path.basename(srt_path)
        srt_dir = os.path.dirname(srt_path)
        
        # Append subtitle step to filter complex
        # PrimaryColour hex format is AABBGGRR, so &H00FFFF is cyan/gold, &H00FFFFFF is white
        style = "Alignment=2,FontSize=18,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,MarginV=180"
        overlay_steps += f" [{current_out}]; [{current_out}] subtitles='{srt_rel}':force_style='{style}' [v_final]"

        # Assemble full command
        # Standardize output to 1080x1920, H264, AAC audio
        cmd = [
            "ffmpeg", "-y", "-nostdin", "-threads", "1",
            *inputs,
            "-filter_complex", f"{filter_inputs} {overlay_steps}",
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
        
        try:
            print("FFmpegRenderer: Rendering final short video...")
            # We change CWD to the directory containing the SRT file so FFmpeg can find the subtitle relative path cleanly on Windows!
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, cwd=srt_dir)
            print(f"FFmpegRenderer: Video rendered successfully at {output_path}")
            return output_path
        except Exception as e:
            print(f"FFmpegRenderer: Failed to render final video: {e}")
            raise e
