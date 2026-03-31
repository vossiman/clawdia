# Raspberry Pi Audio & Spotify Setup

## Hardware

- **USB Speaker:** Jieli Technology UACDemoV1.0
  - ALSA card 3: `UACDemoV10`
  - Playback device: `plughw:CARD=UACDemoV10,DEV=0`
  - Mixer control: `PCM` (card 3)

Verify with:
```bash
aplay -l                          # List audio devices
speaker-test -D plughw:CARD=UACDemoV10,DEV=0 -c 2 -t sine -l 1  # Test tone
amixer -c 3 get PCM               # Check volume
amixer -c 3 set PCM 100%          # Max volume
```

## Spotify Connect: librespot

We use **librespot 0.8.0** (not spotifyd) as the Spotify Connect daemon. spotifyd 0.4.x has a bug where its OAuth flow registers as `product=0` (free tier), causing all tracks to be marked "NonPlayable" even with a Premium account. librespot handles OAuth correctly.

### Installation

Built from source on the Pi (rustc 1.85, Debian Trixie):

```bash
sudo apt-get install -y cargo libssl-dev libasound2-dev
cargo install librespot --locked
```

Binary location: `~/.cargo/bin/librespot`

### First-time OAuth authentication

librespot 0.8.0 requires OAuth (username/password auth removed). Since the Pi is headless, use an SSH port forward:

1. From your local machine:
   ```bash
   ssh -L 8080:127.0.0.1:8080 clawdia
   ```

2. On the Pi (via that SSH session):
   ```bash
   ~/.cargo/bin/librespot -n clawdia -d 'UACDemoV1.0' -b 160 \
     --device-type speaker -c /tmp/librespot-cache \
     --enable-oauth --oauth-port 8080
   ```

3. Open the printed URL in your browser, authorize with Spotify.
4. Credentials are cached at `/tmp/librespot-cache` — subsequent starts don't need OAuth.

### systemd service

File: `~/.config/systemd/user/librespot.service`

```ini
[Unit]
Description=Librespot Spotify Connect
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/vossi/.cargo/bin/librespot -n clawdia -d UACDemoV1.0 -b 160 --device-type speaker -c /tmp/librespot-cache
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now librespot
sudo loginctl enable-linger vossi   # Survive logout
```

### Verification

```bash
systemctl --user status librespot   # Should show "Authenticated as '116616176'"
```

The Pi shows up as "clawdia" in the Spotify app's device list and can receive playback commands via both the Spotify app (Spotify Connect) and Clawdia's Telegram bot / Web API.

## Clawdia Integration

Clawdia (running in Docker) controls Spotify via the **Spotify Web API** using the `spotipy` Python library. It does NOT communicate with librespot directly — the Spotify cloud routes commands to the correct device.

### Required environment variables (.env)

```
SPOTIFY_CLIENT_ID=<from developer.spotify.com>
SPOTIFY_CLIENT_SECRET=<from developer.spotify.com>
```

### Spotify Developer App setup

1. Register at https://developer.spotify.com/dashboard
2. Create an app
3. Set redirect URI to `http://127.0.0.1:8888/callback` (must use IP, not `localhost` — Spotify rejects `localhost`)
4. Copy Client ID and Client Secret to `.env`

### One-time Web API OAuth

Run locally (not on the Pi — needs a browser redirect):

```bash
cd /path/to/clawdia
uv run python -c "
from dotenv import load_dotenv
load_dotenv()
import os, spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.environ['SPOTIFY_CLIENT_ID'],
    client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
    redirect_uri='http://127.0.0.1:8888/callback',
    scope='user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative',
    cache_handler=spotipy.CacheFileHandler(cache_path='.spotify_cache'),
))
print(f'Authenticated as: {sp.current_user()[\"display_name\"]}')
"
```

Copy the resulting `.spotify_cache` file to the Pi at `/home/vossi/clawdia/.spotify_cache`. The Docker container bind-mounts this file. The refresh token auto-renews indefinitely.

### Telegram commands

| Command | Action |
|---|---|
| `/play <query>` | Search + play top result |
| `/pause` | Pause playback |
| `/skip` | Next track |
| `/prev` | Previous track |
| `/np` | Show what's currently playing |
| `/vol <0-100>` | Set volume |
| `/playlist <name>` | Find and play a playlist |
| `/queue <query>` | Add a track to the queue |
| `/playlists` | List your playlists |

Natural language also works: "play some jazz", "skip this song", "what's playing" — the brain routes these to the music controller.

## Troubleshooting

### "Spotify device 'clawdia' not found or offline"
- Check librespot is running: `systemctl --user status librespot`
- Check it authenticated: logs should show `Authenticated as '116616176'`
- If credentials expired, re-run the OAuth flow (SSH tunnel + `--enable-oauth`)

### No audio from speaker
- Test speaker directly: `speaker-test -D plughw:CARD=UACDemoV10,DEV=0 -c 2 -t sine -l 1`
- Check volume: `amixer -c 3 set PCM 100%`
- Check librespot logs: `journalctl --user -u librespot -n 20`

### Wrong search results
- Spotify's search API can return unexpected results with `limit=1`. We use `limit=5` and take the first result for better accuracy.

## Multi-user Spotify (WIP)

### Goal

Each household member gets their own Spotify account linked to their Telegram chat ID. When vossi sends `/play`, it uses vossi's Spotify. When Oxana sends `/play`, it uses Oxana's Spotify. Both play through the same Pi speaker via librespot.

### Current state

- **vossi (chat ID 4380413):** Fully working. Has `.spotify_cache` with valid refresh token.
- **Oxana (chat ID 180506269):** Needs her own `.spotify_cache_oxana` — OAuth not yet completed.

### Planned approach

Config: per-user Spotify credentials via env var mapping chat IDs to cache files:
```
SPOTIFY_USERS=4380413:.spotify_cache,180506269:.spotify_cache_oxana
```

The Spotify Developer App (client_id/secret) is shared — it's the app, not the user. Each user just needs their own OAuth token (refresh token stored in their cache file).

Code changes needed:
- `MusicController` stays the same — one instance per user
- `main.py` creates a dict of `chat_id → MusicController`
- Telegram bot picks the right controller based on `update.effective_chat.id`
- librespot on the Pi stays as one device — whoever plays last takes over the speaker

### Blocker: Spotify Developer App in Development Mode

Spotify apps in "Development Mode" restrict which users can authorize. Users must be explicitly added via **User Management** in the Developer Dashboard.

**Problem:** After adding Oxana's email to User Management, the OAuth flow returns `invalid_scope` for her — even though the exact same scopes work for vossi's account. This is a known misleading error from Spotify's Development Mode — it means the user isn't properly authorized, not that the scopes are invalid.

**What we tried:**
- Verified Oxana's email matches her Spotify account exactly
- Removed and re-added her in User Management
- Waited several minutes between retries
- Tried with minimal scopes (just `user-read-playback-state`) — same error
- Tried incognito browser windows
- No confirmation email was sent to Oxana (Spotify may not always send one)

**Possible solutions (not yet tried):**
1. **Oxana creates her own Spotify Developer App** — she registers at developer.spotify.com with her account, creates an app, and we store her client_id/secret separately. Each user would have their own app credentials.
2. **Request "Extended Quota Mode"** for the app via the Spotify Developer Dashboard — this removes the user restriction but requires Spotify review.
3. **Wait and retry** — Spotify's User Management propagation can be slow or buggy.

### OAuth on the Pi: lessons learned

Running the spotipy OAuth flow on the Pi is painful because:
- No `uv` installed on the Pi (dependencies managed via Docker)
- No `pip` installed by default (Debian Trixie, had to `apt install python3-pip`)
- System Python is 3.13, Docker uses 3.12 — version mismatch possible
- `source .env` doesn't export vars properly for Python's `os.environ`
- Interactive OAuth in `docker compose exec` doesn't handle stdin well

**What works:** Use the Docker container to generate the auth URL (`open_browser=False`), then manually paste the redirect URL back. Or run the OAuth locally where you have `uv` and a browser, then `scp` the cache file to the Pi.

**Recommended approach for future OAuth flows:**
1. Generate auth URL via Docker: `docker compose exec -T clawdia python3 -c "..."`
2. Open URL in browser, authorize
3. Copy the redirect URL (the `?code=...` part)
4. Exchange the code via Docker: `docker compose exec -T clawdia python3 -c "..."` with the code

## What didn't work (for future reference)

- **spotifyd 0.4.x prebuilt binaries:** Linked against OpenSSL 1.1, Debian Trixie has OpenSSL 3. Had to build from source.
- **spotifyd 0.4.1 playback:** OAuth flow registers as free-tier product (`product=0`), all tracks marked "NonPlayable". Switching to librespot 0.8.0 fixed this.
- **spotifyd 0.4.2:** Requires rustc 1.88, Pi has 1.85.
- **`localhost` as redirect URI:** Spotify explicitly bans `localhost` — must use `127.0.0.1`.
- **spotifyd 0.4.1 from source (first attempt):** `cargo install spotifyd` without `--locked` pulled newer dependency versions requiring rustc 1.88. Fixed with `--locked`.
- **librespot 0.8.0 password auth:** Removed in 0.8.0, only OAuth supported. Must use `--enable-oauth` with port forwarding for headless setup.
- **Multi-user OAuth with Development Mode app:** Second user gets `invalid_scope` even with correct User Management setup. Spotify's error message is misleading — it's an authorization issue, not a scope issue.
