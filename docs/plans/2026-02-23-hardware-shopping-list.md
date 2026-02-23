# Clawdia - Hardware Shopping List

**Date:** 2026-02-23
**Status:** FINAL - Order confirmed

## What You Already Have

| Item | Notes |
|------|-------|
| Raspberry Pi 4B | Main unit. Check RAM with `cat /proc/meminfo` when you boot it. |
| ADELGO USB SoundBar Speaker | ASIN: B089W5PS29. USB-powered, plug and play. For future TTS audio output. |
| Breadboard | For IR circuit prototyping. |
| Jumper wires | M-M, M-F, F-F. |
| MicroSD card | Need 32GB+ for Docker. Verify you have one. |
| USB-C power supply | For the Pi 4B. Need 5V/3A minimum. |
| Raspberry Pi 3B+ | Future use (satellite node, experiments) |
| Display shield | Future use (status display) |
| Camera module | Future use |

## Order (Amazon.de)

### 1. Keyestudio ReSpeaker 2-Mic Pi HAT

- **ASIN:** B07H3T8SQY
- **Price:** ~14 EUR
- **Link:** https://www.amazon.de/-/en/gp/product/B07H3T8SQY
- **What:** Dual MEMS microphones, WM8960 codec (I2S), 3.5mm headphone jack, 3x APA102 status LEDs, button
- **Why:** Mic input for voice commands. Status LEDs for visual feedback (listening/processing/responding). Well-documented, Pi 4B compatible.

**GPIO pins used by this HAT (I2S + I2C):**

| Function | GPIO (BCM) |
|----------|-----------|
| I2C SDA | GPIO 2 |
| I2C SCL | GPIO 3 |
| I2S CLK | GPIO 18 |
| I2S LRCLK | GPIO 19 |
| I2S DAC | GPIO 21 |
| I2S ADC | GPIO 20 |
| Button | GPIO 17 |

**IMPORTANT:** GPIO 17 and 18 are occupied. IR must use different pins.

### 2. AZDelivery 5x KY-022 IR Receiver

- **ASIN:** B07ZYZDW28
- **Price:** 6.54 EUR
- **Link:** https://www.amazon.de/-/en/gp/product/B07ZYZDW28
- **What:** 5x CHQ1838 IR receiver modules (38kHz demodulator), breakout PCB with 3 pins (S/+/-), status LED
- **Why:** Records TV remote IR codes. 38kHz carrier demodulation built in. 3-5V compatible. Functionally equivalent to TSOP38238 but on a convenient breakout board.

### 3. AZDelivery 5x KY-005 IR Transmitter

- **ASIN:** B07ZTQX59N
- **Price:** 6.54 EUR
- **Link:** https://www.amazon.de/-/en/AZDelivery-Transmitter-Transceiver-Compatible-Raspberry/dp/B07ZTQX59N
- **What:** 5x IR LED transmitter modules on breakout PCB
- **Why:** Sends IR commands to TV. Driven through an NPN transistor for increased range (5-10m).

### 4. Transistor Assortment (480pcs)

- **ASIN:** B0DGCXLVDM
- **Price:** 9.99 EUR
- **Link:** https://www.amazon.de/-/en/Transistor-Assortment-Values-480pcs-Transistors/dp/B0DGCXLVDM
- **What:** 480-piece transistor assortment, multiple values including 2N2222/BC547
- **Why:** NPN transistor drives IR LED with higher current (~100-200mA) for increased IR range. GPIO alone can only supply ~20mA.

### 5. Resistor Assortment (525pcs)

- **ASIN:** B0CL6XM7RD
- **Price:** 7.99 EUR
- **Link:** https://www.amazon.de/-/en/Innfeeltech-Tolerance-Resistor-Project-Experiments/dp/B0CL6XM7RD
- **What:** 525-piece resistor assortment, 1 ohm to 1M ohm, 1% tolerance
- **Why:** 1K ohm resistor limits base current to transistor (~3mA from GPIO). Also useful for future electronics projects.

## Order Summary

| # | Item | Price |
|---|------|-------|
| 1 | Keyestudio ReSpeaker 2-Mic HAT | ~14 EUR |
| 2 | AZDelivery 5x KY-022 IR Receiver | 6.54 EUR |
| 3 | AZDelivery 5x KY-005 IR Transmitter | 6.54 EUR |
| 4 | Transistor assortment 480pcs | 9.99 EUR |
| 5 | Resistor assortment 525pcs | 7.99 EUR |
| | **Total** | **~45 EUR** |

## Wiring Reference

### IR Transmitter Circuit (KY-005 + transistor for range)

Since the ReSpeaker HAT uses GPIO 17 and 18, IR uses **GPIO 22** (receiver) and **GPIO 24** (transmitter).

```
IR TRANSMITTER (KY-005 module driven via NPN transistor):

Pi GPIO 24 ---[1K ohm]--- Base (B)
                           |
                      2N2222 NPN
                           |
                  Emitter (E) --- GND
                           |
                  Collector (C) --- KY-005 Signal pin (S)
                                    KY-005 VCC (+) --- 5V
                                    KY-005 GND (-) --- GND


IR RECEIVER (KY-022 module):

Pi GPIO 22 --- KY-022 Signal pin (S)
               KY-022 VCC (+) --- 3.3V
               KY-022 GND (-) --- GND
```

### Pi /boot/config.txt additions for IR

```
# IR receiver on GPIO 22
dtoverlay=gpio-ir,gpio_pin=22

# IR transmitter on GPIO 24
dtoverlay=gpio-ir-tx,gpio_pin=24
```

### Complete GPIO Usage Map

| GPIO | Used By | Function |
|------|---------|----------|
| 2 | ReSpeaker HAT | I2C SDA |
| 3 | ReSpeaker HAT | I2C SCL |
| 17 | ReSpeaker HAT | Button |
| 18 | ReSpeaker HAT | I2S CLK |
| 19 | ReSpeaker HAT | I2S LRCLK |
| 20 | ReSpeaker HAT | I2S ADC |
| 21 | ReSpeaker HAT | I2S DAC |
| 22 | **IR Receiver** | KY-022 signal out |
| 24 | **IR Transmitter** | KY-005 via transistor |
| 4, 5-16, 23, 25-27 | Free | Available for future use |

## Future Hardware (already owned, not needed for MVP)

| Item | Potential Use |
|------|------|
| Pi 3B+ | Second room satellite mic/speaker |
| Display shield | Show assistant status, weather, current action |
| Camera module | Gesture control, person detection, video calls |
