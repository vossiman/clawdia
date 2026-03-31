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

## Audio routing: PulseAudio

Multiple librespot instances need to share the USB speaker. ALSA doesn't support concurrent access, so we route through PulseAudio.

### Setup

```bash
sudo apt install pulseaudio
systemctl --user enable --now pulseaudio
```

### Route ALSA default through PulseAudio

`~/.asoundrc`:
```
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
```

### Add USB speaker as PulseAudio sink

`~/.config/pulse/default.pa` (append):
```
load-module module-alsa-sink device=plughw:CARD=UACDemoV10,DEV=0 sink_name=usb_speaker
set-default-sink usb_speaker
```

Verify:
```bash
pactl list sinks short   # Should show usb_speaker
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

### Per-user instances

Each household member gets their own librespot instance with a unique device name. Both output to the USB speaker via PulseAudio — whoever plays last takes over. Service files are in `scripts/`.

### First-time OAuth per instance

librespot 0.8.0 requires OAuth (username/password auth removed). Since the Pi is headless, use an SSH port forward:

1. From your local machine:
   ```bash
   ssh -L 8080:127.0.0.1:8080 clawdia
   ```

2. On the Pi (via that SSH session), run librespot manually with `--enable-oauth`:
   ```bash
   ~/.cargo/bin/librespot -n clawdia-gernot -b 160 \
     --device-type speaker -c /tmp/librespot-cache-gernot \
     --enable-oauth --oauth-port 8080
   ```

3. Open the printed URL in your browser, authorize with the correct Spotify account.
4. Credentials are cached (e.g. `/tmp/librespot-cache-gernot`) — subsequent starts don't need OAuth.
5. Ctrl+C, then install and start the service.

### systemd services

Install:
```bash
cp scripts/librespot-gernot.service ~/.config/systemd/user/
cp scripts/librespot-oxana.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now librespot-gernot
systemctl --user enable --now librespot-oxana
sudo loginctl enable-linger vossi   # Survive logout
```

### Verification

```bash
systemctl --user status librespot-gernot   # Authenticated as '116616176'
systemctl --user status librespot-oxana    # Authenticated as 'crazy_snail'
```

## Clawdia Integration

Clawdia (running in Docker) controls Spotify via the **Spotify Web API** using the `spotipy` Python library. It does NOT communicate with librespot directly — the Spotify cloud routes commands to the correct device.

### Required environment variables (.env)

```
SPOTIFY_CLIENT_ID=<from developer.spotify.com>
SPOTIFY_CLIENT_SECRET=<from developer.spotify.com>
SPOTIFY_USERS=4380413:.spotify_cache:clawdia-gernot,180506269:.spotify_cache_oxana:clawdia-oxana
```

### Spotify Developer App setup

1. Register at https://developer.spotify.com/dashboard
2. Create an app
3. Set redirect URI to `http://127.0.0.1:8888/callback` (must use IP, not `localhost` — Spotify rejects `localhost`)
4. Copy Client ID and Client Secret to `.env`
5. Add each user's Spotify email via **User Management** in the dashboard (Development Mode restriction)

### Web API OAuth per user

Use `scripts/oauth_spotify.py` on the Pi (requires a venv with spotipy):

```bash
cd ~/clawdia
python3 -m venv .venv
.venv/bin/pip install spotipy python-dotenv
.venv/bin/python scripts/oauth_spotify.py .spotify_cache_oxana
```

The script prints an auth URL — open it in a browser, authorize as the correct user, paste the redirect URL back. The resulting cache file is bind-mounted into the Docker container.

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

## Multi-user Spotify

Each household member has their own Spotify account linked to their Telegram chat ID. When Gernot sends `/play`, it uses his Spotify and plays on `clawdia-gernot`. When Oxana sends `/play`, it uses her Spotify and plays on `clawdia-oxana`. Both output to the same USB speaker via PulseAudio — whoever plays last takes over.

### How it works

- Each user has their own librespot instance (`clawdia-gernot`, `clawdia-oxana`) — Spotify Connect devices are account-scoped, so each account needs its own device
- `main.py` parses `SPOTIFY_USERS` and creates one `MusicController` per user, each pointing to their own device
- The Telegram bot routes music commands to the correct controller based on `update.effective_chat.id`
- A **PlaybackCoordinator** ensures only one audio source plays at a time — when someone starts playing, the previous playback is automatically stopped (see [Playback Coordinator](#playback-coordinator))
- If a chat ID isn't in `SPOTIFY_USERS`, it falls back to the default single-user controller
- If `SPOTIFY_USERS` is empty, everything works as before (single-user mode)

### SPOTIFY_USERS format

```
SPOTIFY_USERS=chat_id:cache_path:device_name[,...]
```

Example:
```
SPOTIFY_USERS=4380413:.spotify_cache:clawdia-gernot,180506269:.spotify_cache_oxana:clawdia-oxana
```

If a user needs their own Spotify Developer App credentials (separate client_id/secret):
```
SPOTIFY_USERS=4380413:.spotify_cache:clawdia-gernot:id1:secret1,180506269:.spotify_cache_oxana:clawdia-oxana:id2:secret2
```

### Adding a new user

1. Add their email to User Management in the Spotify Developer Dashboard
2. Create a librespot service file (`scripts/librespot-<name>.service`) — copy an existing one, change the device name and cache dir
3. Run librespot OAuth for their account (SSH tunnel + `--enable-oauth`)
4. Install and start the service: `systemctl --user enable --now librespot-<name>`
5. Run `scripts/oauth_spotify.py .spotify_cache_<name>` on the Pi for the Web API token
6. Add their `chat_id:cache_path:device_name` to `SPOTIFY_USERS` in `.env`
7. Add a volume mount for their cache file in `docker-compose.yml`
8. Restart: `docker compose up -d --build`

## Playback Coordinator

The Pi has one speaker in a shared living room. Only one audio source should play at a time. The `PlaybackCoordinator` enforces this globally — when anyone starts playing anything, whatever was previously playing is automatically stopped.

### How it works

- All playback commands (slash commands like `/play`, `/playlist`, and natural language like "play some jazz") go through the coordinator
- The coordinator tracks a global `PlaybackState`: who is playing, what service, what content, and since when
- When a new play command comes in from a different service, the coordinator calls the previous service's stop callback before starting the new one
- If the stop callback fails (e.g. Spotify API is down), the new playback proceeds anyway
- Read-only commands (`/np`, `/vol`, `/playlists`) bypass the coordinator

### Brain awareness

The brain's system prompt includes the current playback state, e.g.:
```
Currently playing: No Surprises by Radiohead (spotify:4380413, since 3 min ago)
```
This lets the LLM reason about playback: "pausing Oxana's music to play your request", or answer "what's playing?" without an API call.

### Architecture

```
src/clawdia/playback/
├── __init__.py          # exports PlaybackCoordinator
└── coordinator.py       # PlaybackCoordinator + PlaybackState
```

- `PlaybackCoordinator` is created in `main.py` at startup
- Each music controller registers via `coordinator.register_service("spotify:<chat_id>", stop=mc.pause)`
- The coordinator is passed to `Brain` (for prompt injection), `ClawdiaTelegramBot` (for command routing), and `Orchestrator` (for voice command routing)
- Future services (web radio, Emby) register the same way with their own stop callbacks

### Adding a new audio service

1. Create the service controller (e.g. `WebRadioController`) with a `pause()` or `stop()` method
2. Register it: `coordinator.register_service("webradio", stop=radio.stop)`
3. Route play commands through `coordinator.play(service="webradio", ...)`
4. The coordinator handles stopping whatever was previously playing

## Troubleshooting

### "Spotify device 'clawdia-xxx' not found or offline"
- Check librespot is running: `systemctl --user status librespot-gernot`
- Check it authenticated: logs should show `Authenticated as '...'`
- If credentials expired, re-run the librespot OAuth flow (SSH tunnel + `--enable-oauth`)

### No audio from speaker
- Check PulseAudio: `pactl list sinks short` — usb_speaker should be listed
- Check volume: `amixer -c 3 set PCM 100%`
- Test PulseAudio directly: `paplay /usr/share/sounds/freedesktop/stereo/bell.oga`
- Check librespot logs: `systemctl --user status librespot-gernot`

### Wrong search results
- Spotify's search API can return unexpected results with `limit=1`. We use `limit=5` and take the first result for better accuracy.

### Two librespot instances can't share audio
- Both instances must route through PulseAudio, not ALSA directly
- Verify `~/.asoundrc` routes the ALSA default to PulseAudio
- librespot 0.8.0 uses the `rodio` backend (ALSA) — no `--backend pulseaudio` flag, but rodio respects the ALSA default from `.asoundrc`

## What didn't work (for future reference)

- **spotifyd 0.4.x prebuilt binaries:** Linked against OpenSSL 1.1, Debian Trixie has OpenSSL 3. Had to build from source.
- **spotifyd 0.4.1 playback:** OAuth flow registers as free-tier product (`product=0`), all tracks marked "NonPlayable". Switching to librespot 0.8.0 fixed this.
- **spotifyd 0.4.2:** Requires rustc 1.88, Pi has 1.85.
- **`localhost` as redirect URI:** Spotify explicitly bans `localhost` — must use `127.0.0.1`.
- **spotifyd 0.4.1 from source (first attempt):** `cargo install spotifyd` without `--locked` pulled newer dependency versions requiring rustc 1.88. Fixed with `--locked`.
- **librespot 0.8.0 password auth:** Removed in 0.8.0, only OAuth supported. Must use `--enable-oauth` with port forwarding for headless setup.
- **Multi-user OAuth with Development Mode app:** Second user initially got `invalid_scope` — resolved by removing and re-adding the user in User Management and using the manual paste flow (`open_browser=False`) instead of the redirect server.
- **Cross-account device control via API:** Tried having all users share one librespot instance and routing playback commands through the device owner's API client. Doesn't work — `start_playback` with another account's device ID returns 404.
- **Two librespot instances with ALSA directly (`-d UACDemoV1.0`):** ALSA doesn't allow concurrent exclusive access. Second instance crashes. Fixed by routing through PulseAudio.
- **librespot `--backend pulseaudio`:** Not available — librespot 0.8.0 built with default features only has `rodio`, `pipe`, `subprocess`. Workaround: route ALSA default through PulseAudio via `~/.asoundrc`.
