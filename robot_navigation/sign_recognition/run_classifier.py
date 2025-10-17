"""Quick manual test for the traffic sign classifier.

Usage (from project root once the virtualenv is active):

    python -m robot_navigation.sign_recognition.run_classifier \
        --image path/to/test_image.jpg

You can also point to Mary's demo images. The script prints the label and
confidence score and optionally displays the processed frame.
"""
from __future__ import annotations

import argparse
import cv2
import sys
from pathlib import Path

from .classifier import TrafficSignClassifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the traffic sign classifier on a single image.")
    parser.add_argument("--image", required=True, help="Path to the input image (BGR/standard photo).")
    parser.add_argument("--show", action="store_true", help="Display the resized frame with the predicted label.")
    parser.add_argument("--threshold", type=float, default=0.6, help="Confidence floor for accepting predictions.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}")
        return 1

    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"[ERROR] Failed to load image: {image_path}")
        return 1

    classifier = TrafficSignClassifier(confidence_threshold=args.threshold)
    try:
        result = classifier.predict_top(frame)
    except Exception as exc:  # typically missing model weights / TensorFlow setup
        print(f"[ERROR] Classifier failed: {exc}")
        return 1

    if not result:
        print("No prediction met the confidence threshold.")
        return 0

    label = result["label"]
    confidence = result["confidence"]
    print(f"Prediction: {label} ({confidence:.2f})")

    if args.show:
        display = frame.copy()
        cv2.putText(display, f"{label} {confidence:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        max_dim = 720
        height, width = display.shape[:2]
        scale = min(1.0, max_dim / max(height, width))
        if scale < 1.0:
            new_size = (int(width * scale), int(height * scale))
            display = cv2.resize(display, new_size, interpolation=cv2.INTER_AREA)

        cv2.imshow("Traffic Sign", display)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
