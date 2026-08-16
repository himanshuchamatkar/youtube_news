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
        # Fetches aggregate subscriber count and views for the channel
        try:
            creds = self._get_credentials()
            youtube = build("youtube", "v3", credentials=creds)
            
            # Retrieve details of the authenticated user's channel
            # "mine=True" retrieves the channel associated with the OAuth credentials
            request = youtube.channels().list(
                part="statistics,snippet",
                mine=True
            )
            response = request.execute()
            
            if not response.get("items"):
                print("YouTube Service: No channel details returned.")
                return self._get_mock_metrics()
                
            stats = response["items"][0]["statistics"]
            
            return {
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "total_videos": int(stats.get("videoCount", 0)),
                "total_likes": 0,    # Channel-level likes are not in general channel statistics
                "total_comments": 0, # Channel-level comments are not in general channel statistics
                "success": True
            }
        except Exception as e:
            print(f"YouTube Service: Failed to fetch channel metrics: {e}. Returning mock / empty stats.")
            return self._get_mock_metrics()

    def fetch_video_metrics(self, youtube_video_id: str) -> Dict[str, Any]:
        # Fetches views, likes, comments for a specific video
        try:
            creds = self._get_credentials()
            youtube = build("youtube", "v3", credentials=creds)
            
            request = youtube.videos().list(
                part="statistics",
                id=youtube_video_id
            )
            response = request.execute()
            
            if not response.get("items"):
                print(f"YouTube Service: Video {youtube_video_id} not found.")
                return {"views": 0, "likes": 0, "comments": 0, "success": False}
                
            stats = response["items"][0]["statistics"]
            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "success": True
            }
        except Exception as e:
            print(f"YouTube Service: Failed to fetch video metrics for {youtube_video_id}: {e}")
            return {"views": 0, "likes": 0, "comments": 0, "success": False}

    def _get_mock_metrics(self) -> Dict[str, Any]:
        # Return structured mock data for fallback
        return {
            "subscriber_count": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_videos": 0,
            "success": False
        }
