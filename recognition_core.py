#!/usr/bin/env python3
"""Shared facial recognition utilities for the Capstone project.

This module centralises the functionality that was previously duplicated
between ``integrated_recognition_system.py`` and ``ai_facial_recognition.py``.
It provides reusable helpers for database access, face encoding cache
management, HTTP logging to the Flask API, and a lightweight
``FaceRecognitionEngine`` that can analyse frames without requiring the full
integrated runtime.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pymysql
import requests
from dotenv import load_dotenv

try:  # Optional dependencies – callers should handle missing libs gracefully
    import cv2  # type: ignore
except Exception:  # pragma: no cover - OpenCV is optional in some environments
    cv2 = None  # type: ignore

try:
    import face_recognition  # type: ignore
except Exception:  # pragma: no cover - Allow import on systems without dlib
    face_recognition = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment and configuration loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR
PARENT_DIR = PROJECT_ROOT.parent

# Load environment variables in the same order as the legacy implementation
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "flask_api" / ".env", override=False)
load_dotenv(PARENT_DIR / ".env", override=False)

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

FLASK_APP_URL = os.environ.get("FLASK_APP_URL", "http://localhost:5001")
ALTERNATIVE_FLASK_URLS = [
    "http://localhost:5001",
    "http://127.0.0.1:5001",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://10.202.65.203:5001",
]

MATCH_THRESHOLD = 0.65
FACE_DETECTION_MODEL = "hog"
FRAME_SCALE = 0.5
FRAME_SKIP = 3
DB_REFRESH_INTERVAL = 300
HTTP_TIMEOUT = 3

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection() -> pymysql.connections.Connection:
    """Return a new MySQL connection using environment credentials."""
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        raise pymysql.MySQLError("Database credentials are not fully configured.")

    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


def save_encodings_cache(encodings: Sequence[np.ndarray], names: Sequence[Tuple[str, str]]) -> bool:
    """Persist face encodings to a local cache for offline use."""
    cache_dir = PROJECT_ROOT / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "face_encodings.npz"

    try:
        np.savez_compressed(
            cache_file,
            encodings=np.array(list(encodings)),
            names=np.array(list(names), dtype=object),
        )
        logger.info("Cached %d face(s) to %s", len(names), cache_file)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save face cache: %s", exc)
        return False


def load_encodings_cache() -> Tuple[Optional[List[np.ndarray]], Optional[List[Tuple[str, str]]]]:
    """Load locally cached encodings, returning ``(encodings, names)``."""
    cache_file = PROJECT_ROOT / "cache" / "face_encodings.npz"
    if not cache_file.exists():
        return None, None

    try:
        data = np.load(cache_file, allow_pickle=True)
        encodings = list(data["encodings"])
        names = list(data["names"])
        logger.info("Loaded %d face(s) from local cache", len(names))
        return encodings, names
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load face cache: %s", exc)
        return None, None


def _deserialize_encoding(raw_bytes: bytes) -> Optional[np.ndarray]:
    """Convert a raw BLOB from MySQL into a 128-d vector."""
    for dtype in (np.float64, np.float32):
        with contextlib.suppress(Exception):
            arr = np.frombuffer(raw_bytes, dtype=dtype)
            if arr.size == 128:
                return arr.astype(np.float64)
    return None


def load_encodings_from_db() -> Tuple[List[np.ndarray], List[Tuple[str, str]]]:
    """Fetch face encodings from MySQL, falling back to the local cache."""
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        logger.warning("Database credentials missing – attempting to use local cache")
        cached = load_encodings_cache()
        if cached[0] is not None:
            return cached  # type: ignore[return-value]
        logger.warning("No local cache available; returning empty encoding set")
        return [], []

    conn: Optional[pymysql.connections.Connection] = None
    known_encodings: List[np.ndarray] = []
    known_names: List[Tuple[str, str]] = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT banner_id, first_name, last_name, encoding FROM users;")
            rows = cur.fetchall()

        for row in rows:
            display_name = f"{row['first_name']} {row['last_name']}".strip()
            banner_id = row["banner_id"]
            encoding = _deserialize_encoding(row["encoding"])
            if encoding is None:
                logger.warning("Skipping banner_id=%s due to invalid encoding", banner_id)
                continue
            known_encodings.append(encoding)
            known_names.append((banner_id, display_name))

        logger.info("Loaded %d known face(s) from MySQL", len(known_names))
        if known_encodings:
            save_encodings_cache(known_encodings, known_names)

    except pymysql.MySQLError as exc:
        logger.error("Error loading encodings from MySQL: %s", exc)
        cached_encodings, cached_names = load_encodings_cache()
        if cached_encodings is not None:
            return cached_encodings, cached_names  # type: ignore[return-value]
        logger.warning("No cache available; returning empty encoding set")
    finally:
        if conn:
            conn.close()

    return known_encodings, known_names


def load_encodings(cache_first: bool = False) -> Tuple[List[np.ndarray], List[Tuple[str, str]]]:
    """Load encodings from cache (optional) or database."""
    if cache_first:
        cached_encodings, cached_names = load_encodings_cache()
        if cached_encodings is not None:
            return cached_encodings, cached_names  # type: ignore[return-value]
    return load_encodings_from_db()


# ---------------------------------------------------------------------------
# HTTP logging helpers
# ---------------------------------------------------------------------------

def _post_json(url: str, payload: dict) -> requests.Response:
    return requests.post(url, json=payload, timeout=HTTP_TIMEOUT)


def log_verification_http(name: str, matched: bool, confidence: float, location: Optional[str] = None) -> bool:
    """Log a verification event to the Flask API with graceful fallbacks."""
    global FLASK_APP_URL

    urls_to_try = [FLASK_APP_URL] + [url for url in ALTERNATIVE_FLASK_URLS if url != FLASK_APP_URL]
    payload = {
        "name": name,
        "matched": matched,
        "confidence": confidence,
        "location": location or "Raspberry Pi",
    }

    for attempt, url in enumerate(urls_to_try, start=1):
        try:
            endpoint = f"{url}/api/log_verification"
            logger.debug("[HTTP] Attempt %d posting to %s", attempt, endpoint)
            response = _post_json(endpoint, payload)
            if response.status_code == 200:
                FLASK_APP_URL = url
                logger.info("Logged verification to %s", url)
                return True
            logger.warning("HTTP %s from %s", response.status_code, url)
        except requests.RequestException as exc:  # noqa: BLE001
            logger.warning("Connection failure to %s: %s", url, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error logging verification via %s: %s", url, exc)

    logger.error("All Flask endpoints failed – verification stored locally only")
    return False


def process_order_fulfillment(banner_id: str, display_name: str) -> bool:
    """Notify Flask API to process order fulfilment for a recognized user."""
    global FLASK_APP_URL

    urls_to_try = [FLASK_APP_URL] + [url for url in ALTERNATIVE_FLASK_URLS if url != FLASK_APP_URL]
    payload = {"banner_id": banner_id, "action": "fulfill"}

    for attempt, url in enumerate(urls_to_try, start=1):
        try:
            endpoint = f"{url}/api/process_order"
            logger.debug("[HTTP] Attempt %d posting to %s", attempt, endpoint)
            response = _post_json(endpoint, payload)
            if response.status_code == 200:
                result = response.json()
                FLASK_APP_URL = url
                fulfilled = bool(result.get("order_fulfilled"))
                if fulfilled:
                    items = result.get("items", "N/A")
                    logger.info("Order fulfilled for %s (%s): %s", display_name, banner_id, items)
                else:
                    logger.info("No pending orders for %s (%s)", display_name, banner_id)
                return fulfilled
            logger.warning("HTTP %s from %s", response.status_code, url)
        except requests.RequestException as exc:  # noqa: BLE001
            logger.warning("Connection failure to %s: %s", url, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error processing order via %s: %s", url, exc)

    logger.error("All Flask endpoints failed – order fulfilment skipped")
    return False


# ---------------------------------------------------------------------------
# Face recognition engine
# ---------------------------------------------------------------------------

@dataclass
class RecognitionResult:
    name: str
    matched: bool
    confidence: float
    banner_id: Optional[str]
    box: Tuple[int, int, int, int]


class FaceRecognitionEngine:
    """Minimal reusable face recognition pipeline for single-frame analysis."""

    def __init__(
        self,
        match_threshold: float = MATCH_THRESHOLD,
        frame_scale: float = FRAME_SCALE,
        frame_skip: int = FRAME_SKIP,
        detection_model: str = FACE_DETECTION_MODEL,
        cache_first: bool = False,
    ) -> None:
        if face_recognition is None or cv2 is None:
            raise RuntimeError("OpenCV and face_recognition must be installed to use FaceRecognitionEngine")

        self.match_threshold = match_threshold
        self.frame_scale = frame_scale
        self.frame_skip = max(1, frame_skip)
        self.detection_model = detection_model
        self._frame_counter = 0
        self._known_encodings, self._known_names = load_encodings(cache_first=cache_first)
        self._last_refresh = time.time()

    @property
    def known_encodings(self) -> List[np.ndarray]:
        return self._known_encodings

    @property
    def known_identities(self) -> List[Tuple[str, str]]:
        return self._known_names

    @property
    def known_names(self) -> List[str]:
        return [display for _, display in self._known_names]

    @property
    def known_banner_ids(self) -> List[str]:
        return [banner for banner, _ in self._known_names]

    def refresh_known_faces(self, force_online: bool = False) -> None:
        """Reload encodings from DB (fall back to cache when required)."""
        if force_online:
            encodings, names = load_encodings_from_db()
        else:
            encodings, names = load_encodings()
        self._known_encodings = encodings
        self._known_names = names
        self._last_refresh = time.time()

    def should_refresh(self) -> bool:
        return (time.time() - self._last_refresh) >= DB_REFRESH_INTERVAL

    def match_face_encoding(self, encoding: np.ndarray) -> Tuple[str, bool, float, Optional[str]]:
        if not self._known_encodings:
            return "Unknown", False, 0.0, None

        distances = face_recognition.face_distance(self._known_encodings, encoding)
        min_distance = float(np.min(distances))
        best_idx = int(np.argmin(distances))
        confidence = max(0.0, 1.0 - min_distance)

        if min_distance <= self.match_threshold and best_idx < len(self._known_names):
            banner_id, display_name = self._known_names[best_idx]
            name = display_name or banner_id
            return name, True, confidence, banner_id

        return "Unknown", False, confidence, None

    def analyze_frame(self, frame: np.ndarray, *, skip_frame_check: bool = False) -> List[RecognitionResult]:
        """Analyse a single frame and return recognition results."""
        if frame is None:
            return []
        if not self._known_encodings:
            logger.debug("No known encodings loaded; skipping frame analysis")
            return []

        self._frame_counter += 1
        if not skip_frame_check and self._frame_counter % self.frame_skip != 0:
            return []

        small_frame = cv2.resize(frame, (0, 0), fx=self.frame_scale, fy=self.frame_scale)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model=self.detection_model)

        if not face_locations:
            return []

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        results: List[RecognitionResult] = []

        for encoding, location in zip(face_encodings, face_locations):
            name, matched, confidence, banner_id = self.match_face_encoding(encoding)
            top, right, bottom, left = location
            scale = 1.0 / self.frame_scale if self.frame_scale else 1.0
            box = (
                int(top * scale),
                int(right * scale),
                int(bottom * scale),
                int(left * scale),
            )
            results.append(
                RecognitionResult(
                    name=name,
                    matched=matched,
                    confidence=confidence,
                    banner_id=banner_id,
                    box=box,
                )
            )

        if self.should_refresh():
            with contextlib.suppress(Exception):
                self.refresh_known_faces()

        return results


__all__ = [
    "BASE_DIR",
    "MATCH_THRESHOLD",
    "FRAME_SKIP",
    "FRAME_SCALE",
    "FACE_DETECTION_MODEL",
    "FLASK_APP_URL",
    "ALTERNATIVE_FLASK_URLS",
    "get_db_connection",
    "save_encodings_cache",
    "load_encodings_cache",
    "load_encodings_from_db",
    "load_encodings",
    "log_verification_http",
    "process_order_fulfillment",
    "FaceRecognitionEngine",
    "RecognitionResult",
]
