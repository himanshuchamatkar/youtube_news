import os
import httpx
from dotenv import load_dotenv

def main():
    load_dotenv("D:/youtube_news/.env")
    
    service_id = "srv-da0okcnlk1mc738e5e5g"
    api_key = "rnd_FqmQNqxwSntZBrwazQFkyAKGZSyh"
    
    # Read variables from .env
    env_vars = []
    with open("D:/youtube_news/.env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                # Filter out comment suffixes or formatting if any
                env_vars.append({
                    "key": key.strip(),
                    "value": val.strip()
                })
                
    print(f"Read {len(env_vars)} variables from .env. Uploading to Render...")
    
    url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    r = httpx.put(url, headers=headers, json=env_vars)
    print(f"Status Code: {r.status_code}")
    print(r.text)

if __name__ == '__main__':
    main()
