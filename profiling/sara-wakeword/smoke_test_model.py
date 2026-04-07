#!/usr/bin/env python3
"""Smoke test a hey_sara.onnx model on the Pi.

Loads the model via OWW, feeds silent frames to confirm it loads and predicts
without error, then optionally listens on the mic for a live test.

Usage:
    source ~/venv/bin/activate
    python profiling/sara-wakeword/smoke_test_model.py path/to/hey_sara.onnx
    python profiling/sara-wakeword/smoke_test_model.py path/to/hey_sara.onnx --live
"""

import argparse
import sys
import time

import numpy as np


def smoke_silent(model_path: str) -> bool:
    """Load model and run predict on silent frames."""
    from openwakeword.model import Model as OWWModel

    print(f"Loading model: {model_path}")
    t0 = time.monotonic()
    model = OWWModel(wakeword_model_paths=[model_path])
    print(f"  Loaded in {(time.monotonic() - t0)*1000:.0f}ms")
    print(f"  Model keys: {list(model.models.keys())}")

    chunk = np.zeros(1280, dtype=np.float32)
    preds = model.predict(chunk)
    print(f"  Prediction keys: {list(preds.keys())}")
    print(f"  Silent frame scores: {preds}")

    all_zero = all(v == 0.0 for v in preds.values())
    print(f"  All zeros on silence: {all_zero}")
    return True


def live_test(model_path: str, threshold: float = 0.3, duration: int = 15):
    """Listen on mic and print detections for `duration` seconds."""
    from openwakeword.model import Model as OWWModel

    print(f"\nLive test — say 'hey Sara' (listening for {duration}s, threshold={threshold})")
    model = OWWModel(wakeword_model_paths=[model_path])
    wake_key = list(model.models.keys())[0]

    try:
        import pyaudio
    except ImportError:
        print("ERROR: pyaudio not installed — can't do live test")
        return

    pa = pyaudio.PyAudio()
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000,
                     input=True, frames_per_buffer=1280)
    print("  Listening...")

    end_time = time.monotonic() + duration
    detections = 0
    try:
        while time.monotonic() < end_time:
            audio = np.frombuffer(stream.read(1280, exception_on_overflow=False), dtype=np.int16)
            preds = model.predict(audio.astype(np.float32))
            score = preds.get(wake_key, 0.0)
            if score > threshold:
                detections += 1
                remaining = end_time - time.monotonic()
                print(f"  DETECTED '{wake_key}' score={score:.3f} ({remaining:.0f}s remaining)")
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    print(f"\n  Total detections: {detections}")


def main():
    p = argparse.ArgumentParser(description="Smoke test hey_sara.onnx")
    p.add_argument("model", help="Path to hey_sara.onnx")
    p.add_argument("--live", action="store_true", help="Run live mic test after smoke")
    p.add_argument("--threshold", type=float, default=0.3)
    p.add_argument("--duration", type=int, default=15)
    args = p.parse_args()

    ok = smoke_silent(args.model)
    if not ok:
        sys.exit(1)

    if args.live:
        live_test(args.model, args.threshold, args.duration)

    print("\nSmoke test passed.")


if __name__ == "__main__":
    main()
