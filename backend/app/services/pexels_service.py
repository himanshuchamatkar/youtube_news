import httpx
import os
import random
from typing import List, Optional
from backend.app.core.config import settings

class PexelsService:
    def __init__(self):
        self.api_key = settings.PEXELS_API_KEY
        self.headers = {"Authorization": self.api_key} if self.api_key else {}

    async def search_and_download_videos(self, query: str, limit: int = 5, output_dir: Optional[str] = None) -> List[str]:
        if output_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            output_dir = os.path.join(base_dir, "media", "temp")

        if not self.api_key:
            print("Pexels Service: API Key not configured. Using fallback generation.")
            return []

        os.makedirs(output_dir, exist_ok=True)
        downloaded_paths = []
        
        # Search for portrait videos on Pexels
        url = "https://api.pexels.com/videos/search"
        params = {
            "query": query,
            "orientation": "portrait",
            "per_page": limit * 2, # Fetch more in case some links are broken
            "size": "medium"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code != 200:
                    print(f"Pexels Video Search returned status {response.status_code}")
                    # Fallback to search images
                    return await self.search_and_download_images(query, limit, output_dir)
                
                data = response.json()
                videos = data.get("videos", [])
                
                # Pick and download
                count = 0
                for v in videos:
                    if count >= limit:
                        break
                        
                    # Find a good quality video file (we want portrait, e.g. 1080x1920 or 720x1280)
                    video_files = v.get("video_files", [])
                    best_file_url = None
                    
                    # Sort files to find portrait files
                    for vf in video_files:
                        width = vf.get("width", 0)
                        height = vf.get("height", 0)
                        # Check if portrait orientation
                        if height > width:
                            # Prefer 1080p or 720p
                            if 720 <= width <= 1080:
                                best_file_url = vf.get("link")
                                break
                    
                    # If no portrait file found, take the first link
                    if not best_file_url and video_files:
                        best_file_url = video_files[0].get("link")
                        
                    if best_file_url:
                        # Download the video file
                        filename = f"pexels_video_{v.get('id')}_{count}.mp4"
                        filepath = os.path.join(output_dir, filename)
                        
                        try:
                            print(f"Pexels Service: Downloading video {best_file_url}...")
                            v_res = await client.get(best_file_url, follow_redirects=True)
                            if v_res.status_code == 200:
                                with open(filepath, "wb") as f:
                                    f.write(v_res.content)
                                downloaded_paths.append(filepath)
                                count += 1
                        except Exception as dl_err:
                            print(f"Pexels Service: Failed to download video file: {dl_err}")
                            
        except Exception as e:
            print(f"Pexels Service: Video search failed: {e}")
            
        # If we couldn't download enough videos, download images as fallback
        if len(downloaded_paths) < limit:
            fallback_images = await self.search_and_download_images(query, limit - len(downloaded_paths), output_dir)
            downloaded_paths.extend(fallback_images)
            
        return downloaded_paths

    async def search_and_download_images(self, query: str, limit: int = 5, output_dir: Optional[str] = None) -> List[str]:
        if output_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            output_dir = os.path.join(base_dir, "media", "temp")

        if not self.api_key:
            return []

        os.makedirs(output_dir, exist_ok=True)
        downloaded_paths = []
        url = "https://api.pexels.com/v1/search"
        params = {
            "query": query,
            "orientation": "portrait",
            "per_page": limit * 2
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code != 200:
                    print(f"Pexels Image Search returned status {response.status_code}")
                    return []
                    
                data = response.json()
                photos = data.get("photos", [])
                
                count = 0
                for p in photos:
                    if count >= limit:
                        break
                        
                    img_url = p.get("src", {}).get("portrait") or p.get("src", {}).get("large")
                    if img_url:
                        filename = f"pexels_photo_{p.get('id')}_{count}.jpg"
                        filepath = os.path.join(output_dir, filename)
                        
                        try:
                            print(f"Pexels Service: Downloading image {img_url}...")
                            img_res = await client.get(img_url, follow_redirects=True)
                            if img_res.status_code == 200:
                                with open(filepath, "wb") as f:
                                    f.write(img_res.content)
                                downloaded_paths.append(filepath)
                                count += 1
                        except Exception as dl_err:
                            print(f"Pexels Service: Failed to download photo: {dl_err}")
        except Exception as e:
            print(f"Pexels Service: Image search failed: {e}")
            
        return downloaded_paths
