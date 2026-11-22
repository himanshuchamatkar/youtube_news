import os
import json
import uuid
import sqlite3
import socket
import re
from urllib.parse import urlparse
from datetime import date, datetime
from typing import Any, List, Dict, Optional, Union

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

# Database path: stored at the root of the workspace
DB_FILE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")), "factory.db")

class SupabaseResponse:
    def __init__(self, data):
        self.data = data

class QueryBuilder:
    def __init__(self, table: str, db_path: str):
        self.table = table
        self.db_path = db_path
        self.op = None
        self.select_fields = "*"
        self.insert_data = None
        self.update_data = None
        self.where_clauses = []
        self.where_args = []
        self.order_by = None
        self.limit_val = None

    def select(self, fields: str = "*"):
        self.op = "select"
        self.select_fields = fields
        return self

    def insert(self, data: Any):
        self.op = "insert"
        self.insert_data = data
        return self

    def update(self, data: Any):
        self.op = "update"
        self.update_data = data
        return self

    def delete(self):
        self.op = "delete"
        return self

    def upsert(self, data: Any):
        self.op = "upsert"
        self.insert_data = data
        return self

    def eq(self, column: str, value: Any):
        self.where_clauses.append(f"{column} = ?")
        self.where_args.append(value)
        return self

    def order(self, column: str, desc: bool = False):
        self.order_by = f"{column} {'DESC' if desc else 'ASC'}"
        return self

    def limit(self, val: int):
        self.limit_val = val
        return self

    def execute(self):
        # Open connection on demand with 30s timeout and WAL concurrency mode
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            res_data = []
            if self.op == "select":
                sql = f"SELECT {self.select_fields} FROM {self.table}"
                if self.where_clauses:
                    sql += " WHERE " + " AND ".join(self.where_clauses)
                if self.order_by:
                    sql += f" ORDER BY {self.order_by}"
                if self.limit_val:
                    sql += f" LIMIT {self.limit_val}"
                
                cursor.execute(sql, self.where_args)
                rows = cursor.fetchall()
                for r in rows:
                    row_dict = dict(r)
                    if self.table == "scripts" and "hashtags" in row_dict and row_dict["hashtags"]:
                        try:
                            row_dict["hashtags"] = json.loads(row_dict["hashtags"])
                        except Exception:
                            pass
                    if "source_urls" in row_dict and row_dict["source_urls"] and isinstance(row_dict["source_urls"], str):
                        try:
                            row_dict["source_urls"] = json.loads(row_dict["source_urls"])
                        except Exception:
                            pass
                    for k, v in row_dict.items():
                        if k in ["is_test", "is_encrypted", "auto_upload", "auto_voice"]:
                            row_dict[k] = True if v == 1 else False
                    res_data.append(row_dict)

            elif self.op == "insert" or self.op == "upsert":
                rows_to_insert = self.insert_data if isinstance(self.insert_data, list) else [self.insert_data]
                
                for item in rows_to_insert:
                    item_copy = dict(item)
                    
                    # Auto-populate UUID for general tables
                    if "id" not in item_copy and self.table != "settings":
                        item_copy["id"] = str(uuid.uuid4())
                        
                    # Auto-populate date for daily_selections to avoid NOT NULL constraints
                    if self.table == "daily_selections" and "date" not in item_copy:
                        item_copy["date"] = date.today().isoformat()
                        
                    for k, v in item_copy.items():
                        if isinstance(v, list):
                            item_copy[k] = json.dumps(v)
                        elif isinstance(v, bool):
                            item_copy[k] = 1 if v else 0
                            
                    columns = list(item_copy.keys())
                    placeholders = ", ".join(["?"] * len(columns))
                    
                    if self.op == "upsert" or self.table == "settings":
                        sql = f"INSERT OR REPLACE INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})"
                    else:
                        sql = f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})"
                        
                    cursor.execute(sql, list(item_copy.values()))
                    
                    if self.table == "settings":
                        read_back_sql = f"SELECT * FROM {self.table} WHERE key = ?"
                        read_back_args = [item_copy["key"]]
                    else:
                        read_back_sql = f"SELECT * FROM {self.table} WHERE id = ?"
                        read_back_args = [item_copy["id"]]
                        
                    read_cursor = conn.cursor()
                    read_cursor.execute(read_back_sql, read_back_args)
                    r = read_cursor.fetchone()
                    if r:
                        row_dict = dict(r)
                        if self.table == "scripts" and "hashtags" in row_dict and row_dict["hashtags"]:
                            try:
                                row_dict["hashtags"] = json.loads(row_dict["hashtags"])
                            except Exception:
                                pass
                        for k, v in row_dict.items():
                            if k in ["is_test", "is_encrypted", "auto_upload", "auto_voice"]:
                                row_dict[k] = True if v == 1 else False
                        res_data.append(row_dict)

            elif self.op == "update":
                if not self.where_clauses:
                    raise ValueError("Updates must have a where clause.")
                    
                update_items = dict(self.update_data)
                for k, v in update_items.items():
                    if isinstance(v, bool):
                        update_items[k] = 1 if v else 0
                    elif isinstance(v, list):
                        update_items[k] = json.dumps(v)
                        
                set_clause = ", ".join([f"{k} = ?" for k in update_items.keys()])
                sql = f"UPDATE {self.table} SET {set_clause} WHERE " + " AND ".join(self.where_clauses)
                args = list(update_items.values()) + self.where_args
                cursor.execute(sql, args)
                
                read_cursor = conn.cursor()
                read_cursor.execute(f"SELECT * FROM {self.table} WHERE " + " AND ".join(self.where_clauses), self.where_args)
                rows = read_cursor.fetchall()
                for r in rows:
                    row_dict = dict(r)
                    if self.table == "scripts" and "hashtags" in row_dict and row_dict["hashtags"]:
                        try:
                            row_dict["hashtags"] = json.loads(row_dict["hashtags"])
                        except Exception:
                            pass
                    for k, v in row_dict.items():
                        if k in ["is_test", "is_encrypted", "auto_upload", "auto_voice"]:
                            row_dict[k] = True if v == 1 else False
                    res_data.append(row_dict)

            elif self.op == "delete":
                sql = f"DELETE FROM {self.table}"
                if self.where_clauses:
                    sql += " WHERE " + " AND ".join(self.where_clauses)
                cursor.execute(sql, self.where_args)
                res_data = []

            conn.commit()
            return SupabaseResponse(res_data)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            conn.close()

class SupabaseClientMock:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        try:
            # 1. settings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                is_encrypted INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 2. news_articles table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                url TEXT UNIQUE NOT NULL,
                source TEXT,
                provider TEXT,
                published_at TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                company TEXT,
                sector TEXT,
                country TEXT,
                relevance_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'raw',
                duplicate_of TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 3. daily_selections table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_selections (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL DEFAULT (date('now')),
                news_article_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                selection_reason TEXT,
                is_test INTEGER DEFAULT 0,
                selected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(news_article_id) REFERENCES news_articles(id) ON DELETE CASCADE
            )
            """)
            
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_selections_prod_date 
            ON daily_selections(date) WHERE is_test = 0
            """)
            
            # 4. scripts table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id TEXT PRIMARY KEY,
                news_article_id TEXT NOT NULL,
                script TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                hashtags TEXT,
                model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(news_article_id) REFERENCES news_articles(id) ON DELETE CASCADE
            )
            """)
            
            # 5. video_jobs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_jobs (
                id TEXT PRIMARY KEY,
                job_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                progress INTEGER DEFAULT 0,
                current_stage TEXT DEFAULT 'queued',
                is_test INTEGER DEFAULT 0,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                error_message TEXT
            )
            """)
            
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_video_jobs_prod_date 
            ON video_jobs(job_date) WHERE is_test = 0
            """)
            
            # 6. videos table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                youtube_video_id TEXT UNIQUE,
                youtube_url TEXT,
                published_at TEXT DEFAULT CURRENT_TIMESTAMP,
                video_path TEXT,
                status TEXT DEFAULT 'uploaded',
                duration INTEGER,
                tags TEXT,
                source_urls TEXT,
                FOREIGN KEY(job_id) REFERENCES video_jobs(id) ON DELETE SET NULL
            )
            """)
            
            # 7. job_logs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_logs (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                duration REAL DEFAULT 0.0,
                error TEXT,
                FOREIGN KEY(job_id) REFERENCES video_jobs(id) ON DELETE CASCADE
            )
            """)
            
            # 8. channel_metrics table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_metrics (
                id TEXT PRIMARY KEY,
                subscriber_count INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                captured_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # --- Schema Migrations (non-destructive) ---
            # Add is_test column to videos table
            try:
                cursor.execute("ALTER TABLE videos ADD COLUMN is_test INTEGER DEFAULT 0")
            except Exception:
                pass  # Column already exists
            
            # Add execution_type column to video_jobs table
            try:
                cursor.execute("ALTER TABLE video_jobs ADD COLUMN execution_type TEXT DEFAULT 'public'")
            except Exception:
                pass  # Column already exists
            
            # Backfill execution_type from is_test for existing rows
            try:
                cursor.execute("UPDATE video_jobs SET execution_type = 'test' WHERE is_test = 1 AND (execution_type IS NULL OR execution_type = 'public')")
                cursor.execute("UPDATE videos SET is_test = 1 WHERE job_id IN (SELECT id FROM video_jobs WHERE is_test = 1) AND is_test = 0")
            except Exception:
                pass

            conn.commit()
        finally:
            conn.close()

    def table(self, table_name: str) -> QueryBuilder:
        return QueryBuilder(table_name, self.db_path)

_client_instance = None

def get_supabase_client() -> Any:
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    url = (getattr(settings, "SUPABASE_URL", "") or "").strip().rstrip('/')
    key = (getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "") or getattr(settings, "SUPABASE_ANON_KEY", "") or "").strip()

    if url and key:
        try:
            parsed = urlparse(url)
            host = parsed.netloc or parsed.path.split('/')[0]
            # Fast DNS check to verify host exists and internet is available
            socket.gethostbyname(host)
            
            from supabase import create_client
            cloud_client = create_client(url, key)
            # Verify connectivity to tables
            cloud_client.table("settings").select("key").limit(1).execute()
            print(f"[Database] LIVE: Connected to Cloud Supabase ({host})! Cross-device sync active.")
            _client_instance = cloud_client
            return _client_instance
        except Exception as e:
            print(f"[Database] NOTICE: Cloud Supabase is not reachable ({e}).")
            print("[Database] Using local SQLite database (factory.db). To enable cross-device sync, ensure your Supabase project is unpaused at supabase.com.")

    _client_instance = SupabaseClientMock()
    return _client_instance
