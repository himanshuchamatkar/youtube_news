import re
import supabase._sync.client
from supabase import create_client, Client
from backend.app.core.config import settings

# Monkeypatch the regex key validation in supabase client to allow "sb_" prefixed keys
original_match = re.match
def custom_match(pattern, string, flags=0):
    if pattern == r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$":
        if string and string.startswith("sb_"):
            return True
    return original_match(pattern, string, flags)

supabase._sync.client.re.match = custom_match

def get_supabase_client() -> Client:
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not url or not key:
        raise ValueError("Supabase URL and Key must be set in environment variables")
    return create_client(url, key)
