# Logitech Z-5500 Digital IR Codes Reference

## System

Logitech Z-5500 Digital — 5.1 surround sound system.

## IR Setup

- Protocol: NEC (standard NEC1), 38 kHz carrier, 32-bit
- NEC address: `0x08`, address complement: `0xF7`
- Each byte sent LSB first

**Note:** The Z-5500 database codes (NEC address `0x08`) do NOT work on this unit.
All commands are recorded from a universal remote (NEC Extended, address `0x02A0`).
The database codes below are kept for reference only — use `/record` to add new commands.

## Usage

Use `IRController.generate_code_file(name, nec_address=0x08, nec_command=<cmd>, description=...)`
to create ir-ctl raw files from any code below.

## Essential Commands

| Function | NEC Cmd | Description |
|---|---|---|
| Power On/Off | `0x10` | Toggle power |
| Volume Up | `0x1A` | Increase volume |
| Volume Down | `0x0E` | Decrease volume |
| Mute | `0x16` | Mute/unmute |

## Input Selection

| Function | NEC Cmd | Description |
|---|---|---|
| Direct | `0x0A` | 3.5mm analog input |
| Optical | `0x0B` | Optical digital input |
| Coaxial | `0x0C` | Coaxial digital input |
| Stereo 1 | `0x13` | Stereo input 1 (discrete) |
| Stereo 2 | `0x1B` | Stereo input 2 (discrete) |
| Stereo 3 | `0x18` | Stereo input 3 (discrete) |

## DSP / Settings

| Function | NEC Cmd | Description |
|---|---|---|
| Effect | `0x1D` | Cycle DSP modes |
| Settings/Menu | `0x1F` | Open settings menu |
| Test | `0x05` | Speaker test tone |

## Level Adjustment

| Function | NEC Cmd | Description |
|---|---|---|
| Subwoofer Up | `0x03` | Increase subwoofer level |
| Subwoofer Down | `0x01` | Decrease subwoofer level |
| Center Up | `0x02` | Increase center channel |
| Center Down | `0x06` | Decrease center channel |
| Surround Up | `0x00` | Increase surround level |
| Surround Down | `0x04` | Decrease surround level |

Bass and treble have no IR codes — only adjustable via the control pod LCD menu.

## Sources

- [LIRC Remote Database: Z-5500D.lircd.conf](https://sourceforge.net/p/lirc-remotes/code/ci/master/tree/remotes/logitech/Z-5500D.lircd.conf)
- [Flipper-IRDB: Logitech_Z-5500.ir](https://github.com/Lucaslhm/Flipper-IRDB/blob/main/Speakers/Logitech/Logitech_Z-5500.ir)
- [Homey app: com.logitech.soundsystems](https://github.com/IvoDerksen/com.logitech.soundsystems)
