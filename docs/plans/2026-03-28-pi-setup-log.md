# Pi Setup Log

**Date:** 2026-03-28
**Status:** Complete

## Hardware

- Raspberry Pi 5, 8GB RAM
- 64GB microSD
- Debian Trixie (13.4), kernel 6.12.75+rpt-rpi-v8, aarch64
- 4 cores, 51GB free disk

## What was done

### OS
- Raspberry Pi OS Lite (64-bit) flashed via Pi Imager
- Hostname: `clawdia`
- User: `vossi`
- WiFi configured, timezone Europe/Vienna, keyboard de

### Security hardening
- SSH key-only auth (ed25519), password auth disabled
- Root login disabled
- UFW firewall: deny all incoming, allow all outgoing, SSH rate-limited
- `unattended-upgrades` enabled for automatic security patches

### Software installed
- Docker 26.1.5
- Docker Compose 2.26.1
- Git 2.47.3
- UFW, unattended-upgrades

### User groups
`vossi` is in: `docker`, `gpio`, `i2c`, `spi`, `audio`, `video`, `input`, `dialout`

All hardware-relevant groups (GPIO, I2C, SPI, audio) are set — ready for HAT and IR wiring.

## SSH access
```
ssh clawdia
```
(Requires `~/.ssh/config` entry pointing to `clawdia.local` with the ed25519 key)

## Next: Phase 1 — Python project foundation
