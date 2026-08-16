import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any
from backend.app.core.config import settings

class NewsAPIProvider:
    def __init__(self):
        self.api_key = settings.NEWS_API_KEY
        self.base_url = "https://newsapi.org/v2/everything"

    async def fetch_articles(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            print("NewsAPI key not configured.")
            return []
            
        articles = []
        # Fetch articles from last 2 days
        from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
        
        # Query targeted to Indian stock markets
        q = '("Nifty" OR "Sensex" OR "BSE India" OR "NSE India" OR "Indian stock market" OR "SEBI")'
        params = {
            "q": q,
            "from": from_date,
            "sortBy": "publishedAt",
            "language": "en",
            "apiKey": self.api_key,
            "pageSize": 50
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                if response.status_code != 200:
                    print(f"NewsAPI returned status {response.status_code}: {response.text}")
                    return []
                    
                data = response.json()
                raw_articles = data.get("articles", [])
                for item in raw_articles:
                    title = item.get("title", "") or ""
                    desc = item.get("description", "") or ""
                    url = item.get("url", "") or ""
                    
                    if not title or not url:
                        continue
                        
                    source_name = item.get("source", {}).get("name", "NewsAPI")
                    published_at = item.get("publishedAt", datetime.utcnow().isoformat())

                    articles.append({
                        "title": title,
                        "description": desc,
                        "url": url,
                        "source": source_name,
                        "provider": "newsapi",
                        "published_at": published_at,
                        "company": "",
                        "sector": "",
                        "country": "IN",
                        "raw_content": f"{title}\n{desc}\n{item.get('content', '')}"
                    })
        except Exception as e:
            print(f"Error fetching from NewsAPI: {e}")
            
        return articles
