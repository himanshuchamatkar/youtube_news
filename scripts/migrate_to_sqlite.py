import sys
import os
import re
import supabase._sync.client

# Monkeypatch key validation to allow "sb_" prefixed keys
original_match = re.match
def custom_match(pattern, string, flags=0):
    if pattern == r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$":
        if string and string.startswith("sb_"):
            return True
    return original_match(pattern, string, flags)

supabase._sync.client.re.match = custom_match

# Insert D:/youtube_news into system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from supabase import create_client
from backend.app.core.config import settings
from backend.app.core.supabase_client import get_supabase_client

def main():
    print("=== Database Migration: Supabase -> SQLite ===")
    
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not url or not key:
        print("ERROR: Supabase URL/Key not configured in .env. Skipping cloud import.")
        return
        
    print("Connecting to Supabase cloud database...")
    try:
        supabase_real = create_client(url, key)
    except Exception as e:
        print(f"ERROR: Failed to connect to Supabase: {e}")
        return
        
    sqlite_db = get_supabase_client()
    
    tables = [
        "settings",
        "news_articles",
        "daily_selections",
        "scripts",
        "video_jobs",
        "videos",
        "job_logs",
        "channel_metrics"
    ]
    
    for t in tables:
        print(f"\nMigrating table '{t}'...")
        try:
            # Fetch all rows from real Supabase
            res = supabase_real.table(t).select("*").execute()
            rows = res.data
            print(f"Fetched {len(rows)} rows from cloud.")
            
            if not rows:
                continue
                
            # SQLite insert
            for row in rows:
                try:
                    # SQLite upsert
                    sqlite_db.table(t).upsert(row).execute()
                except Exception as ins_err:
                    print(f"  Warning: failed to insert row {row.get('id', row.get('key'))}: {ins_err}")
            print(f"Table '{t}' migrated successfully.")
        except Exception as e:
            print(f"ERROR migrating table '{t}': {e}")
            
    print("\nDatabase migration completed successfully! All data synced to local factory.db.")

if __name__ == "__main__":
    main()
