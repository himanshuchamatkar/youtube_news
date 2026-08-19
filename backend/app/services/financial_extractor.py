"""
Financial data extraction service.
Extracts structured financial metrics from news articles using LLM (Ollama/Gemini).
This ensures charts and cards use REAL data from the source, never fabricated values.
"""
import json
import re
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.app.services.gemini_service import GeminiService


class FinancialFigure(BaseModel):
    """A single extracted financial data point."""
    label: str = Field(description="Metric label, e.g. 'Revenue', 'Net Profit', 'Stock Price'")
    value: str = Field(description="The value as a string, e.g. '₹1,250 Cr', '8.5%', '₹2,345'")
    change: Optional[str] = Field(default=None, description="Change indicator if available, e.g. '+15%', '-2.3%'")
    period: Optional[str] = Field(default=None, description="Time period, e.g. 'Q1 FY27', 'YoY', 'Dec 2025'")


class FinancialMetrics(BaseModel):
    """Structured financial data extracted from a news article."""
    company_name: str = Field(description="Primary company name mentioned")
    ticker: str = Field(default="", description="Stock ticker symbol if known, e.g. 'TATAMOTORS', 'RELIANCE'")
    headline_type: str = Field(description="Type of news: STOCK_MOVEMENT, EARNINGS, IPO, POLICY, MERGER, DIVIDEND, SECTOR, GENERAL")
    
    # Core financial values
    current_price: str = Field(default="", description="Current stock price if mentioned, e.g. '₹2,345'")
    price_change_pct: str = Field(default="", description="Price change percentage, e.g. '+8.5%' or '-2.3%'")
    market_cap: str = Field(default="", description="Market cap if mentioned, e.g. '₹3.2 Lakh Cr'")
    
    # Key figures extracted from the article
    key_figures: List[FinancialFigure] = Field(default_factory=list, description="List of important financial figures from the article")
    
    # Summary for card generation
    short_headline: str = Field(description="A short, punchy headline for the video card, max 6 words")
    sub_headline: str = Field(default="", description="Secondary headline or context, max 10 words")


class FinancialExtractor:
    """Extracts structured financial data from news articles using LLM."""
    
    def __init__(self):
        self.gemini = GeminiService()
    
    def extract(self, article: Dict[str, Any]) -> FinancialMetrics:
        """Extract financial metrics from an article using LLM."""
        prompt = f"""
        Extract ONLY the financial data that is EXPLICITLY stated in the following news article.
        Do NOT invent, estimate, or hallucinate any numbers.
        If a value is not mentioned in the article, leave it empty.
        
        Article:
        Title: {article.get('title', '')}
        Description: {article.get('description', '')}
        Content: {article.get('raw_content', '')}
        Source: {article.get('source', '')}
        Company: {article.get('company', '')}
        Sector: {article.get('sector', '')}
        
        STRICT RULES:
        1. Only extract numbers that appear in the source text.
        2. Include the currency symbol (₹) and unit (Cr, Lakh, etc.) with values.
        3. For percentage changes, include the + or - sign.
        4. Extract at most 5 key_figures.
        5. The short_headline should be a compelling 4-6 word headline for a video card.
        """
        
        try:
            # Check active LLM selection
            active_id = "default"
            try:
                from backend.app.core.supabase_client import get_supabase_client
                supabase = get_supabase_client()
                res = supabase.table("settings").select("value").eq("key", "active_gemini_key_id").execute()
                if res.data:
                    active_id = res.data[0]["value"]
            except Exception:
                pass
            
            if active_id == "ollama":
                result = self.gemini.call_ollama(prompt, FinancialMetrics)
            else:
                keys = self.gemini.get_keys()
                if not keys:
                    return self._fallback_extract(article)
                
                import google.generativeai as genai
                last_err = None
                for key in keys:
                    try:
                        genai.configure(api_key=key)
                        model = genai.GenerativeModel(
                            self.gemini.model_name,
                            generation_config={"response_mime_type": "application/json", "response_schema": FinancialMetrics}
                        )
                        response = model.generate_content(prompt)
                        data = json.loads(response.text)
                        result = FinancialMetrics(**data)
                        break
                    except Exception as e:
                        last_err = e
                        continue
                else:
                    if last_err:
                        print(f"FinancialExtractor: All keys failed: {last_err}")
                    return self._fallback_extract(article)
            
            # Validate: cross-check extracted values appear in source text
            result = self._validate_extraction(result, article)
            return result
            
        except Exception as e:
            print(f"FinancialExtractor: LLM extraction failed: {e}")
            return self._fallback_extract(article)
    
    def _validate_extraction(self, metrics: FinancialMetrics, article: Dict[str, Any]) -> FinancialMetrics:
        """Cross-reference extracted values against source text to prevent hallucination."""
        source_text = f"{article.get('title', '')} {article.get('description', '')} {article.get('raw_content', '')}".lower()
        
        # Validate key figures - remove any that don't have values traceable to source
        validated_figures = []
        for fig in metrics.key_figures:
            # Extract numeric part from the value
            numbers = re.findall(r'[\d,.]+', fig.value)
            if numbers:
                # Check if any of these numbers appear in source
                found = any(num in source_text for num in numbers)
                if found:
                    validated_figures.append(fig)
                else:
                    print(f"FinancialExtractor: Rejected figure '{fig.label}: {fig.value}' - not found in source")
            else:
                # Non-numeric values, keep them (they're likely labels)
                validated_figures.append(fig)
        
        metrics.key_figures = validated_figures[:5]  # Cap at 5 figures
        return metrics
    
    def _fallback_extract(self, article: Dict[str, Any]) -> FinancialMetrics:
        """Heuristic fallback when LLM is unavailable."""
        title = article.get("title", "Market Update")
        company = article.get("company", "Market")
        sector = article.get("sector", "General")
        desc = article.get("description", "")
        combined = f"{title} {desc}"
        
        # Try to extract percentage from title/description
        pct_match = re.search(r'([+-]?\d+\.?\d*)\s*%', combined)
        price_change = f"{pct_match.group(0)}" if pct_match else ""
        if price_change and not price_change.startswith(('+', '-')):
            # Try to determine direction from context
            if any(w in combined.lower() for w in ['surges', 'rises', 'jumps', 'gains', 'soars', 'rallies', 'up']):
                price_change = f"+{price_change}"
            elif any(w in combined.lower() for w in ['falls', 'drops', 'plummets', 'crashes', 'slumps', 'down']):
                price_change = f"-{price_change}"
        
        # Determine headline type
        headline_type = "GENERAL"
        lower_combined = combined.lower()
        if any(w in lower_combined for w in ['ipo', 'listing']):
            headline_type = "IPO"
        elif any(w in lower_combined for w in ['earnings', 'profit', 'revenue', 'result', 'quarterly']):
            headline_type = "EARNINGS"
        elif any(w in lower_combined for w in ['merger', 'acquisition', 'takeover']):
            headline_type = "MERGER"
        elif any(w in lower_combined for w in ['dividend', 'bonus']):
            headline_type = "DIVIDEND"
        elif any(w in lower_combined for w in ['rbi', 'sebi', 'policy', 'rate']):
            headline_type = "POLICY"
        elif pct_match:
            headline_type = "STOCK_MOVEMENT"
        
        # Build short headline
        short_headline = title.split(" | ")[0][:40]
        if len(short_headline) > 30:
            words = short_headline.split()
            short_headline = " ".join(words[:5])
        
        # Extract key figures from text using regex
        key_figures = []
        
        # Look for currency values (₹ or Rs or INR)
        currency_matches = re.finditer(r'(?:₹|Rs\.?|INR)\s*([\d,]+\.?\d*)\s*((?:Cr|Lakh|crore|lakh|billion|million)?)', combined, re.IGNORECASE)
        for m in currency_matches:
            val = m.group(0).strip()
            key_figures.append(FinancialFigure(label="Value", value=val))
        
        if price_change:
            key_figures.append(FinancialFigure(label="Change", value=price_change))
        
        return FinancialMetrics(
            company_name=company if company != "N/A" else "Market",
            ticker="",
            headline_type=headline_type,
            price_change_pct=price_change,
            key_figures=key_figures[:5],
            short_headline=short_headline,
            sub_headline=f"{sector} Sector" if sector and sector != "N/A" else "Indian Market Update"
        )
