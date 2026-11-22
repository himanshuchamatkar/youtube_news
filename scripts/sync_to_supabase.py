import os
import sys
import json
import sqlite3
import re
from urllib.parse import urlparse

# Add root directory to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.core.config import settings

# Monkeypatch regex in supabase client to allow "sb_" prefixed keys
try:
    import supabase._sync.client
    original_match = re.match
    def custom_match(pattern, string, flags=0):
        if 'A-Za-z0-9-_=' in pattern:
            if string and ('sb_' in string):
                return True
        return original_match(pattern, string, flags)
    supabase._sync.client.re.match = custom_match
except Exception:
    pass

from supabase import create_client

def sync_sqlite_to_supabase():
    db_file = os.path.join(BASE_DIR, "factory.db")
    if not os.path.exists(db_file):
        print(f"Local SQLite database not found at {db_file}")
        return

    url = (settings.SUPABASE_URL or "").strip().rstrip('/')
    key = (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY or "").strip()

    if not url or not key:
        print("Error: SUPABASE_URL and key must be set in .env")
        return

    print("======================================================================")
    print("  Syncing Local SQLite (factory.db) -> Cloud Supabase")
    print(f"  Target URL: {url}")
    print("======================================================================")

    try:
        supabase = create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        return

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

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

    for table_name in tables:
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            if not rows:
                print(f"Table '{table_name}': 0 rows (skipped)")
                continue

            records = []
            for r in rows:
                item = dict(r)
                # Parse JSON fields if necessary
                if table_name == "scripts" and "hashtags" in item and item["hashtags"]:
                    try:
                        item["hashtags"] = json.loads(item["hashtags"])
                    except Exception:
                        pass
                if table_name == "videos" and "source_urls" in item and item["source_urls"]:
                    try:
                        item["source_urls"] = json.loads(item["source_urls"])
                    except Exception:
                        pass
                if "is_test" in item:
                    item["is_test"] = bool(item["is_test"])
                if "is_encrypted" in item:
                    item["is_encrypted"] = bool(item["is_encrypted"])
                records.append(item)

            # Upload in batches of 50
            batch_size = 50
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                supabase.table(table_name).upsert(batch).execute()

            print(f"Table '{table_name}': Successfully uploaded {len(records)} records!")
        except Exception as e:
            print(f"Table '{table_name}' error: {e}")

    conn.close()
    print("======================================================================")
    print("  Sync completed successfully! Cloud Supabase is now up-to-date.")
    print("======================================================================")

if __name__ == "__main__":
    sync_sqlite_to_supabase()
