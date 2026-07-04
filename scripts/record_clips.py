"""Record wake word training clips on the Pi.

Records from the default PulseAudio source (echo_cancel_source) so clips
match what the wake word listener hears at runtime.

Positive clips (speaker says the wake phrase once after each chime):

    uv run python scripts/record_clips.py positive --out data/clips/gernot --count 12

Negative clips (background/TV audio, recorded back to back, no chime):

    uv run python scripts/record_clips.py negative --out data/clips/tv --count 30

Stop the clawdia service first so detections don't fire mid-session:

    systemctl --user stop clawdia
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

CHIME = Path(__file__).parent.parent / "src" / "clawdia" / "voice" / "sounds" / "chime.wav"


def record(path: Path, duration: float) -> None:
    # parecord runs until killed, so bound it with coreutils timeout

    subprocess.run(
        [
            "timeout",
            "--preserve-status",
            str(duration),
            "parecord",
            "--channels=1",
            "--rate=16000",
            "--format=s16le",
            "--file-format=wav",
            str(path),
        ],
        check=False,
    )


def chime() -> None:
    subprocess.run(["paplay", str(CHIME)], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["positive", "negative"])
    parser.add_argument("--out", required=True, help="output directory for WAV clips")
    parser.add_argument("--count", type=int, default=12, help="number of clips to record")
    parser.add_argument("--duration", type=float, default=2.5, help="seconds per clip")
    parser.add_argument("--gap", type=float, default=1.5, help="pause between positive takes")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    existing = len(list(out.glob("*.wav")))

    for i in range(args.count):
        path = out / f"clip_{existing + i:03d}.wav"
        if args.mode == "positive":
            chime()
            time.sleep(0.3)  # let the chime tail clear the room
        print(f"[{i + 1}/{args.count}] recording {path.name} ({args.duration}s)...", flush=True)
        record(path, args.duration)
        if args.mode == "positive":
            time.sleep(args.gap)

    print(f"Done. {args.count} clips in {out}/")


if __name__ == "__main__":
    main()
