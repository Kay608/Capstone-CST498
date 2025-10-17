"""Runtime helper for Mary's traffic sign recognition model.

The model is a MobileNetV2 classifier trained on four classes:
- stop
- speed_limit
- no_entry
- crosswalk

During integration we only need lightweight inference helpers so this module
wraps the Keras model with preprocessing consistent with Mary's training
pipeline.
"""
from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional

import cv2
import numpy as np

try:  # Optional dependency
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
    from tensorflow.keras.models import Model
except ImportError:  # pragma: no cover - handled at runtime
    MobileNetV2 = None  # type: ignore[assignment]
    Dense = None  # type: ignore[assignment]
    GlobalAveragePooling2D = None  # type: ignore[assignment]
    Model = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)

# Default class order derived from Mary's repository folder names
DEFAULT_CLASS_NAMES = [
    "crosswalk",
    "no_entry",
    "speed_limit",
    "stop",
]


def _default_model_path() -> str:
    """Return the default on-disk model path."""
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "model", "mobilenetv2.h5")


class TrafficSignClassifier:
    """Lightweight wrapper around the MobileNetV2 traffic sign model."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        class_names: Optional[List[str]] = None,
        confidence_threshold: float = 0.6,
    ) -> None:
        self.model_path = model_path or os.environ.get("SIGN_MODEL_PATH") or _default_model_path()
        self.class_names = class_names or DEFAULT_CLASS_NAMES
        self.confidence_threshold = confidence_threshold
        self._model = None

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        if None in (MobileNetV2, Dense, GlobalAveragePooling2D, Model):
            raise ImportError(
                "TensorFlow/Keras is required for traffic sign recognition. "
                "Install tensorflow or tensorflow-cpu in the active environment."
            )
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Traffic sign model not found at '{self.model_path}'. "
                "Place Mary's mobilenetv2.h5 there or set SIGN_MODEL_PATH."
            )
        LOGGER.info("Loading traffic sign model from %s", self.model_path)
        self._model = self._build_model()
        self._model.load_weights(self.model_path)

    def _build_model(self):
        base_model = MobileNetV2(input_shape=(64, 64, 3), include_top=False, weights="imagenet")
        base_model.trainable = False
        x = base_model.output
        x = GlobalAveragePooling2D()(x)
        x = Dense(128, activation="relu")(x)
        predictions = Dense(len(self.class_names), activation="softmax")(x)
        return Model(inputs=base_model.input, outputs=predictions)

    @staticmethod
    def preprocess(frame: np.ndarray) -> np.ndarray:
        """Resize and normalize a frame to feed the model."""
        resized = cv2.resize(frame, (64, 64))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return rgb.astype("float32") / 255.0

    def predict(self, frame: np.ndarray) -> List[Dict[str, float]]:
        """Run inference on an image frame and return confident predictions."""
        self._ensure_model_loaded()
        processed = self.preprocess(frame)
        batch = np.expand_dims(processed, axis=0)
        preds = self._model.predict(batch, verbose=0)[0]
        results: List[Dict[str, float]] = []
        for idx, confidence in enumerate(preds):
            if confidence < self.confidence_threshold:
                continue
            label = self.class_names[idx] if idx < len(self.class_names) else f"class_{idx}"
            results.append({
                "label": label,
                "confidence": float(confidence),
            })
        # Sort high → low confidence so downstream code can pick the first entry
        results.sort(key=lambda item: item["confidence"], reverse=True)
        return results

    def predict_top(self, frame: np.ndarray) -> Optional[Dict[str, float]]:
        """Return the single most confident prediction, or None if below threshold."""
        predictions = self.predict(frame)
        return predictions[0] if predictions else None
