"""Train an openwakeword custom verifier model from recorded clips.

The verifier is a per-voice second stage: when the base wake word model
scores above the verifier gate, the score is replaced by the verifier's
probability that the audio is one of the trained speakers.

    uv run python scripts/train_verifier.py \
        --positive data/clips/gernot --positive data/clips/oxana \
        --negative data/clips/tv \
        --output data/models/verifier_hey_jarvis.pkl

Unlike openwakeword's train_custom_verifier, the positive feature
threshold is configurable: the stock 0.5 discards clips the base model
scores low on, which is exactly the failure mode we are correcting.
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
from openwakeword.custom_verifier_model import (
    get_reference_clip_features,
    train_verifier_model,
)
from openwakeword.model import Model

MODEL_NAME = "hey_jarvis_v0.1"


def clip_max_score(oww: Model, path: Path) -> float:
    oww.reset()
    scores = [p[MODEL_NAME] for p in oww.predict_clip(str(path))]
    return max(scores) if scores else 0.0


def extract(oww: Model, paths: list[Path], threshold: float, n: int, label: str) -> np.ndarray:
    chunks = []
    for path in paths:
        oww.reset()
        max_score = clip_max_score(oww, path)
        oww.reset()
        features = get_reference_clip_features(str(path), oww, MODEL_NAME, threshold=threshold, N=n)
        print(f"  {label} {path.name}: max base score {max_score:.3f}, {features.shape[0]} frames")
        if features.shape[0] > 0:
            chunks.append(features)
    return np.vstack(chunks) if chunks else np.empty((0, 0, 96))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--positive", action="append", required=True, help="dir of wake word WAVs (repeatable)"
    )
    parser.add_argument(
        "--negative", action="append", required=True, help="dir of background WAVs (repeatable)"
    )
    parser.add_argument("--output", required=True, help="output .pkl path")
    parser.add_argument("--positive-threshold", type=float, default=0.3)
    args = parser.parse_args()

    positives = sorted(p for d in args.positive for p in Path(d).glob("*.wav"))
    negatives = sorted(p for d in args.negative for p in Path(d).glob("*.wav"))
    print(f"{len(positives)} positive clips, {len(negatives)} negative clips")

    oww = Model(wakeword_models=[MODEL_NAME], inference_framework="onnx")

    print("Extracting positive features...")
    pos = extract(oww, positives, args.positive_threshold, n=5, label="+")
    print("Extracting negative features...")
    neg = extract(oww, negatives, threshold=0.0, n=1, label="-")

    if pos.shape[0] == 0:
        raise SystemExit(
            "No positive frames extracted - lower --positive-threshold or re-record louder/closer clips."
        )
    if neg.shape[0] == 0:
        raise SystemExit("No negative frames extracted - check the negative clips.")

    print(f"Training on {pos.shape[0]} positive / {neg.shape[0]} negative frames...")
    verifier = train_verifier_model(
        np.vstack((pos, neg)),
        np.array([1] * pos.shape[0] + [0] * neg.shape[0]),
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        pickle.dump(verifier, f)
    print(f"Saved verifier to {out}")


if __name__ == "__main__":
    main()
