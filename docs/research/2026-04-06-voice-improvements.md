# Voice Pipeline Improvement Research

**Date:** 2026-04-06

## Current Issues

- Wake word false triggers from music playing through nearby speaker
- Voice scores low (0.4-0.5) at distance with music playing
- Fixed 5-second recording window — should stop when user stops talking
- Single USB mic close to speaker limits software echo cancellation

## Wake Word Detection

### Porcupine (Picovoice)

Best-in-class accuracy, lowest false positive rate. Runs natively on ARM/Pi with minimal CPU. Custom wake words via their console — type the phrase, get a model file, no audio samples needed. Free tier allows 3 custom wake words (personal/non-commercial use). Drop-in replacement for openWakeWord.

### Custom openWakeWord Training

Train a custom "hey clawdia" model using synthetic TTS-generated clips plus negative examples (music, TV, conversation). Requires ~500-1000 synthetic clips. Training runs on a GPU machine, not the Pi. A few hours of work. A custom model trained with music-as-negative-examples would significantly reduce false triggers.

### Recommendation

Try Porcupine first — near-zero false positives with minimal effort. If licensing is a concern, train a custom openWakeWord model with music/noise negatives.

## Voice Activity Detection (VAD)

### Silero VAD

Best option. Small ONNX model (~2MB), runs in a few ms per chunk on ARM. Returns speech probability per audio frame. Use to detect end-of-speech: start recording after wake word, stop after ~2s of consecutive non-speech frames. `onnxruntime` is already a dependency. Well-maintained, widely used in production.

### webrtcvad

Simpler, C-based, very lightweight. Less accurate than Silero — more prone to cutting off speech or missing pauses. Fine as a fallback.

### Whisper / OpenAI STT

Does not do streaming — you send a complete audio file. Won't help with detecting when to stop recording. Local VAD is needed to determine recording boundaries before sending to the API.

### Recommendation

Use Silero VAD. Clear winner for Pi-class hardware.

## Echo Cancellation

PulseAudio `module-echo-cancel` with speex is a basic AEC. With a single USB mic and nearby speaker, software AEC has limited reference signal quality.

### Improvements

- Pre-filter: high-pass filter (cut below 85Hz) on mic input before wake word — removes bass-heavy music energy
- Properly configure AEC reference channel (already done)
- Noise gate before wake word processing

### Hardware: ReSpeaker USB Mic Array

A $15-20 ReSpeaker USB mic array (2-mic or 4-mic) with built-in AEC and beamforming would be the single biggest improvement. Hardware echo cancellation on a mic array fundamentally outperforms software AEC on a single omnidirectional mic.

## Implementation Priority

1. **Silero VAD** — easiest win, replaces fixed 5s recording window with dynamic stop-on-silence
2. **Porcupine** — drop-in wake word replacement, way fewer false positives
3. **ReSpeaker mic array** — if software fixes aren't enough for echo cancellation
