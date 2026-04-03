"""Generate a Spotify OAuth cache file for a user.

Usage:
    python oauth_spotify.py <cache_path>
    python oauth_spotify.py .spotify_cache_oxana
    python oauth_spotify.py .spotify_cache
"""

import sys

from dotenv import load_dotenv

load_dotenv()
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <cache_path>")
    print(f"Example: {sys.argv[0]} .spotify_cache_oxana")
    sys.exit(1)

cache_path = sys.argv[1]

auth = SpotifyOAuth(
    client_id=os.environ["SPOTIFY_CLIENT_ID"],
    client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative",
    cache_handler=spotipy.CacheFileHandler(cache_path=cache_path),
    open_browser=False,
)
url = auth.get_authorize_url()
print(f"\nOpen this URL in your browser:\n\n{url}\n")
print("After authorizing, paste the full redirect URL here:")
response_url = input("> ").strip()
code = auth.parse_response_code(response_url)
token = auth.get_access_token(code)
if token:
    sp = spotipy.Spotify(auth=token["access_token"])
    print(f"\nAuthenticated as: {sp.current_user()['display_name']}")
    print(f"Cache saved to {cache_path}")
else:
    print("Failed to get token")
