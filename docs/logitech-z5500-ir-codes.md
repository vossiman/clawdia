# Logitech Z-5500 Digital IR Codes Reference

## System

Logitech Z-5500 Digital — 5.1 surround sound system.

## IR Setup

- Protocol: NEC Extended, 38 kHz carrier, 32-bit
- Recorded from universal remote (NEC Extended, address `0x02A0`)
- Standard Z-5500 database codes (NEC address `0x08`) do NOT work on this unit

## Recorded Commands (working)

| Command | File | Description |
|---|---|---|
| `sound_power_toggle` | `sound_power_toggle.txt` | Toggle power on/off |
| `sound_vol_up` | `sound_vol_up.txt` | Volume up |
| `sound_vol_down` | `sound_vol_down.txt` | Volume down |
| `sound_mute` | `sound_mute.txt` | Mute/unmute |

Use `/record <name> <description>` via Telegram to add more commands.

## Not Yet Recorded

These functions exist on the remote but haven't been recorded yet:

- Input selection (Direct, Optical, Coaxial)
- Effect / DSP mode cycle
- Subwoofer level up/down
- Center channel level up/down
- Surround level up/down
- Settings/Menu

Bass and treble have no IR codes — only adjustable via the control pod LCD menu.
