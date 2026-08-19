"""
Caption / Subtitle generator for finance news shorts.
Uses word-level timestamps from Edge-TTS for accurate synchronization.
Falls back to proportional estimation if timestamps are unavailable.
"""
import os
import re
from typing import List, Dict, Any, Optional


class CaptionGenerator:
    def __init__(self):
        pass

    def format_srt_time(self, seconds: float) -> str:
        """Convert float seconds to SRT time format: HH:MM:SS,mmm"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int(round((seconds % 1) * 1000))
        if msecs == 1000:
            msecs = 999
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

    def group_words_into_chunks(self, word_timestamps: List[Dict], words_per_chunk: int = 4) -> List[Dict]:
        """
        Group word-level timestamps into subtitle chunks of N words.
        Returns list of {text, start_s, end_s}.
        """
        chunks = []
        current_words = []
        chunk_start = 0.0
        
        for i, wt in enumerate(word_timestamps):
            if not current_words:
                chunk_start = wt["start_ms"] / 1000.0
            
            current_words.append(wt["text"])
            
            # Determine if we should break here
            should_break = False
            word_text = wt["text"].strip()
            
            # Break on punctuation (natural pause points)
            if word_text.endswith(('.', '!', '?', ';')):
                should_break = True
            # Break on comma if we have enough words
            elif word_text.endswith(',') and len(current_words) >= 3:
                should_break = True
            # Break on word count limit
            elif len(current_words) >= words_per_chunk:
                should_break = True
            # Break on last word
            elif i == len(word_timestamps) - 1:
                should_break = True
            
            if should_break and current_words:
                chunk_end = wt["end_ms"] / 1000.0
                chunks.append({
                    "text": " ".join(current_words),
                    "start_s": chunk_start,
                    "end_s": chunk_end
                })
                current_words = []
        
        return chunks

    def generate_srt_from_timestamps(self, word_timestamps: List[Dict], total_duration: float, output_srt_path: str) -> str:
        """
        Generate SRT subtitles using actual word-level timestamps from TTS engine.
        This produces properly synchronized captions.
        """
        # Cap subtitle duration to end 3 seconds before video ends (CTA window)
        cta_window = 3.0
        subtitle_end = max(0.0, total_duration - cta_window)
        
        print(f"CaptionGenerator: Generating synchronized SRT from {len(word_timestamps)} word timestamps...")
        print(f"CaptionGenerator: Subtitle window: 0.0s to {subtitle_end:.1f}s (CTA starts at {subtitle_end:.1f}s)")
        
        # Group words into readable subtitle chunks
        chunks = self.group_words_into_chunks(word_timestamps, words_per_chunk=4)
        
        # Filter out chunks that extend into the CTA window
        chunks = [c for c in chunks if c["start_s"] < subtitle_end]
        
        # Trim the last chunk's end time if needed
        if chunks and chunks[-1]["end_s"] > subtitle_end:
            chunks[-1]["end_s"] = subtitle_end
        
        srt_lines = []
        for i, chunk in enumerate(chunks):
            start_str = self.format_srt_time(chunk["start_s"])
            end_str = self.format_srt_time(chunk["end_s"])
            
            srt_lines.append(str(i + 1))
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(chunk["text"])
            srt_lines.append("")  # Empty line separator
        
        os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        
        print(f"CaptionGenerator: Generated {len(chunks)} synchronized subtitle entries at {output_srt_path}")
        return output_srt_path

    def split_script_into_chunks(self, script_text: str) -> List[str]:
        """Split script text into readable chunks for proportional timing fallback."""
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

    def generate_srt_from_sentence_timestamps(self, timestamps: List[Dict], total_duration: float, output_srt_path: str) -> str:
        """
        Generate SRT subtitles using sentence boundary timestamps.
        Each sentence is split proportionally into 3-4 word chunks within its specific timeframe.
        """
        cta_window = 3.0
        subtitle_end = max(0.0, total_duration - cta_window)
        
        print(f"CaptionGenerator: Generating synchronized SRT from {len(timestamps)} sentence boundaries...")
        
        chunks = []
        for ts in timestamps:
            text = ts["text"].strip()
            start_s = ts["start_ms"] / 1000.0
            end_s = ts["end_ms"] / 1000.0
            
            # Skip if sentence starts inside the CTA window
            if start_s >= subtitle_end:
                continue
                
            # Cap end_s to subtitle_end
            if end_s > subtitle_end:
                end_s = subtitle_end
                
            words = text.split()
            if len(words) <= 4:
                chunks.append({
                    "text": text,
                    "start_s": start_s,
                    "end_s": end_s
                })
            else:
                # Split sentence into 3-4 word sub-chunks, distributing duration proportionally
                sub_chunks_count = (len(words) - 1) // 4 + 1
                words_per_sub = (len(words) + sub_chunks_count - 1) // sub_chunks_count
                
                sub_words_list = [words[i:i + words_per_sub] for i in range(0, len(words), words_per_sub)]
                
                # Calculate total characters in sentence for proportional timing
                total_chars = sum(len(" ".join(sw)) for sw in sub_words_list)
                if total_chars == 0:
                    total_chars = 1
                    
                sentence_duration = end_s - start_s
                current_start = start_s
                
                for sw in sub_words_list:
                    sub_text = " ".join(sw)
                    sub_duration = sentence_duration * (len(sub_text) / total_chars)
                    chunks.append({
                        "text": sub_text,
                        "start_s": current_start,
                        "end_s": min(current_start + sub_duration, end_s)
                    })
                    current_start += sub_duration
                    
        # Trim final chunk if it overlaps CTA
        if chunks and chunks[-1]["end_s"] > subtitle_end:
            chunks[-1]["end_s"] = subtitle_end
            
        srt_lines = []
        for i, chunk in enumerate(chunks):
            start_str = self.format_srt_time(chunk["start_s"])
            end_str = self.format_srt_time(chunk["end_s"])
            
            srt_lines.append(str(i + 1))
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(chunk["text"])
            srt_lines.append("")
            
        os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
            
        print(f"CaptionGenerator: Generated {len(chunks)} sentence-aligned subtitle entries at {output_srt_path}")
        return output_srt_path

    def generate_srt(self, script_text: str, total_duration: float, output_srt_path: str, word_timestamps: Optional[List[Dict]] = None) -> str:
        """
        Generate SRT subtitle file.
        If word_timestamps are provided, uses them for accurate timing.
        Otherwise, falls back to proportional character-based estimation.
        """
        if word_timestamps:
            # Check for sentence boundary timestamps first
            sentence_ts = [t for t in word_timestamps if t.get("type") == "SentenceBoundary"]
            if sentence_ts:
                return self.generate_srt_from_sentence_timestamps(sentence_ts, total_duration, output_srt_path)
            
            # If word-level boundaries are available
            word_ts = [t for t in word_timestamps if t.get("type") != "SentenceBoundary"]
            if len(word_ts) > 5:
                return self.generate_srt_from_timestamps(word_ts, total_duration, output_srt_path)
        
        # Fallback: proportional timing based on character count
        print(f"CaptionGenerator: No word timestamps available. Using proportional timing fallback.")
        
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
            srt_lines.append("")  # Empty line separator
            
            current_time += chunk_duration

        os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
            
        print(f"CaptionGenerator: Generated SRT file at {output_srt_path}")
        return output_srt_path
