import os
import sys
import json
import sqlite3
import re
import uuid
import requests
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

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except Exception:
        return False

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

    # Fetch table schemas from PostgREST swagger
    table_props = {}
    try:
        r = requests.get(f"{url}/rest/v1/", headers={'apikey': key, 'Authorization': f'Bearer {key}'}, timeout=10)
        if r.status_code == 200:
            defs = r.json().get('definitions', {})
            for tname, tinfo in defs.items():
                table_props[tname] = set(tinfo.get('properties', {}).keys())
    except Exception as e:
        print(f"Note: Could not fetch schema definitions: {e}")

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

            valid_cols = table_props.get(table_name)
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

                # Handle invalid UUIDs in job_logs
                if table_name == "job_logs":
                    if not is_valid_uuid(item.get("job_id")):
                        continue  # Skip logs with malformed/undefined job_id

                # Filter item keys to valid columns if schema is known
                if valid_cols:
                    item = {k: v for k, v in item.items() if k in valid_cols}

                records.append(item)

            if not records:
                continue

            # Upload in batches of 50
            batch_size = 50
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                supabase.table(table_name).upsert(batch).execute()

            print(f"Table '{table_name}': Successfully synced {len(records)} records!")
        except Exception as e:
            print(f"Table '{table_name}' error: {e}")

    conn.close()
    print("======================================================================")
    print("  ALL TABLES SYNCED TO CLOUD SUPABASE SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    sync_sqlite_to_supabase()
