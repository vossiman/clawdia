# KY-022 Infrared Receiver Module - Manual

## Specifications

- Operating voltage range: 3.3V to 5V DC
- Current consumption: 1.5mA peak
- Chip type: VS1838B
- Reception distance: 17m
- Carrier frequency: 38kHz
- Infrared wavelength: 940nm
- Pulse duration: 400us to 2000us
- Dimensions: 9 x 22mm

## Pinout

The KY-022 has three pins:

- **S** (Signal) - data output
- **Middle pin** (VCC) - power
- **-** (GND) - ground

## Raspberry Pi Wiring

| KY-022 pin       | Raspberry Pi pin       | Wire color |
|-------------------|------------------------|------------|
| Middle pin (VCC)  | 3V3 [pin 1]           | Red        |
| - (GND)           | GND [pin 6]           | Black      |
| S (Signal)        | GPIO17 [pin 11]       | Blue       |

## Atmega328p Wiring

| KY-022 pin       | Mc pin | Wire color |
|-------------------|--------|------------|
| S                 | D4     | Blue       |
| Middle pin (VCC)  | 5V     | Red        |
| - (GND)           | GND    | Black      |

## Working Principle

The IR receiver uses a VS1838B photodiode and pre-amplifier that detects 38kHz modulated infrared light.

The receiver diode detects all frequencies of IR light but has a band pass filter that only lets through 38kHz. It amplifies the modulated signal with a pre-amplifier and converts it to binary.

Common IR transmission protocols: Sony, Matsushita, NEC, RC5, RC6.

### NEC Protocol (most common in embedded projects)

- Logical 1: 562.5us HIGH pulse at 38kHz followed by 1687.5us LOW pulse
- Logical 0: 562.5us HIGH pulse followed by 562.5us LOW pulse
- Repeat/held: sends 0xFFFFFFFF

## Raspberry Pi Python Script

```python
import RPi.GPIO as GPIO
from time import time, sleep

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

Signal_Pin = 17
GPIO.setup(Signal_Pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

code = None
CODES = {
    0xe0e040bf: "ON/OFF",
    0xe0e08877: "0",
    0xe0e020df: "1",
    0xe0e0a05d: "2",
    0xe0e0609f: "3",
    0xe0e010ef: "4",
    0xe0e0906f: "5",
    0xe0e050ad: "6",
    0xe0e030cf: "7",
    0xe0e0b04f: "8",
    0xe0e0708f: "9"
}

def binary_aquire(pin, duration):
    t0 = time()
    results = []
    while (time() - t0) < duration:
        results.append(GPIO.input(pin))
    return results

def rec(pinNo, bouncetime=150):
    global code, CODES
    data = binary_aquire(pinNo, bouncetime/1000.0)
    if len(data) < bouncetime:
        return
    rate = len(data) / (bouncetime / 1000.0)
    pulses = []
    i_break = 0
    for i in range(1, len(data)):
        if (data[i] != data[i-1]) or (i == len(data) - 1):
            pulses.append((data[i-1], int((i-i_break)/rate*1e6)))
            i_break = i
    outbin = ""
    for val, us in pulses:
        if val != 1:
            continue
        if outbin and us > 2000:
            break
        elif us < 1000:
            outbin += "0"
        elif 1000 < us < 2000:
            outbin += "1"
    try:
        code = int(outbin, 2)
        print('Key {} -> {}'.format(str(hex(code)), CODES[code]))
    except ValueError:
        code = None
    except KeyError:
        print('Key {} is not defined.'.format(str(hex(code))))

GPIO.add_event_detect(17, GPIO.FALLING, callback=rec, bouncetime=100)

print('[Press CTRL + C to end the script!]')
try:
    print('Starting IR Listener')
    print('Waiting for signal')
    while True:
        sleep(0.000033)
except KeyboardInterrupt:
    print('\nScript end!')
finally:
    GPIO.cleanup()
```

Run with: `python3 ky022.py`
