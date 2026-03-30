---
name: raspi-deploy
description: Use when connecting to the Raspberry Pi, checking if code is up to date, deploying changes, or troubleshooting the Pi environment. Triggers on "raspi", "pi", "deploy", "update the pi", "is the pi up to date".
---

# Raspberry Pi Deploy

Connect to the Clawdia Raspberry Pi and sync code.

## Connection

```bash
ssh clawdia
```

Requires `~/.ssh/config` entry (host `clawdia`, IP `10.0.0.144`, user `vossi`, key `~/.ssh/clawdia`).

## Check if code is up to date

```bash
ssh clawdia "cd /home/vossi/clawdia && git fetch origin && git status && git log --oneline HEAD..origin/main"
```

- **No output from `git log`** = up to date
- **Commits listed** = Pi is behind by that many commits

## Update code

### Clean pull (no local changes)

```bash
ssh clawdia "cd /home/vossi/clawdia && git pull"
```

### Manual copy was done (local changes match remote)

This happens when files were copied via scp instead of git pull. The working tree has uncommitted changes that duplicate what's in remote commits.

1. Verify local changes match remote:
   ```bash
   ssh clawdia "cd /home/vossi/clawdia && git diff --stat origin/main"
   ```
   If the only diffs are untracked files (shown as deletions from origin/main's perspective), the tracked changes are identical.

2. Discard local changes and remove conflicting untracked files:
   ```bash
   ssh clawdia "cd /home/vossi/clawdia && git checkout . && rm <conflicting files> && git pull"
   ```

### Genuine local changes exist

Stash first, then pull:
```bash
ssh clawdia "cd /home/vossi/clawdia && git stash && git pull && git stash pop"
```

## Pi details

- Raspberry Pi 5, 8GB RAM, Debian Trixie (aarch64)
- Docker 26.1.5, Docker Compose 2.26.1
- Repo path: `/home/vossi/clawdia`
- Remote: `https://github.com/vossiman/clawdia.git`
