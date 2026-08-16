import httpx
from datetime import datetime
from typing import List, Dict, Any
from backend.app.core.config import settings

class FinnhubProvider:
    def __init__(self):
        self.api_key = settings.FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1/news"

    async def fetch_articles(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            print("Finnhub API key not configured.")
            return []
            
        articles = []
        params = {
            "category": "general",
            "token": self.api_key
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                if response.status_code != 200:
                    print(f"Finnhub returned status {response.status_code}: {response.text}")
                    return []
                    
                raw_articles = response.json()
                if not isinstance(raw_articles, list):
                    print(f"Finnhub response is not a list: {raw_articles}")
                    return []
                    
                for item in raw_articles:
                    title = item.get("headline", "") or ""
                    desc = item.get("summary", "") or ""
                    url = item.get("url", "") or ""
                    
                    if not title or not url:
                        continue
                        
                    source_name = item.get("source", "Finnhub")
                    dt_val = item.get("datetime", None)
                    if dt_val:
                        published_at = datetime.utcfromtimestamp(dt_val).isoformat()
                    else:
                        published_at = datetime.utcnow().isoformat()

                    articles.append({
                        "title": title,
                        "description": desc,
                        "url": url,
                        "source": source_name,
                        "provider": "finnhub",
                        "published_at": published_at,
                        "company": "",
                        "sector": "",
                        "country": "", # Will be checked by country filtering downstream
                        "raw_content": f"{title}\n{desc}"
                    })
        except Exception as e:
            print(f"Error fetching from Finnhub: {e}")
            
        return articles
