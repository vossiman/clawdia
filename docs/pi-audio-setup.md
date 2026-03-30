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

## What didn't work (for future reference)

- **spotifyd 0.4.x prebuilt binaries:** Linked against OpenSSL 1.1, Debian Trixie has OpenSSL 3. Had to build from source.
- **spotifyd 0.4.1 playback:** OAuth flow registers as free-tier product (`product=0`), all tracks marked "NonPlayable". Switching to librespot 0.8.0 fixed this.
- **spotifyd 0.4.2:** Requires rustc 1.88, Pi has 1.85.
- **`localhost` as redirect URI:** Spotify explicitly bans `localhost` — must use `127.0.0.1`.
