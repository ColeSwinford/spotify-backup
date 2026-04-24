import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
from datetime import datetime
import time
import requests

# Configuration
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:5173/"
SCOPE = "user-library-read playlist-read-private playlist-read-collaborative"
BACKUP_DIR = "/data"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
IS_TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


def send_discord_msg(content):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": content}, timeout=10)
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")


def get_all_items(sp, results):
    """Paginates through Spotify results with rate-limit safety."""
    items = results["items"]
    if IS_TEST_MODE:
        return items

    while results["next"]:
        results = sp.next(results)
        items.extend(results["items"])
        # 0.5s sleep prevents 429 Rate Limit hits on large libraries
        time.sleep(0.5)
    return items


def extract_track_metadata(item):
    """Standardizes high-fidelity metadata extraction for both likes and playlists."""
    # February 2026 Fix: Playlists now use 'item', Liked Songs still use 'track'
    track = item.get("track") or item.get("item")

    if not track:
        return None

    # Capture all critical data points for library recreation
    return {
        "name": track.get("name"),
        "artist": ", ".join([a["name"] for a in track.get("artists", [])]),
        "album": track.get("album", {}).get("name"),
        "release_date": track.get("album", {}).get("release_date"),
        "isrc": track.get("external_ids", {}).get("isrc"),
        "uri": track.get("uri"),
        "added_at": item.get("added_at"),
        "duration_ms": track.get("duration_ms"),
        "explicit": track.get("explicit"),
    }


def main():
    start_time = time.time()
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=REDIRECT_URI,
                scope=SCOPE,
                open_browser=False,
                cache_path="/data/.cache",
            ),
            requests_timeout=20,
            retries=5,
        )

        data = {
            "backup_info": {"date": run_timestamp, "is_test": IS_TEST_MODE},
            "liked_songs": [],
            "playlists": [],
        }

        # Identify Current User for Strict Ownership Check
        current_user = sp.current_user()
        my_user_id = current_user["id"]
        print(f"Logged in as: {my_user_id}", flush=True)

        # 1. Fetch Liked Songs (Hard cap 50 per request)
        print("Fetching Liked Songs...", flush=True)
        results = sp.current_user_saved_tracks(limit=50)
        tracks = get_all_items(sp, results)
        data["liked_songs"] = [
            t for t in (extract_track_metadata(i) for i in tracks) if t
        ]

        # 2. Fetch Playlists
        print("Fetching Playlists...", flush=True)
        playlists_results = sp.current_user_playlists(limit=50)
        all_playlists = get_all_items(sp, playlists_results)

        playlist_count = 0
        skipped_playlists = 0

        for pl in all_playlists:
            # Strict Ownership Check: Skip if you do not own it
            if pl["owner"]["id"] != my_user_id:
                print(f"   [SKIPPED] Not Owner: '{pl['name']}'", flush=True)
                skipped_playlists += 1
                continue

            if IS_TEST_MODE and playlist_count >= 2:
                break

            playlist_count += 1
            print(f"   Vaulting Playlist: {pl['name']}", flush=True)

            # Limit 100 is allowed for playlist items
            try:
                pl_tracks_results = sp.playlist_items(pl["id"], limit=100)
                pl_tracks = get_all_items(sp, pl_tracks_results)
            except spotipy.exceptions.SpotifyException as e:
                # Catch 403s or any other API hiccups
                print(f"   [ERROR] Failed to fetch '{pl['name']}': {e}", flush=True)
                skipped_playlists += 1
                continue

            p_data = {
                "name": pl["name"],
                "id": pl["id"],
                "description": pl.get("description"),
                "tracks": [
                    t for t in (extract_track_metadata(i) for i in pl_tracks) if t
                ],
            }
            data["playlists"].append(p_data)

            # Cooldown between playlists to respect API limits
            time.sleep(1.0)

        # 3. Save to JSON
        filename = f"{BACKUP_DIR}/spotify_backup_{run_timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # 4. Final Logging and Notification
        elapsed = round(time.time() - start_time, 2)
        msg = (
            f"**Spotify Vault Backup Successful** ✅\n"
            f"📅 Date: {run_timestamp}\n"
            f"🎵 Liked Songs: {len(data['liked_songs'])}\n"
            f"📂 Playlists Vaulted: {len(data['playlists'])}\n"
            f"⚠️ Playlists Skipped: {skipped_playlists}\n"
            f"⏱️ Time: {elapsed}s"
        )
        send_discord_msg(msg)
        print(msg)

    except Exception as e:
        send_discord_msg(
            f"@everyone **Spotify Vault Backup FAILED** ❌\n🚨 Error: `{str(e)}`"
        )
        raise e


if __name__ == "__main__":
    main()
