import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from typing import Dict, Any, List
from backend.app.core.config import settings

class YouTubeService:
    def __init__(self):
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.refresh_token = settings.YOUTUBE_REFRESH_TOKEN

    def _get_credentials(self) -> Credentials:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise ValueError("YouTube OAuth Client ID, Secret, and Refresh Token must be configured.")
        
        return Credentials(
            token=None, # Will refresh dynamically on request
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )

    def upload_short(self, video_path: str, title: str, description: str, tags: List[str], privacy_status: str = "public") -> Dict[str, Any]:
        print(f"YouTube Service: Starting video upload for {video_path}...")
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at {video_path}")
            
        creds = self._get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100], # Max 100 characters
                "description": description,
                "tags": tags,
                "categoryId": "25" # News & Politics category
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        # MediaFileUpload chunksize=-1 means simple upload (perfect for small Shorts videos < 100MB)
        media = MediaFileUpload(video_path, mimetype="video/mp4", chunksize=-1, resumable=True)

        try:
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"YouTube Service: Uploading... {int(status.progress() * 100)}% complete.")
                    
            video_id = response.get("id")
            youtube_url = f"https://youtu.be/{video_id}"
            print(f"YouTube Service: Upload success! Video ID: {video_id} | URL: {youtube_url}")
            
            return {
                "success": True,
                "video_id": video_id,
                "youtube_url": youtube_url
            }
        except Exception as e:
            print(f"YouTube Service: Video upload failed: {e}")
            raise e

    def fetch_channel_metrics(self) -> Dict[str, Any]:
        # Fetches aggregate subscriber count and videos by scraping public handle page
        try:
            import httpx
            import re
            url = "https://www.youtube.com/@himanshuChamatkar"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            r = httpx.get(url, headers=headers, timeout=3.0)
            if r.status_code != 200:
                return self._get_mock_metrics()
                
            sub_match = re.search(r'"subscriberCountText":\s*\{[^}]*"(?:simpleText|label)":\s*"([^"]+)"', r.text)
            sub_text = sub_match.group(1) if sub_match else ""
            if not sub_text:
                sub_matches = re.findall(r'"([0-9.,]+M?K? subscribers?)"', r.text)
                sub_text = sub_matches[0] if sub_matches else "0"
                
            video_match = re.search(r'"videoCountText":\s*\{[^}]*"(?:simpleText|label)":\s*"([^"]+)"', r.text)
            video_text = video_match.group(1) if video_match else ""
            if not video_text:
                video_matches = re.findall(r'"([0-9.,]+ videos?)"', r.text)
                video_text = video_matches[0] if video_matches else "0"

            sub_count = 0
            sub_clean = sub_text.lower().replace("subscribers", "").replace("subscriber", "").strip()
            if "m" in sub_clean:
                sub_count = int(float(sub_clean.replace("m", "")) * 1000000)
            elif "k" in sub_clean:
                sub_count = int(float(sub_clean.replace("k", "")) * 1000)
            else:
                try:
                    sub_count = int(sub_clean.replace(",", ""))
                except ValueError:
                    sub_count = 0
                    
            vid_count = 0
            vid_clean = video_text.lower().replace("videos", "").replace("video", "").strip()
            try:
                vid_count = int(vid_clean.replace(",", ""))
            except ValueError:
                vid_count = 0
                
            return {
                "subscriber_count": sub_count,
                "total_views": 0, # Will be summed from database
                "total_videos": vid_count,
                "total_likes": 0,
                "total_comments": 0,
                "success": True
            }
        except Exception as e:
            print(f"YouTube Service: Scraping channel metrics failed: {e}")
            return self._get_mock_metrics()

    def fetch_video_metrics(self, youtube_video_id: str) -> Dict[str, Any]:
        # Fetches views, likes, comments for a specific video by scraping the public watch page
        try:
            import httpx
            import re
            url = f"https://www.youtube.com/watch?v={youtube_video_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            r = httpx.get(url, headers=headers, timeout=3.0)
            if r.status_code != 200:
                return {"views": 0, "likes": 0, "comments": 0, "success": False}
                
            # Parse views
            view_match = re.search(r'"viewCount":\s*"([0-9]+)"', r.text)
            views = int(view_match.group(1)) if view_match else 0
            
            # Parse likes
            like_match = re.search(r'"likeCountText":\s*\{[^}]*"simpleText":\s*"([^"]+)"', r.text)
            like_text = like_match.group(1) if like_match else ""
            if not like_text:
                like_matches = re.findall(r'"([0-9,]+ likes?)"', r.text)
                like_text = like_matches[0] if like_matches else "0"
                
            likes = 0
            like_clean = like_text.lower().replace("likes", "").replace("like", "").replace(",", "").strip()
            try:
                if "k" in like_clean:
                    likes = int(float(like_clean.replace("k", "")) * 1000)
                elif "m" in like_clean:
                    likes = int(float(like_clean.replace("m", "")) * 1000000)
                else:
                    likes = int(like_clean)
            except ValueError:
                likes = 0
                
            return {
                "views": views,
                "likes": likes,
                "comments": 0,
                "success": True
            }
        except Exception as e:
            print(f"YouTube Service: Scraping video metrics failed for {youtube_video_id}: {e}")
            return {"views": 0, "likes": 0, "comments": 0, "success": False}

    def fetch_multiple_videos_metrics(self, video_ids: List[str]) -> Dict[str, Dict[str, int]]:
        res_dict = {}
        for vid_id in video_ids:
            metrics = self.fetch_video_metrics(vid_id)
            if metrics.get("success", False):
                res_dict[vid_id] = {
                    "views": metrics["views"],
                    "likes": metrics["likes"],
                    "comments": metrics["comments"]
                }
        return res_dict

    def _get_mock_metrics(self) -> Dict[str, Any]:
        return {
            "subscriber_count": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_videos": 0,
            "success": False
        }
