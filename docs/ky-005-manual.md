# KY-005 Infrared LED Module - Manual

## Specifications

- Operating voltage range: 3.3V to 5V DC
- Forward current: 30 ~ 60 mA
- Power consumption: 90mW
- Operating temperature: -25C to 80C
- Dimensions: 19 x 15mm

## Pinout

The KY-005 has three pins:

- **S** (Signal) - data input
- **Middle pin** (VCC) - power
- **-** (GND) - ground

## Raspberry Pi Wiring (manual default, no transistor)

| KY-005 pin       | Raspberry Pi pin       | Wire color |
|-------------------|------------------------|------------|
| S (Signal)        | GPIO22 [pin 15]       | Blue       |
| Middle pin (VCC)  | 3V3 [pin 17]          | Red        |
| - (GND)           | GND [pin 20]          | Black      |

## Raspberry Pi Python Script (basic LED test)

```python
import RPi.GPIO as GPIO
from time import sleep

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

IRLED = 22
GPIO.setup(IRLED, GPIO.OUT)

print('[Press CTRL + C to end the script!]')
try:
    while True:
        # PWM 500Hz, duty cycle 50%
        GPIO.output(IRLED, GPIO.HIGH)
        sleep(0.001)
        GPIO.output(IRLED, GPIO.LOW)
        sleep(0.001)
except KeyboardInterrupt:
    print('\nScript End!')
finally:
    GPIO.cleanup()
```

Run with: `python3 ky005.py`

## Atmega328p Wiring

| KY-005 pin       | Mc pin | Wire color |
|-------------------|--------|------------|
| S                 | D3     | Blue       |
| Middle pin (VCC)  | 5V     | Red        |
| - (GND)           | GND    | Black      |

## Notes

- The IR LED emits at 38kHz carrier frequency
- Human eye cannot see IR light, but phone cameras can
- Use together with KY-022 receiver to create IR interfaces
- To determine TV remote codes, use the KY-022 module to read them first
