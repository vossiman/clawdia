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

Each household member gets their own librespot instance with a unique device name. Service files are in `scripts/`.

Install a service:
```bash
cp scripts/librespot-gernot.service ~/.config/systemd/user/
cp scripts/librespot-oxana.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now librespot-gernot
systemctl --user enable --now librespot-oxana
sudo loginctl enable-linger vossi   # Survive logout
```

Each instance needs its own OAuth (first-time only, via SSH tunnel):
```bash
ssh -L 8080:127.0.0.1:8080 clawdia
# On the Pi:
~/.cargo/bin/librespot -n clawdia-oxana -d 'UACDemoV1.0' -b 160 \
  --device-type speaker -c /tmp/librespot-cache-oxana \
  --enable-oauth --oauth-port 8080
```

### Verification

```bash
systemctl --user status librespot-gernot
systemctl --user status librespot-oxana
```

The Pi shows up as "clawdia-gernot" and "clawdia-oxana" in the Spotify app's device list. Each user's Telegram commands route to their own device.

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

## Multi-user Spotify

Each household member has their own Spotify account linked to their Telegram chat ID. When vossi sends `/play`, it uses vossi's Spotify. When Oxana sends `/play`, it uses Oxana's Spotify. Both play through the same Pi speaker via librespot — whoever plays last takes over.

### Setup

**1. Add users to Spotify Developer App**

The app is in Development Mode — users must be explicitly added via **User Management** in the Developer Dashboard. Add each user's exact Spotify account email.

**2. Run OAuth for each user**

Use `scripts/oauth_spotify.py` on the Pi (requires a venv with spotipy):

```bash
cd ~/clawdia
python3 -m venv .venv
.venv/bin/pip install spotipy python-dotenv
.venv/bin/python scripts/oauth_spotify.py .spotify_cache_oxana
```

The script prints an auth URL — open it in a browser, authorize, paste the redirect URL back. No SSH tunnel needed.

**3. Configure `.env`**

Map each Telegram chat ID to its cache file and librespot device name:
```
SPOTIFY_USERS=4380413:.spotify_cache:clawdia-gernot,180506269:.spotify_cache_oxana:clawdia-oxana
```

Format: `chat_id:cache_path:device_name[,...]`

The shared `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` are used for all users. If a user needs their own app credentials, append them:
```
SPOTIFY_USERS=4380413:.spotify_cache:clawdia-gernot:id1:secret1,180506269:.spotify_cache_oxana:clawdia-oxana:id2:secret2
```

**4. Volume mounts in `docker-compose.yml`**

Each cache file needs its own mount:
```yaml
volumes:
  - ./.spotify_cache:/app/.spotify_cache
  - ./.spotify_cache_oxana:/app/.spotify_cache_oxana
```

**5. Rebuild and restart**

```bash
git pull && docker compose up -d --build
```

### How it works

- Each user has their own librespot instance (e.g. `clawdia-gernot`, `clawdia-oxana`) — Spotify Connect devices are account-scoped
- `main.py` parses `SPOTIFY_USERS` and creates one `MusicController` per user, each pointing to their own device
- The Telegram bot routes music commands to the correct controller based on `update.effective_chat.id`
- If a chat ID isn't in `SPOTIFY_USERS`, it falls back to the default single-user controller
- The `Brain` and `Orchestrator` get a single default controller (they just need to know music is available)
- If `SPOTIFY_USERS` is empty, everything works as before (single-user mode)

### Adding a new user

1. Add their email to User Management in the Spotify Developer Dashboard
2. Create a librespot service file (`scripts/librespot-<name>.service`) and install it
3. Run librespot OAuth for their account (SSH tunnel + `--enable-oauth`)
4. Run `scripts/oauth_spotify.py .spotify_cache_<name>` on the Pi for the Web API token
5. Add their `chat_id:cache_path:device_name` to `SPOTIFY_USERS` in `.env`
6. Add a volume mount for their cache file in `docker-compose.yml`
7. Restart: `docker compose up -d --build`

### OAuth on the Pi: lessons learned

- The headless Pi can't open a browser — use `open_browser=False` and paste URLs manually
- `docker compose exec` doesn't handle interactive stdin well — use a venv outside Docker instead
- Spotify bans `localhost` as a redirect URI — must use `127.0.0.1`
- Spotify Development Mode `invalid_scope` errors are misleading — they mean the user isn't authorized, not that scopes are wrong. Ensure the email matches exactly and wait for propagation

## What didn't work (for future reference)

- **spotifyd 0.4.x prebuilt binaries:** Linked against OpenSSL 1.1, Debian Trixie has OpenSSL 3. Had to build from source.
- **spotifyd 0.4.1 playback:** OAuth flow registers as free-tier product (`product=0`), all tracks marked "NonPlayable". Switching to librespot 0.8.0 fixed this.
- **spotifyd 0.4.2:** Requires rustc 1.88, Pi has 1.85.
- **`localhost` as redirect URI:** Spotify explicitly bans `localhost` — must use `127.0.0.1`.
- **spotifyd 0.4.1 from source (first attempt):** `cargo install spotifyd` without `--locked` pulled newer dependency versions requiring rustc 1.88. Fixed with `--locked`.
- **librespot 0.8.0 password auth:** Removed in 0.8.0, only OAuth supported. Must use `--enable-oauth` with port forwarding for headless setup.
- **Multi-user OAuth with Development Mode app:** Second user initially got `invalid_scope` — resolved by removing and re-adding the user in User Management and using the manual paste flow (`open_browser=False`) instead of the redirect server.
