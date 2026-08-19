import os
import re
from typing import List, Dict, Any

class CaptionGenerator:
    def __init__(self):
        pass

    def format_srt_time(self, seconds: float) -> str:
        # Convert float seconds to SRT time format: HH:MM:SS,mmm
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int(round((seconds % 1) * 1000))
        if msecs == 1000:
            msecs = 999
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

    def split_script_into_chunks(self, script_text: str) -> List[str]:
        # Clean text
        text = re.sub(r'\s+', ' ', script_text).strip()
        
        # Split by punctuation to get natural pause boundaries
        raw_segments = re.split(r'([.,;!?])', text)
        
        segments = []
        current = ""
        for part in raw_segments:
            if part in [".", ",", ";", "!", "?"]:
                current += part
                segments.append(current.strip())
                current = ""
            else:
                if current:
                    segments.append(current.strip())
                current = part
        if current:
            segments.append(current.strip())

        # Further break down chunks that are too long (> 5 words or > 25 characters)
        final_chunks = []
        for seg in segments:
            if not seg:
                continue
            words = seg.split()
            if len(words) <= 4:
                final_chunks.append(seg)
            else:
                # Group words into chunks of 3-4 words
                sub_chunk = []
                for w in words:
                    sub_chunk.append(w)
                    if len(sub_chunk) >= 3:
                        final_chunks.append(" ".join(sub_chunk))
                        sub_chunk = []
                if sub_chunk:
                    final_chunks.append(" ".join(sub_chunk))
                    
        return [c for c in final_chunks if c.strip()]

    def generate_srt(self, script_text: str, total_duration: float, output_srt_path: str) -> str:
        # Cap subtitle duration to end 3 seconds before video ends to avoid CTA overlaps
        subtitle_duration = max(0.0, total_duration - 3.0)
        print(f"CaptionGenerator: Generating SRT subtitles for {subtitle_duration}s (capped from {total_duration}s)...")
        chunks = self.split_script_into_chunks(script_text)
        
        if not chunks:
            # Fallback in case of empty list
            chunks = [script_text]

        # Calculate character lengths
        char_counts = [len(c) for c in chunks]
        total_chars = sum(char_counts)
        
        if total_chars == 0:
            total_chars = 1

        srt_lines = []
        current_time = 0.0

        for i, chunk in enumerate(chunks):
            # Proportional duration distribution
            chunk_duration = subtitle_duration * (len(chunk) / total_chars)
            
            start_str = self.format_srt_time(current_time)
            end_str = self.format_srt_time(current_time + chunk_duration)
            
            srt_lines.append(str(i + 1))
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(chunk)
            srt_lines.append("") # Empty line separator
            
            current_time += chunk_duration

        os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
            
        print(f"CaptionGenerator: Generated SRT file at {output_srt_path}")
        return output_srt_path
