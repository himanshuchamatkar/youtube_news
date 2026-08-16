import httpx
from datetime import datetime
from typing import List, Dict, Any
from backend.app.core.config import settings

class GNewsProvider:
    def __init__(self):
        self.api_key = settings.GNEWS_API_KEY
        self.base_url = "https://gnews.io/api/v4/search"

    async def fetch_articles(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            print("GNews API key not configured.")
            return []
            
        articles = []
        # Target Indian stock indices and market terms
        q = '("Nifty" OR "Sensex" OR "Indian stock market" OR "SEBI" OR "NSE" OR "BSE")'
        params = {
            "q": q,
            "lang": "en",
            "country": "in",
            "token": self.api_key,
            "max": 20
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                if response.status_code != 200:
                    print(f"GNews returned status {response.status_code}: {response.text}")
                    return []
                    
                data = response.json()
                raw_articles = data.get("articles", [])
                for item in raw_articles:
                    title = item.get("title", "") or ""
                    desc = item.get("description", "") or ""
                    url = item.get("url", "") or ""
                    
                    if not title or not url:
                        continue
                        
                    source_name = item.get("source", {}).get("name", "GNews")
                    published_at = item.get("publishedAt", datetime.utcnow().isoformat())

                    articles.append({
                        "title": title,
                        "description": desc,
                        "url": url,
                        "source": source_name,
                        "provider": "gnews",
                        "published_at": published_at,
                        "company": "",
                        "sector": "",
                        "country": "IN",
                        "raw_content": f"{title}\n{desc}\n{item.get('content', '')}"
                    })
        except Exception as e:
            print(f"Error fetching from GNews: {e}")
            
        return articles
