import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from backend.app.providers.rss import RSSProvider
from backend.app.providers.newsapi import NewsAPIProvider
from backend.app.providers.gnews import GNewsProvider
from backend.app.providers.finnhub import FinnhubProvider
from backend.app.core.config import settings

class NewsEngine:
    def __init__(self):
        self.rss = RSSProvider()
        self.newsapi = NewsAPIProvider()
        self.gnews = GNewsProvider()
        self.finnhub = FinnhubProvider()

        # Prohibited terms (Blacklist)
        self.blacklist = [
            "bitcoin", "cryptocurrency", "crypto", "ethereum", "dogecoin",
            "nasdaq", "s&p 500", "dow jones", "wall street", "nyse",
            "forex", "bollywood", "cricket", "hollywood", "celebrity", "sports",
            "athletics", "football", "tennis", "olympics", "boxing"
        ]

        # Indian financial market terms (Whitelist validation)
        self.indian_terms = [
            "nifty", "sensex", "bse", "nse", "sebi", "rbi", "india", "rupee", 
            "crore", "lakh", "ipo", "sme ipo", "adani", "reliance", "tata", 
            "infosys", "tcs", "hdfc", "wipro", "maruti", "icici", "sbi", "lic",
            "bharti airtel", "itc", "larsenn", "l&t", "kotak", "mahindra", "hindustan unilever",
            "bajaj", "sun pharma", "ntpc", "power grid", "coal india", "ongc"
        ]

    def jaccard_similarity(self, s1: str, s2: str) -> float:
        words1 = set(re.findall(r'\w+', s1.lower()))
        words2 = set(re.findall(r'\w+', s2.lower()))
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / len(words1.union(words2))

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    def filter_and_score(self, article: Dict[str, Any]) -> int:
        title = article["title"].lower()
        desc = article["description"].lower() if article["description"] else ""
        combined = f"{title} {desc}"

        # 1. Blacklist Check: If it contains any blacklisted term, reject immediately (score 0)
        for term in self.blacklist:
            if re.search(r'\b' + re.escape(term) + r'\b', combined):
                return 0

        # 2. Indian Market Relevance: Check if title/desc contains Indian terms
        relevance_score = 0
        has_indian_context = False
        
        # Primary check: direct index mentions (NSE, BSE, Nifty, Sensex, SEBI, RBI)
        primary_terms = ["nifty", "sensex", "bse", "nse", "sebi", "rbi", "rupee"]
        for term in primary_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', combined):
                relevance_score += 15
                has_indian_context = True

        # Secondary check: general Indian terms/companies
        for term in self.indian_terms:
            if term not in primary_terms:
                if re.search(r'\b' + re.escape(term) + r'\b', combined):
                    relevance_score += 10
                    has_indian_context = True
                    break # Cap at one secondary match to avoid score bloating

        # If it doesn't have any Indian context, reject it (unless provider is local like RSS or GNews-IN)
        if not has_indian_context and article["provider"] not in ["rss", "gnews"]:
            return 0
            
        relevance_score = min(relevance_score, 30)

        # 3. Financial Importance Check
        importance_score = 0
        financial_keywords = [
            "ipo", "earnings", "profit", "merger", "acquisition", "dividend", 
            "split", "crash", "rally", "policy", "rate hike", "bonus", "q1", 
            "q2", "q3", "q4", "revenue", "loss", "securities", "deal"
        ]
        for term in financial_keywords:
            if re.search(r'\b' + re.escape(term) + r'\b', combined):
                importance_score += 10
        importance_score = min(importance_score, 20)

        # 4. Freshness Scoring
        freshness_score = 5
        try:
            pub_dt = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            age_hours = (now_dt - pub_dt).total_seconds() / 3600.0
            if age_hours <= 12:
                freshness_score = 15
            elif age_hours <= 24:
                freshness_score = 10
            elif age_hours <= 48:
                freshness_score = 5
            else:
                freshness_score = 0
        except Exception:
            pass

        # 5. Source Credibility
        # RSS feeds and direct official/high-quality domains get higher points
        credibility_score = 10
        if article["provider"] == "rss":
            credibility_score = 15
        elif article["source"].lower() in ["reuters", "bloomberg", "economic times", "moneycontrol", "livemint", "business standard"]:
            credibility_score = 15

        # 6. Market Impact Score
        impact_score = 0
        impact_keywords = [
            "soars", "surges", "plummets", "crashes", "record high", "record low", 
            "hits", "jumps", "slumps", "tumbles", "skyrockets", "multibagger"
        ]
        for term in impact_keywords:
            if re.search(r'\b' + re.escape(term) + r'\b', combined):
                impact_score += 15
                break

        # Calculate final score
        total_score = relevance_score + importance_score + freshness_score + credibility_score + impact_score
        return min(total_score, 100)

    async def get_daily_news(self) -> List[Dict[str, Any]]:
        # Fetch from all active sources
        print("News Engine: Fetching raw news articles...")
        raw_list = []
        
        # Parallel-ish fetches
        rss_articles = await self.rss.fetch_articles()
        raw_list.extend(rss_articles)
        
        if settings.NEWS_API_KEY:
            newsapi_articles = await self.newsapi.fetch_articles()
            raw_list.extend(newsapi_articles)
            
        if settings.GNEWS_API_KEY:
            gnews_articles = await self.gnews.fetch_articles()
            raw_list.extend(gnews_articles)
            
        if settings.FINNHUB_API_KEY:
            finnhub_articles = await self.finnhub.fetch_articles()
            raw_list.extend(finnhub_articles)

        print(f"News Engine: Fetched {len(raw_list)} raw articles.")

        # Deduplication and filtering
        unique_articles = []
        for raw_art in raw_list:
            # Clean title
            raw_art["title"] = self.clean_text(raw_art["title"])
            raw_art["description"] = self.clean_text(raw_art["description"])
            
            # Score
            score = self.filter_and_score(raw_art)
            raw_art["relevance_score"] = score
            
            # Filter minimum score of 70
            if score < 70:
                continue

            # Duplicate check
            is_duplicate = False
            for existing in unique_articles:
                # URL Match or High Jaccard title match
                if raw_art["url"] == existing["url"] or self.jaccard_similarity(raw_art["title"], existing["title"]) > 0.5:
                    is_duplicate = True
                    # Map to duplicate parent if existing is older/newer
                    raw_art["duplicate_of"] = existing.get("id")
                    break
            
            if not is_duplicate:
                unique_articles.append(raw_art)

        # Sort by relevance score descending
        unique_articles.sort(key=lambda x: x["relevance_score"], reverse=True)
        print(f"News Engine: Found {len(unique_articles)} unique articles above score limit 70.")
        return unique_articles
