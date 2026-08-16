import os
from dotenv import load_dotenv
from supabase import create_client, Client

def main():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("Supabase credentials not found in environment!")
        return

    print(f"Connecting to Supabase at: {url}...")
    try:
        import traceback
        try:
            supabase: Client = create_client(url, key)
            print("Connected! Verifying tables...")
        except Exception as conn_err:
            print("Connection creation failed:")
            traceback.print_exc()
            return
        
        # Test settings table
        try:
            res = supabase.table("settings").select("*").limit(1).execute()
            print("Table 'settings': EXISTS")
        except Exception as e:
            print(f"Table 'settings': MISSING or ERROR:")
            traceback.print_exc()
            
        # Test video_jobs table
        try:
            res = supabase.table("video_jobs").select("*").limit(1).execute()
            print("Table 'video_jobs': EXISTS")
        except Exception as e:
            print(f"Table 'video_jobs': MISSING or ERROR:")
            traceback.print_exc()
            
    except Exception as e:
        print(f"General failure: {e}")

if __name__ == "__main__":
    main()
