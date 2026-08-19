import os
import sys
import asyncio
import sqlite3

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.media_service import MediaService

async def main():
    print("=== Demo Video Generator Starting ===")
    
    # 1. Resolve SQLite database path
    db_path = "E:\\youtube_news\\factory.db"
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "factory.db")
        
    print(f"Reading database from: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 2. Fetch the latest generated script
    cursor.execute("SELECT id, news_article_id, script, title FROM scripts ORDER BY created_at DESC LIMIT 1")
    script_row = cursor.fetchone()
    if not script_row:
        print("Error: No scripts found in database!")
        return
        
    script_id, news_id, script_text, script_title = script_row
    print(f"Latest Script Title: {script_title}")
    
    # 3. Fetch the associated news article
    cursor.execute("SELECT title, description, url, source, provider, published_at, company, sector, country FROM news_articles WHERE id = ?", (news_id,))
    art_row = cursor.fetchone()
    if not art_row:
        print("Error: News article not found in database!")
        return
        
    art = {
        "title": art_row[0],
        "description": art_row[1],
        "url": art_row[2],
        "source": art_row[3],
        "provider": art_row[4],
        "published_at": art_row[5],
        "company": art_row[6],
        "sector": art_row[7],
        "country": art_row[8]
    }
    print(f"Associated Article: {art['title']}")
    
    # 4. Initialize MediaService with normalized E: paths
    media = MediaService()
    media.base_dir = "E:\\youtube_news"
    media.logo_path = "E:\\youtube_news\\logo\\logo.png"
    media.cta_path = "E:\\youtube_news\\logo\\cta_subscribe.jpg"
    media.temp_dir = "E:\\youtube_news\\media\\temp"
    media.audio_dir = "E:\\youtube_news\\media\\audio"
    media.charts_dir = "E:\\youtube_news\\media\\charts"
    media.rendered_dir = "E:\\youtube_news\\media\\rendered"
    
    # Ensure directories exist
    os.makedirs(media.temp_dir, exist_ok=True)
    os.makedirs(media.audio_dir, exist_ok=True)
    os.makedirs(media.charts_dir, exist_ok=True)
    os.makedirs(media.rendered_dir, exist_ok=True)
    
    script_dict = {
        "script": script_text,
        "title": script_title
    }
    
    job_id = f"demo_{script_id}"
    print(f"Generating demo video for Job ID: {job_id}...")
    
    try:
        video_path = await media.generate_video(art, script_dict, job_id)
        print(f"\nSUCCESS! Demo video rendered successfully at: {video_path}")
    except Exception as e:
        print(f"\nFAILED! Video generation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
