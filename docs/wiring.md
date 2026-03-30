# Clawdia Raspberry Pi Wiring

## GPIO Pin Reference

See `docs/pi_gpio.jpg` for the full pinout diagram.

## KY-022 IR Receiver (VS1838B) — Direct to Pi

Module pins (left to right on the board): **S**, **VCC**, **- (GND)**.

| # | Wire | From | To |
|---|------|------|-----|
| 1 | Blue | KY-022 S (Signal) | Pi Pin 15 (GPIO 22) |
| 2 | Red | KY-022 Middle (VCC) | Pi Pin 1 (3.3V) |
| 3 | Brown | KY-022 - (minus) | Pi Pin 6 (GND) |

Boot config: `dtoverlay=gpio-ir,gpio_pin=22`

## KY-005 IR Transmitter — via 2N2222 transistor + 1kΩ resistor

Module pins (left to right on the board): **S**, **VCC**, **- (GND)**.

2N2222 pinout (flat side facing you, legs down): Left=Emitter, Middle=Base, Right=Collector.

| # | Wire | From | To |
|---|------|------|-----|
| 1 | Violet | Pi Pin 16 (GPIO 23) | 1kΩ resistor leg 1 |
| 2 | — | 1kΩ resistor leg 2 | 2N2222 Base (middle leg) |
| 3 | White | Pi Pin 4 (5V) | KY-005 S (Signal) |
| 4 | Yellow | KY-005 - (minus) | 2N2222 Collector (right leg) |
| 5 | Orange | 2N2222 Emitter (left leg) | Pi Pin 14 (GND) |

KY-005 VCC (middle) — unconnected.

Row 2: no wire needed, resistor leg and 2N2222 base sit in the same breadboard row.

The transistor switches the ground path: 5V → S → LED → GND(-) → Collector → Emitter → GND.

Boot config: `dtoverlay=gpio-ir-tx,gpio_pin=23`

**Status:** Verified working (2026-03-30). 3x KY-005 modules wired in parallel.
Currently placed ~1m from TV — works for all commands including power off at this range.
At 3m, only power ON works (TV in standby = clean IR reception). Power OFF and all
other commands fail at 3m — plasma panel EM noise drowns out the signal.
10 more KY-005 modules ordered (13 total should give ~4x signal strength).
If 13 LEDs still insufficient at 3m, swap 1kΩ base resistor to 470Ω to support up to ~25 LEDs.
See `docs/samsung-ir-codes.md` for the full code reference.

## Pi Header Layout (relevant pins)

```
Pin 1  (3.3V) ← Receiver VCC    |  Pin 2  (5V)
Pin 3  (GPIO2)                   |  Pin 4  (5V) ← Transmitter VCC
Pin 5  (GPIO3)                   |  Pin 6  (GND) ← Receiver GND
Pin 7  (GPIO4)                   |  Pin 8
Pin 9  (GND)                     |  Pin 10
Pin 11 (GPIO17)                  |  Pin 12
Pin 13 (GPIO27)                  |  Pin 14 (GND) ← Transmitter GND (emitter)
Pin 15 (GPIO22) ← Receiver SIG  |  Pin 16 (GPIO23) ← Transmitter SIG (→ resistor → base)
Pin 17 (3.3V)                    |  Pin 18 (GPIO24)
Pin 19                           |  Pin 20
```
