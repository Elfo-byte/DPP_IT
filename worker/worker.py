from __future__ import annotations
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pika
import numpy as np
import cv2
import easyocr
import xml.etree.ElementTree as ET

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "pass")
QUEUE_NAME = os.getenv("QUEUE_NAME", "images")

DB_PATH = os.getenv("DB_PATH", "/shared/results.db")
ANNOTATIONS_PATH = os.getenv("ANNOTATIONS_PATH", "/worker/annotations.xml")

SCHEMA = """
CREATE TABLE IF NOT EXISTS ocr_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  mode TEXT NOT NULL,
  crop_used INTEGER NOT NULL,
  text TEXT,
  confidence REAL,
  created_at TEXT NOT NULL
);
"""

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(SCHEMA)
        con.commit()

def insert_result(filename: str, crop_used: bool, text: str | None, confidence: float | None):
    created = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO ocr_results(filename, mode, crop_used, text, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (filename, "async", 1 if crop_used else 0, text, confidence, created),
        )
        con.commit()

def load_annotations(path: str) -> dict[str, tuple[float,float,float,float]]:
    p = Path(path)
    if not p.exists():
        return {}
    tree = ET.parse(p)
    root = tree.getroot()
    out: dict[str, tuple[float,float,float,float]] = {}
    for img in root.findall("image"):
        name = img.attrib.get("name")
        if not name:
            continue
        box = img.find("box")
        if box is None:
            continue
        try:
            xtl = float(box.attrib["xtl"])
            ytl = float(box.attrib["ytl"])
            xbr = float(box.attrib["xbr"])
            ybr = float(box.attrib["ybr"])
            out[name] = (xtl, ytl, xbr, ybr)
        except Exception:
            pass
    return out

def crop_with_box(img_bgr: np.ndarray, box):
    h, w = img_bgr.shape[:2]
    xtl, ytl, xbr, ybr = box
    x1 = max(0, min(w - 1, int(round(xtl))))
    y1 = max(0, min(h - 1, int(round(ytl))))
    x2 = max(0, min(w, int(round(xbr))))
    y2 = max(0, min(h, int(round(ybr))))
    if x2 <= x1 or y2 <= y1:
        return img_bgr
    return img_bgr[y1:y2, x1:x2]

def ocr_file(path: str, box=None):
    img = cv2.imread(path)
    if img is None:
        return None, None, False

    crop_used = False
    if box is not None:
        img = crop_with_box(img, box)
        crop_used = True

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    detections = reader.readtext(img_rgb, detail=1)
    if not detections:
        return None, None, crop_used

    best = max(detections, key=lambda d: float(d[2]))
    text = str(best[1]).strip() if best[1] is not None else None
    conf = float(best[2]) if best[2] is not None else None
    return (text or None), conf, crop_used

def connect_with_retry():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds, heartbeat=30)
    for _ in range(60):
        try:
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue=QUEUE_NAME, durable=True)
            ch.basic_qos(prefetch_count=1)
            return conn, ch
        except Exception:
            time.sleep(1)
    raise RuntimeError("Nie mogę połączyć się z RabbitMQ (timeout).")

init_db()
annotations = load_annotations(ANNOTATIONS_PATH)
reader = easyocr.Reader(["en"], gpu=False)

def on_message(ch, method, properties, body: bytes):
    try:
        payload = json.loads(body.decode("utf-8"))
        filename = payload["filename"]
        path = payload["path"]
        box = annotations.get(filename)

        print(f"[worker] OCR start: {filename} ({path})")
        text, conf, crop_used = ocr_file(path, box=box)
        insert_result(filename=filename, crop_used=crop_used, text=text, confidence=conf)
        print(f"[worker] OCR done: {filename} -> {text} (conf={conf}) crop={crop_used}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[worker] ERROR: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

conn, ch = connect_with_retry()
ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
print("Worker działa: czekam na wiadomości z kolejki...")
ch.start_consuming()
