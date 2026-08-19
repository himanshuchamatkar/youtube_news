import json
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List, Optional, Any
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
        self.backup_key = settings.GEMINI_BACKUP_API_KEY
        self.backup_key_2 = settings.GEMINI_BACKUP_API_KEY_2
        self.model_name = "gemini-3.6-flash"

    def get_db_key(self) -> Optional[str]:
        try:
            supabase = get_supabase_client()
            res = supabase.table("settings").select("value").eq("key", "gemini_api_key").execute()
            if res.data:
                encrypted_key = res.data[0]["value"]
                decrypted_key = settings.decrypt(encrypted_key)
                if decrypted_key:
                    return decrypted_key
        except Exception as e:
            print(f"GeminiService: Failed to fetch key from DB settings: {e}")
        return None

    def get_keys(self) -> List[str]:
        # 1. Gather all configured keys
        all_keys = {}
        
        db_key = self.get_db_key()
        if db_key:
            all_keys["db_key"] = db_key
        if self.default_key:
            all_keys["default"] = self.default_key
        if self.backup_key:
            all_keys["backup_1"] = self.backup_key
        if self.backup_key_2:
            all_keys["backup_2"] = self.backup_key_2
            
        # 2. Check if a specific active key ID has been selected in settings
        active_id = "default"
        try:
            supabase = get_supabase_client()
            res = supabase.table("settings").select("value").eq("key", "active_gemini_key_id").execute()
            if res.data:
                active_id = res.data[0]["value"]
        except Exception as e:
            print(f"GeminiService: Failed to fetch active key selection: {e}")
            
        # 3. Sort keys putting the selected one at index 0
        keys = []
        if active_id in all_keys and all_keys[active_id]:
            keys.append(all_keys[active_id])
            
        # Add remaining keys for robust fallback rotation
        for k_id, k_val in all_keys.items():
            if k_val and k_val not in keys:
                keys.append(k_val)
                
        return keys

    def test_key(self, api_key: str) -> bool:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content("Hello. Reply with 'OK'.")
            return "OK" in response.text or len(response.text) > 0
        except Exception as e:
            print(f"Gemini key test failed: {e}")
            return False

    def call_ollama(self, prompt: str, schema_class: Any) -> Any:
        import httpx
        url = "http://localhost:11434/api/chat"
        
        schema_fields = schema_class.__fields__
        schema_desc = {k: v.description for k, v in schema_fields.items()}
        
        system_prompt = f"""
        You are a helpful AI assistant. You must output JSON that exactly conforms to the following schema structure:
        Fields: {list(schema_fields.keys())}
        Field descriptions: {json.dumps(schema_desc)}
        
        Return ONLY a raw JSON object. Do not wrap the JSON in Markdown backticks or include any explanation.
        """
        
        # Auto-detect running Ollama models (fall back to qwen2.5:7b if not checked)
        target_model = "qwen2.5:7b"
        try:
            res = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
            if res.status_code == 200:
                installed_models = [m["name"] for m in res.json().get("models", [])]
                if installed_models:
                    # Select the first model matching qwen or llama, else first available
                    found = False
                    for m in installed_models:
                        if "qwen" in m or "llama" in m:
                            target_model = m
                            found = True
                            break
                    if not found:
                        target_model = installed_models[0]
        except Exception:
            pass

        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        }
        
        print(f"GeminiService: Connecting to local Ollama (model: {target_model})...")
        response = httpx.post(url, json=payload, timeout=180.0)
        if response.status_code != 200:
            raise ValueError(f"Ollama returned status {response.status_code}: {response.text}")
            
        res_json = response.json()
        message_content = res_json["message"]["content"]
        
        parsed_data = json.loads(message_content)
        
        # Fill defaults for missing fields to avoid pydantic schema validation errors
        for field_name, field in schema_class.__fields__.items():
            if field_name not in parsed_data:
                if field.annotation == bool:
                    parsed_data[field_name] = False
                elif field.annotation == int:
                    parsed_data[field_name] = 0
                elif field.annotation == str:
                    parsed_data[field_name] = "N/A"
                elif getattr(field.annotation, "__origin__", None) == list:
                    parsed_data[field_name] = []
                    
        return schema_class(**parsed_data)

    def evaluate_article(self, article: dict) -> NewsEvaluation:
        # Check active selection
        active_id = "default"
        try:
            supabase = get_supabase_client()
            res = supabase.table("settings").select("value").eq("key", "active_gemini_key_id").execute()
            if res.data:
                active_id = res.data[0]["value"]
        except Exception:
            pass

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

        if active_id == "ollama":
            return self.call_ollama(prompt, NewsEvaluation)

        keys = self.get_keys()
        if not keys:
            raise ValueError("No Gemini API keys are configured.")

        last_err = None
        for key in keys:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(
                    self.model_name,
                    generation_config={"response_mime_type": "application/json", "response_schema": NewsEvaluation}
                )
                response = model.generate_content(prompt)
                data = json.loads(response.text)
                return NewsEvaluation(**data)
            except Exception as e:
                print(f"GeminiService: Key failed or rate limited during evaluate: {e}. Trying backup key...")
                last_err = e
        
        raise last_err

    def generate_script(self, article: dict) -> ScriptOutput:
        # Check active selection
        active_id = "default"
        try:
            supabase = get_supabase_client()
            res = supabase.table("settings").select("value").eq("key", "active_gemini_key_id").execute()
            if res.data:
                active_id = res.data[0]["value"]
        except Exception:
            pass

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

        if active_id == "ollama":
            script_data = self.call_ollama(prompt, ScriptOutput)
            if not script_data.source_urls:
                script_data.source_urls = [article.get("url")]
            return script_data

        keys = self.get_keys()
        if not keys:
            raise ValueError("No Gemini API keys are configured.")

        last_err = None
        for key in keys:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(
                    self.model_name,
                    generation_config={"response_mime_type": "application/json", "response_schema": ScriptOutput}
                )
                response = model.generate_content(prompt)
                data = json.loads(response.text)
                if not data.get("source_urls"):
                    data["source_urls"] = [article.get("url")]
                return ScriptOutput(**data)
            except Exception as e:
                print(f"GeminiService: Key failed or rate limited during script generation: {e}. Trying backup key...")
                last_err = e
                
        raise last_err
