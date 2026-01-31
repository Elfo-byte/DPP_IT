from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import cv2
import easyocr

@dataclass(frozen=True)
class OcrResult:
    text: Optional[str]
    confidence: Optional[float]
    crop_used: bool

_reader = None

def get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        # tablice rejestracyjne: zwykle wystarczy 'en'
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader

def crop_with_box(img_bgr: np.ndarray, box: Tuple[float, float, float, float]) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    xtl, ytl, xbr, ybr = box

    x1 = max(0, min(w - 1, int(round(xtl))))
    y1 = max(0, min(h - 1, int(round(ytl))))
    x2 = max(0, min(w, int(round(xbr))))
    y2 = max(0, min(h, int(round(ybr))))

    if x2 <= x1 or y2 <= y1:
        return img_bgr
    return img_bgr[y1:y2, x1:x2]

def ocr_image_bytes(image_bytes: bytes, box: Optional[Tuple[float, float, float, float]] = None) -> OcrResult:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return OcrResult(text=None, confidence=None, crop_used=False)

    crop_used = False
    if box is not None:
        img = crop_with_box(img, box)
        crop_used = True

    reader = get_reader()
    # EasyOCR najlepiej pracuje na RGB:
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    detections = reader.readtext(img_rgb, detail=1)
    if not detections:
        return OcrResult(text=None, confidence=None, crop_used=crop_used)

    # wybieramy najbardziej pewny odczyt
    best = max(detections, key=lambda d: float(d[2]))
    text = str(best[1]).strip() if best[1] is not None else None
    conf = float(best[2]) if best[2] is not None else None
    return OcrResult(text=text or None, confidence=conf, crop_used=crop_used)
