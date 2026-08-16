import xml.etree.ElementTree as ET
import httpx
from datetime import datetime
import email.utils
from typing import List, Dict, Any

class RSSProvider:
    def __init__(self):
        # Configure standard Indian financial news feeds
        self.feeds = {
            "Moneycontrol Markets": "https://www.moneycontrol.com/rss/marketoutlook.xml",
            "Moneycontrol Business": "https://www.moneycontrol.com/rss/business.xml",
            "Economic Times Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
            "Livemint Markets": "https://www.livemint.com/rss/markets"
        }

    async def fetch_articles(self) -> List[Dict[str, Any]]:
        articles = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for feed_name, url in self.feeds.items():
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        print(f"RSS Feed {feed_name} returned status {response.status_code}")
                        continue
                    
                    root = ET.fromstring(response.content)
                    channel = root.find("channel")
                    if channel is None:
                        continue
                    
                    items = channel.findall("item")
                    for item in items:
                        title_el = item.find("title")
                        desc_el = item.find("description")
                        link_el = item.find("link")
                        pub_el = item.find("pubDate")
                        
                        title = title_el.text.strip() if title_el is not None and title_el.text else ""
                        desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                        link = link_el.text.strip() if link_el is not None and link_el.text else ""
                        
                        # Clean HTML tags if present in description
                        if desc:
                            import re
                            desc = re.sub(r'<[^>]*>', '', desc)
                        
                        published_at = None
                        if pub_el is not None and pub_el.text:
                            try:
                                dt = email.utils.parsedate_to_datetime(pub_el.text.strip())
                                published_at = dt.isoformat()
                            except Exception:
                                published_at = datetime.utcnow().isoformat()
                        else:
                            published_at = datetime.utcnow().isoformat()

                        articles.append({
                            "title": title,
                            "description": desc,
                            "url": link,
                            "source": feed_name,
                            "provider": "rss",
                            "published_at": published_at,
                            "company": "",
                            "sector": "",
                            "country": "IN",
                            "raw_content": f"{title}\n{desc}"
                        })
                except Exception as e:
                    print(f"Error fetching RSS feed {feed_name}: {e}")
        return articles
