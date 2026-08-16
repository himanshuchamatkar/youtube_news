import os
import re
import json
import secrets
from cryptography.fernet import Fernet

def parse_credentials(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    data = {}
    
    # Simple regex parsing for key-value
    kv_pattern = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$')
    
    # We also need to extract the Google TTS JSON object
    # Find "{ ... }" block in the file
    json_blocks = re.findall(r'(\{[\s\S]*?\})', content)
    google_tts_json = None
    if json_blocks:
        try:
            # Validate it's proper JSON
            parsed_json = json.loads(json_blocks[0])
            google_tts_json = json.dumps(parsed_json)
        except Exception as e:
            print(f"Error parsing Google TTS JSON block: {e}")

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        match = kv_pattern.match(line)
        if match:
            key, val = match.groups()
            data[key] = val.strip()

    if google_tts_json:
        data['GOOGLE_TTS_SERVICE_ACCOUNT_JSON'] = google_tts_json

    return data

def main():
    cred_file = "D:/youtube_news/credentials.txt"
    if not os.path.exists(cred_file):
        print(f"Credentials file not found at {cred_file}")
        return

    print("Parsing credentials.txt...")
    creds = parse_credentials(cred_file)
    
    # Generate Encryption Key and Admin Password
    encryption_key = Fernet.generate_key().decode()
    admin_password = secrets.token_urlsafe(12)
    
    # Parse Supabase URL (strip rest/v1/ if present so supabase-py client likes it)
    supabase_url = creds.get('SUPABASE_URL', '')
    if supabase_url.endswith('/rest/v1/'):
        supabase_url = supabase_url[:-8]
    elif supabase_url.endswith('/rest/v1'):
        supabase_url = supabase_url[:-7]

    env_lines = [
        "# Generated Environment Variables",
        f"GEMINI_API_KEY={creds.get('GEMINI_API_KEY', '')}",
        f"YOUTUBE_CLIENT_ID={creds.get('YOUTUBE_CLIENT_ID', '')}",
        f"YOUTUBE_CLIENT_SECRET={creds.get('YOUTUBE_CLIENT_SECRET', '')}",
        f"YOUTUBE_REFRESH_TOKEN={creds.get('YOUTUBE_REFRESH_TOKEN', '')}",
        f"SUPABASE_URL={supabase_url}",
        f"SUPABASE_ANON_KEY={creds.get('SUPABASE_ANON_KEY', '')}",
        f"SUPABASE_SERVICE_ROLE_KEY={creds.get('SUPABASE_SERVICE_ROLE_KEY', '')}",
        f"GOOGLE_TTS_SERVICE_ACCOUNT_JSON={creds.get('GOOGLE_TTS_SERVICE_ACCOUNT_JSON', '')}",
        f"NEWS_API_KEY={creds.get('NEWS_API_KEY', '')}",
        f"GNEWS_API_KEY={creds.get('GNEWS_API_KEY', '')}",
        f"FINNHUB_API_KEY={creds.get('FINNHUB_API_KEY', '')}",
        f"PEXELS_API_KEY={creds.get('PEXELS_API_KEY', '')}",
        f"GITHUB_REPO_URL={creds.get('GITHUB_REPO_URL', '')}",
        f"VERCEL_TOKEN={creds.get('VERCEL_TOKEN', '')}",
        f"RENDER_API_KEY={creds.get('RENDER_API_KEY', '')}",
        "",
        "# System Encryption",
        f"SETTINGS_ENCRYPTION_KEY={encryption_key}",
        "",
        "# Administrator Authentication",
        "ADMIN_USERNAME=admin",
        f"ADMIN_PASSWORD={admin_password}",
        "",
        "# Application Options",
        "PORT=8000",
        "HOST=0.0.0.0",
        "NODE_ENV=development",
    ]

    # Save to .env
    with open("D:/youtube_news/.env", "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines))
    print("Created D:/youtube_news/.env successfully!")
    print(f"Admin Credentials: Username: admin | Password: {admin_password}")

    # Create .gitignore
    gitignore_content = """# Environment and secrets
.env
.env.*
credentials.txt
*.json
!package.json
!tsconfig.json
!composer.json
!vercel.json
!render.yaml

# OS files
Thumbs.db
ehthumbs.db
Desktop.ini

# Python files
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.cache
nosetests.xml
coverage.xml
*,cover
.hypothesis/
.pytest_cache/

# Node files
node_modules/
dist/
build/
.eslintcache

# Media files (temporary / rendered)
media/temp/*
media/audio/*
media/images/*
media/charts/*
media/rendered/*
!media/temp/.gitkeep
!media/audio/.gitkeep
!media/images/.gitkeep
!media/charts/.gitkeep
!media/rendered/.gitkeep
"""
    with open("D:/youtube_news/.gitignore", "w", encoding="utf-8") as f:
        f.write(gitignore_content)
    print("Created D:/youtube_news/.gitignore successfully!")

    # Create media folder structures and .gitkeep files
    media_dirs = [
        "D:/youtube_news/media/temp",
        "D:/youtube_news/media/audio",
        "D:/youtube_news/media/images",
        "D:/youtube_news/media/charts",
        "D:/youtube_news/media/rendered",
    ]
    for d in media_dirs:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, ".gitkeep"), "w") as f:
            f.write("")
    print("Created media folder structure and .gitkeep files.")

if __name__ == '__main__':
    main()
