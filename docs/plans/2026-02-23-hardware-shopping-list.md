# Clawdia - Hardware Shopping List

**Date:** 2026-02-23

## What You Already Have

| Item | Notes |
|------|-------|
| Raspberry Pi 4B | Main unit. Check RAM with `cat /proc/meminfo` when you boot it. |
| Raspberry Pi 3B+ | Future use (satellite node, experiments) |
| Display shield | Future use (status display) |
| Camera module | Future use |
| MicroSD card | Probably have one. Need 32GB+ for Docker. |
| USB-C power supply | For the Pi 4B. Need 5V/3A minimum. |

## What to Buy

### Essential (MVP)

| Item | Purpose | Approx. Price | Notes |
|------|---------|---------------|-------|
| ReSpeaker 2-Mic Pi HAT | Microphone array | ~12-18 EUR | Plugs directly onto Pi GPIO header. Built-in LEDs for status feedback. Has 3.5mm headphone jack for speaker output. Search: "ReSpeaker 2-Mic Pi HAT" on Amazon.de |
| IR receiver TSOP38238 | Record remote codes | ~2-3 EUR | 38kHz carrier frequency (standard for most TV remotes). 3 pins: VCC, GND, OUT. Search: "TSOP38238" or "AZ-Delivery IR Empfaenger" |
| IR LED (940nm) | Send IR commands to TV | ~1-2 EUR | Usually comes in packs of 5-10. Need 940nm wavelength. |
| NPN transistor (2N2222 or BC547) | Drive IR LED from GPIO | ~1-2 EUR | GPIO can't supply enough current directly. Transistor acts as switch. |
| Resistors (100 ohm + 1K ohm) | Current limiting | ~1 EUR | 100 ohm for IR LED, 1K ohm for transistor base. Any assortment pack works. |
| Breadboard + jumper wires | Prototyping the IR circuit | ~3-5 EUR | For initial setup. Can solder permanently later. |

**Or instead of individual IR components:**

| Item | Purpose | Approx. Price | Notes |
|------|---------|---------------|-------|
| IR Sender/Receiver module for Raspberry Pi | All-in-one IR board | ~6-10 EUR | Search "IR Sender Empfaenger Modul Raspberry Pi" on Amazon.de. Includes receiver + LED + driver circuit on one board. Saves soldering. |

### Speaker (for future TTS, buy now)

| Item | Purpose | Approx. Price | Notes |
|------|---------|---------------|-------|
| Small USB speaker or 3.5mm speaker | Audio output for TTS | ~10-20 EUR | Option A: USB speaker (simpler, just plug in). Option B: 3.5mm speaker plugged into ReSpeaker HAT's headphone jack. Doesn't need to be fancy - a small desktop speaker works fine. |

**Specific recommendations:**
- **Budget:** Any small USB-powered speaker (~10 EUR). Search "Mini USB Lautsprecher" on Amazon.de.
- **Better:** Anker SoundCore Mini (~25 EUR, Bluetooth + AUX, decent sound, rechargeable). You probably already have something lying around.

## Summary

| Category | Est. Cost |
|----------|-----------|
| ReSpeaker 2-Mic HAT | ~15 EUR |
| IR components (individual or module) | ~5-10 EUR |
| Breadboard + wires | ~4 EUR |
| Small speaker | ~10-20 EUR |
| **Total** | **~35-50 EUR** |

## Wiring Reference (for individual IR components)

```
Pi GPIO 17 ---[1K ohm]--- Base (B)
                           |
                      2N2222 NPN
                           |
                      Collector (C) ---[100 ohm]--- IR LED anode (+)
                                                         |
                                                    IR LED cathode (-) --- 3.3V or 5V
                           |
                      Emitter (E) --- GND


Pi GPIO 18 --- TSOP38238 OUT
               TSOP38238 VCC --- 3.3V
               TSOP38238 GND --- GND
```

Note: The ReSpeaker 2-Mic HAT uses GPIO pins for its own I2S audio. Check for conflicts with GPIO 17/18 for IR. If there's a conflict, IR can use alternative GPIO pins (configured in `/boot/config.txt` device tree overlay). This needs testing during setup.

## Where to Order (Amazon.de)

Search terms for a single order:
1. "ReSpeaker 2-Mic Pi HAT" or "Seeed Studio ReSpeaker"
2. "TSOP38238 IR Empfaenger" or "IR Sender Empfaenger Modul Raspberry Pi"
3. "Breadboard Jumper Kabel Set"
4. "Mini USB Lautsprecher" or grab any speaker you have
