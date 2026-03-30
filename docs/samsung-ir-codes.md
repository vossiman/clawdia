# Samsung TV IR Codes Reference

## TV Model

Samsung PS59D578C2S — 59" Plasma, D-series (2011).

## IR Setup

- Protocol: Samsung32 (NEC variant), 38 kHz carrier, 32-bit
- Device address: `0xE0E0` (universal across Samsung TVs)
- Transmitter: KY-005 IR LED via 2N2222 transistor on GPIO 23 (`/dev/lirc0`)
- Receiver: KY-022 (VS1838B) on GPIO 22 (`/dev/lirc1`)

**Known issue:** IR signal too weak at 3m — plasma panel EM noise drowns it out
when the screen is on. Power ON works at any range (panel off in standby = clean
reception). All commands work at ~1m. Currently using 3x KY-005 in parallel,
10 more ordered (13 total). Pi is not connected via HDMI so CEC is not available.
Soundbar handles all volume (separate remote/protocol).

## Usage

Use `IRController.generate_code_file(name, hex_code, description)` to create
ir-ctl raw files from any code below.

## Power

| Function | Hex Code |
|---|---|
| Power Toggle | `0xE0E040BF` |
| Discrete Power ON | `0xE0E09966` |
| Discrete Power OFF | `0xE0E019E6` |

## HDMI / Input

| Function | Hex Code |
|---|---|
| Source (cycle) | `0xE0E0807F` |
| HDMI 1 | `0xE0E09768` |
| HDMI 2 | `0xE0E07D82` |
| HDMI 3 | `0xE0E043BC` |
| HDMI 4 | `0xE0E0A35C` |
| TV / DTV | `0xE0E0D827` |
| Component | `0xE0E0619E` |
| AV Input | `0xE0E037C8` |
| PC Input | `0xE0E09669` |

## Volume

| Function | Hex Code |
|---|---|
| Volume Up | `0xE0E0E01F` |
| Volume Down | `0xE0E0D02F` |
| Mute | `0xE0E0F00F` |

## Channel

| Function | Hex Code |
|---|---|
| Channel Up | `0xE0E048B7` |
| Channel Down | `0xE0E008F7` |
| Previous Channel | `0xE0E0C837` |
| Channel List | `0xE0E0D629` |
| Favourite Channel | `0xE0E022DD` |

## Number Buttons

| Function | Hex Code |
|---|---|
| 0 | `0xE0E08877` |
| 1 | `0xE0E020DF` |
| 2 | `0xE0E0A05F` |
| 3 | `0xE0E0609F` |
| 4 | `0xE0E010EF` |
| 5 | `0xE0E0906F` |
| 6 | `0xE0E050AF` |
| 7 | `0xE0E030CF` |
| 8 | `0xE0E0B04F` |
| 9 | `0xE0E0708F` |
| Dash (-) | `0xE0E0C43B` |

## Navigation

| Function | Hex Code |
|---|---|
| Up | `0xE0E006F9` |
| Down | `0xE0E08679` |
| Left | `0xE0E0A659` |
| Right | `0xE0E046B9` |
| Enter / OK | `0xE0E016E9` |
| Return / Back | `0xE0E01AE5` |
| Exit | `0xE0E0B44B` |

## Menu / Settings

| Function | Hex Code |
|---|---|
| Menu | `0xE0E058A7` |
| Smart Hub / Home | `0xE0E09E61` |
| Guide / EPG | `0xE0E0F20D` |
| Tools | `0xE0E0D22D` |
| Info | `0xE0E0F807` |

## Media / Playback

| Function | Hex Code |
|---|---|
| Play | `0xE0E0E21D` |
| Pause | `0xE0E052AD` |
| Stop | `0xE0E0629D` |
| Rewind | `0xE0E0A25D` |
| Fast Forward | `0xE0E012ED` |
| Record | `0xE0E0926D` |

## Color Buttons

| Function | Hex Code |
|---|---|
| Red (A) | `0xE0E036C9` |
| Green (B) | `0xE0E028D7` |
| Yellow (C) | `0xE0E0A857` |
| Blue (D) | `0xE0E06897` |

## Picture / Sound / Display

| Function | Hex Code |
|---|---|
| Picture Size | `0xE0E07C83` |
| Picture Mode | `0xE0E014EB` |
| Sound Mode | `0xE0E0D42B` |
| Subtitles | `0xE0E0A45B` |
| Teletext | `0xE0E034CB` |
| Still / Freeze | `0xE0E042BD` |

## PIP (Picture-in-Picture)

| Function | Hex Code |
|---|---|
| PIP On/Off | `0xE0E004FB` |
| PIP Swap | `0xE0E0847B` |
| PIP Position | `0xE0E044BB` |

## Timer

| Function | Hex Code |
|---|---|
| Sleep Timer | `0xE0E0C03F` |

## Sources

- [Tasmota IR Codes](https://tasmota.github.io/docs/Codes-for-IR-Remotes/)
- [Arduino Forum - Samsung IR codes](https://forum.arduino.cc/t/samsung-and-lg-tv-ir-codes/1145086)
- [Home Assistant - Samsung discrete codes](https://community.home-assistant.io/t/ir-remote-transmitter-discrete-codes-for-samsung-lcd-on-off/215925)
- [Flipper-IRDB Samsung](https://github.com/Lucaslhm/Flipper-IRDB/tree/main/TVs/Samsung)
- [Arduino-IRremote Samsung protocol](https://github.com/Arduino-IRremote/Arduino-IRremote/blob/master/src/ir_Samsung.hpp)
