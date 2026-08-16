import json
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List, Optional
from backend.app.core.config import settings
from backend.app.core.supabase_client import get_supabase_client

# Define structured Pydantic schemas for Gemini outputs
class NewsEvaluation(BaseModel):
    selected: bool = Field(description="True if this is a high-quality Indian market news story fit for today's video.")
    score: int = Field(description="A quality score from 0-100.")
    category: str = Field(description="Classification: INDIAN_STOCK_MARKET, NON_INDIAN, FOREX, CRYPTO, GENERAL, IRRELEVANT")
    reason: str = Field(description="Short reason explaining why the article was selected or rejected.")
    market_impact: str = Field(description="Market impact: HIGH, MEDIUM, LOW")
    company: str = Field(description="Name of the company affected, or 'N/A'")
    sector: str = Field(description="Sector (e.g. IT, Banking, Auto, Pharma, FMCG, Energy, N/A)")
    needs_verification: bool = Field(description="True if the source numbers or facts seem dubious and need verification.")

class ScriptOutput(BaseModel):
    title: str = Field(description="Catchy but professional YouTube Short title (max 70 characters). Must end with '| Indian Stock Market Today'")
    hook: str = Field(description="High-impact opening sentence (first 3-5 seconds).")
    script: str = Field(description="The complete narration script (30-60 seconds, approx 120-150 words). Avoid investment advice like 'Buy' or 'Sell', use 'Could affect' or 'Investors are watching'.")
    description: str = Field(description="Comprehensive YouTube description containing summary and disclaimer.")
    hashtags: List[str] = Field(description="List of 3-5 relevant financial hashtags.")
    source_urls: List[str] = Field(description="List of source URLs for attribution.")
    disclaimer: str = Field(description="Disclaimer: 'This content is for informational purposes only and is not financial advice.'")

class GeminiService:
    def __init__(self):
        self.default_key = settings.GEMINI_API_KEY
        self.model_name = "gemini-1.5-flash"

    def get_api_key(self) -> str:
        # Dynamically fetch the API key from database settings table
        try:
            supabase = get_supabase_client()
            res = supabase.table("settings").select("value").eq("key", "gemini_api_key").execute()
            if res.data:
                encrypted_key = res.data[0]["value"]
                # Decrypt the key
                decrypted_key = settings.decrypt(encrypted_key)
                if decrypted_key:
                    return decrypted_key
        except Exception as e:
            print(f"GeminiService: Failed to fetch key from DB settings: {e}")
        
        return self.default_key

    def test_key(self, api_key: str) -> bool:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model_name)
            # A simple quick prompt to verify the key
            response = model.generate_content("Hello. Reply with 'OK'.")
            return "OK" in response.text or len(response.text) > 0
        except Exception as e:
            print(f"Gemini key test failed: {e}")
            return False

    def evaluate_article(self, article: dict) -> NewsEvaluation:
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError("Gemini API key is not configured.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json", "response_schema": NewsEvaluation}
        )

        prompt = f"""
        Analyze the following article for selection in a daily Indian Stock Market video.
        
        Article Details:
        Title: {article.get('title')}
        Description: {article.get('description')}
        Source: {article.get('source')}
        Content: {article.get('raw_content')}
        
        Strict Rules:
        1. Reject (selected=false) if the topic is NOT directly about the Indian stock/financial market.
        2. Reject if the news is about USA, Forex (unless direct Rupee impact), Crypto (Bitcoin), Sports, Bollywood, or International politics with no direct Indian market impact.
        3. Double check that numbers, company names, and dates are realistic.
        """

        response = model.generate_content(prompt)
        data = json.loads(response.text)
        return NewsEvaluation(**data)

    def generate_script(self, article: dict) -> ScriptOutput:
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError("Gemini API key is not configured.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json", "response_schema": ScriptOutput}
        )

        prompt = f"""
        You are the lead content writer for a professional Indian financial news channel.
        Create a 30-60 second YouTube Shorts script based ONLY on the supplied source news article below.
        
        Source News Article:
        Title: {article.get('title')}
        Description: {article.get('description')}
        Source URL: {article.get('url')}
        Content: {article.get('raw_content')}

        Strict Writing Rules:
        1. Use ONLY the supplied source information. Do NOT invent prices, dates, percentages, company statements, market movements, or statistics.
        2. Keep the script length between 120 and 150 words (perfect for 40-55 seconds narration).
        3. Use a clear Hook -> What happened -> Why it matters -> Market/Stock impact -> What to watch structure.
        4. NEVER give direct investment advice (e.g. do NOT say 'Buy this stock' or 'Sell now'). Use phrases like 'could affect', 'investors are watching', 'potential impact'.
        5. Provide source urls and a professional disclaimer.
        """

        response = model.generate_content(prompt)
        data = json.loads(response.text)
        # Ensure source url is included
        if not data.get("source_urls"):
            data["source_urls"] = [article.get("url")]
        return ScriptOutput(**data)
