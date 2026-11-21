import os
from google_auth_oauthlib.flow import InstalledAppFlow

# YouTube scopes required for uploading and viewing metrics
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def update_env_file(client_id: str, client_secret: str, refresh_token: str):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_file = os.path.join(base_dir, ".env")
    
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_to_update = {
        "YOUTUBE_CLIENT_ID": client_id,
        "YOUTUBE_CLIENT_SECRET": client_secret,
        "YOUTUBE_REFRESH_TOKEN": refresh_token,
    }

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        matched = False
        for k in keys_to_update:
            if stripped.startswith(f"{k}="):
                new_lines.append(f"{k}={keys_to_update[k]}\n")
                updated_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_update.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"\n[OK] Automatically saved credentials into {env_file}!")

def main():
    print("=" * 60)
    print("  YouTube OAuth 2.0 Refresh Token Generator")
    print("=" * 60)
    
    # Try reading existing keys from .env
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_file = os.path.join(base_dir, ".env")
    env_client_id = ""
    env_client_secret = ""
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("YOUTUBE_CLIENT_ID="):
                    env_client_id = line.split("=", 1)[1].strip()
                elif line.startswith("YOUTUBE_CLIENT_SECRET="):
                    env_client_secret = line.split("=", 1)[1].strip()

    if env_client_id:
        print(f"\n[Found in .env] Client ID: {env_client_id[:16]}...apps.googleusercontent.com")
        client_id_prompt = f"1. Enter YOUTUBE_CLIENT_ID (Press Enter to use above): "
    else:
        client_id_prompt = "\n1. Enter your YOUTUBE_CLIENT_ID: "

    entered_id = input(client_id_prompt).strip()
    client_id = entered_id if entered_id else env_client_id

    if not client_id:
        print("[ERROR] Client ID cannot be empty.")
        return

    if env_client_secret:
        print(f"[Found in .env] Client Secret: {env_client_secret[:6]}...{env_client_secret[-4:]}")
        secret_prompt = f"2. Enter YOUTUBE_CLIENT_SECRET (Press Enter to use above): "
    else:
        secret_prompt = "2. Enter your YOUTUBE_CLIENT_SECRET: "

    entered_secret = input(secret_prompt).strip()
    client_secret = entered_secret if entered_secret else env_client_secret

    if not client_secret:
        print("[ERROR] Client Secret cannot be empty.")
        return

    # Support both Desktop App ("installed") and Web Application ("web")
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                "http://localhost:8080/",
                "http://localhost:8080",
                "http://127.0.0.1:8080/",
                "http://127.0.0.1:8080"
            ]
        }
    }

    print("\nOpening your browser for Google account approval...")
    print("Please select your YouTube channel account and click 'Allow'.")
    
    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
        creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

        refresh_token = creds.refresh_token
        if not refresh_token:
            print("\n[WARNING] No refresh token returned. Did you already authorize this app?")
            print("Try revoking app permissions in Google Account Settings or run with prompt='consent'.")
            return

        print("\n" + "=" * 60)
        print("SUCCESSFULLY RETRIEVED REFRESH TOKEN!")
        print("=" * 60)
        print(f"YOUTUBE_CLIENT_ID={client_id}")
        print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
        print(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
        print("=" * 60)

        update_env_file(client_id, client_secret, refresh_token)
        print("\nDone! You can now run the pipeline and upload directly to YouTube.")

    except Exception as e:
        print(f"\n[ERROR] Failed to obtain token: {e}")

if __name__ == "__main__":
    main()
