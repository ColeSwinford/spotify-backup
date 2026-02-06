import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
from datetime import datetime
import time
import requests
import glob

# Configuration
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:5173/"
SCOPE = "user-library-read playlist-read-private"
BACKUP_DIR = "/data"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
IS_TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Load AppSettings
try:
    with open("/app/appsettings.json", "r") as f:
        settings = json.load(f)
        RETENTION_DAYS = settings.get("BackupRetentionDays", 30)
except FileNotFoundError:
    print("Warning: appsettings.json not found. Defaulting to 30 days retention.")
    RETENTION_DAYS = 30

def send_discord_msg(content):
    if not DISCORD_WEBHOOK: return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": content})
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

def get_all_items(sp, results):
    items = results['items']
    
    # <--- TEST MODE LOGIC --->
    if IS_TEST_MODE:
        print("   [Test Mode] Skipping pagination to save time.")
        return items 
    # <--- END TEST MODE LOGIC --->

    # Track count
    count = len(items)

    while results['next']:
        print(f"   ...fetching next batch (Total so far: {count})", flush=True)
        results = sp.next(results)
        items.extend(results['items'])
        count += len(results['items'])
        time.sleep(0.1)
    return items

def cleanup_old_backups():
    deleted_count = 0
    now = datetime.now()
    files = glob.glob(os.path.join(BACKUP_DIR, "spotify_backup_*.json"))
    
    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            date_part = filename.replace("spotify_backup_", "").replace(".json", "")
            file_date = datetime.strptime(date_part, "%Y-%m-%d")
            age = (now - file_date).days
            if age > RETENTION_DAYS:
                os.remove(filepath)
                deleted_count += 1
                print(f"Deleted old backup: {filename} ({age} days old)")
        except ValueError:
            continue
    return deleted_count

def main():
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    try:
        if IS_TEST_MODE:
            print(f"[{timestamp}] Starting QUICK TEST backup...")
        else:
            print(f"[{timestamp}] Starting backup...")
        
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            open_browser=False,
            cache_path="/data/.cache"
        ))

        data = {
            "backup_date": timestamp,
            "liked_songs": [],
            "playlists": []
        }

        # 1. Fetch Liked Songs
        results = sp.current_user_saved_tracks(limit=50) # In test mode, get_all_items stops after this
        tracks = get_all_items(sp, results)
        
        for item in tracks:
            track = item['track']
            data['liked_songs'].append({
                "name": track['name'],
                "artist": ", ".join([artist['name'] for artist in track['artists']]),
                "uri": track['uri']
            })
            
        # 2. Fetch Playlists
        playlists_results = sp.current_user_playlists(limit=50)
        all_playlists = get_all_items(sp, playlists_results)
        
        playlist_count = 0
        for pl in all_playlists:
            if pl['owner']['id'] == 'spotify': continue
            
            # <--- TEST MODE BREAK --->
            if IS_TEST_MODE and playlist_count >= 2: 
                print("   [Test Mode] Stopping after 2 playlists.")
                break
            # <--- END TEST MODE BREAK --->
            
            playlist_count += 1
            pl_tracks_results = sp.playlist_items(pl['id'], limit=100)
            pl_tracks = get_all_items(sp, pl_tracks_results)
            
            p_data = {
                "name": pl['name'],
                "id": pl['id'],
                "tracks": []
            }
            for item in pl_tracks:
                if item['track']:
                    p_data['tracks'].append({
                        "name": item['track'].get('name', 'Unknown'),
                        "uri": item['track'].get('uri', '')
                    })
            data['playlists'].append(p_data)

        # 3. Save
        filename = f"{BACKUP_DIR}/spotify_backup_{timestamp}.json"
        with open(filename, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        deleted_files = cleanup_old_backups()
        elapsed = round(time.time() - start_time, 2)
        song_count = len(data['liked_songs'])
        
        # Add [TEST] tag to discord message if testing
        title = "**Spotify TEST Backup Successful**" if IS_TEST_MODE else "**Spotify Backup Successful**"
        
        msg = (f"{title} ✅\n"
               f"📅 Date: {timestamp}\n"
               f"🎵 Liked Songs: {song_count}\n"
               f"📂 Playlists: {playlist_count}\n"
               f"🗑️ Cleaned: {deleted_files}\n"
               f"⏱️ Time: {elapsed}s")
        send_discord_msg(msg)
        print(msg)

    except Exception as e:
        error_msg = f"**Spotify Backup FAILED** ❌\n🚨 Error: `{str(e)}`"
        send_discord_msg(error_msg)
        raise e

if __name__ == "__main__":
    main()