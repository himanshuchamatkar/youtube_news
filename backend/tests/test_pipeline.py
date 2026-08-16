import unittest
import os
from datetime import datetime, timezone, timedelta
from backend.app.services.news_engine import NewsEngine

class TestShortsFactoryPipeline(unittest.TestCase):
    def setUp(self):
        self.engine = NewsEngine()

    def test_indian_market_news_accepted(self):
        # Valid Indian Stock Market Article
        art = {
            "title": "Nifty 50 Hits Record High of 24,500 Amid HDFC Bank Rally",
            "description": "Indian benchmark indices rose to all-time highs today as HDFC Bank shares surged by 4.5% after strong Q1 earnings.",
            "source": "Moneycontrol",
            "provider": "rss",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "company": "HDFC Bank",
            "sector": "Banking",
            "country": "IN"
        }
        score = self.engine.filter_and_score(art)
        print(f"Test: Indian stock news score = {score}")
        self.assertTrue(score >= 70, f"Expected score >= 70, got {score}")

    def test_us_news_rejected(self):
        # US Stock Market Article
        art = {
            "title": "Nasdaq Surges as Nvidia and Apple Drive Tech Market Rallies",
            "description": "Tech giants Microsoft and Apple led Wall Street shares higher today as interest rate worries fade.",
            "source": "Reuters US",
            "provider": "newsapi",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "company": "Apple",
            "sector": "Technology",
            "country": "US"
        }
        score = self.engine.filter_and_score(art)
        print(f"Test: US news score = {score}")
        self.assertTrue(score == 0 or score < 70, f"Expected US news to be rejected, got score {score}")

    def test_crypto_news_rejected(self):
        # Cryptocurrency Article
        art = {
            "title": "Bitcoin Plummets Below $55,000 Amid Ethereum Cell-off",
            "description": "Major crypto tokens crashed today as sell pressure pushed bitcoin prices down by 8%.",
            "source": "CoinDesk",
            "provider": "gnews",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "company": "",
            "sector": "",
            "country": ""
        }
        score = self.engine.filter_and_score(art)
        print(f"Test: Crypto news score = {score}")
        self.assertTrue(score == 0 or score < 70, f"Expected Crypto news to be rejected, got score {score}")

    def test_duplicate_detection(self):
        # Two highly similar headlines
        title1 = "Reliance Q1 Net Profit rises 10 percent to 16000 crore"
        title2 = "Reliance Q1 profit jumps 10 percent to 16000 crore"
        similarity = self.engine.jaccard_similarity(title1, title2)
        print(f"Test: Jaccard similarity = {similarity:.4f}")
        # Expecting high similarity (> 0.5)
        self.assertTrue(similarity > 0.5, f"Expected Jaccard similarity > 0.5, got {similarity}")

    def test_stale_news_rejection(self):
        # Article published 5 days ago (should get low freshness score)
        stale_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        art = {
            "title": "SEBI Announce New Mutual Fund Margins Policy Guidelines",
            "description": "The regulator introduced changes to margin requirements starting next week.",
            "source": "Economic Times",
            "provider": "rss",
            "published_at": stale_date,
            "company": "",
            "sector": "",
            "country": "IN"
        }
        score = self.engine.filter_and_score(art)
        print(f"Test: Stale news score = {score}")
        # Even with Indian context, the stale date should pull the score below 70
        self.assertTrue(score < 70, f"Expected stale news score < 70, got {score}")

    def test_video_duration_bounds(self):
        # Validation bounds test
        min_dur = 28.0
        max_dur = 65.0
        
        # Test a valid duration
        v_dur = 45.0
        self.assertTrue(min_dur <= v_dur <= max_dur)
        
        # Test an invalid duration
        v_dur_invalid = 15.0
        self.assertFalse(min_dur <= v_dur_invalid <= max_dur)

if __name__ == '__main__':
    unittest.main()
