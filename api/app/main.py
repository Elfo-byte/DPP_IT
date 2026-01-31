from __future__ import annotations
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pika
from fastapi import FastAPI, UploadFile, File, Query
from pydantic import BaseModel

from .ocr import ocr_image_bytes
from .annotations import load_annotations, best_box_for_image, gt_plate_for_image
from .db import init_db, insert_result, fetch_results

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "pass")
QUEUE_NAME = os.getenv("QUEUE_NAME", "images")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/shared/uploads")
DB_PATH = os.getenv("DB_PATH", "/shared/results.db")
ANNOTATIONS_PATH = os.getenv("ANNOTATIONS_PATH", "/app/app/annotations.xml")

app = FastAPI(title="Plate OCR API (sync + rabbitmq)")
annotations = {}





class AnalyzeResponse(BaseModel):
    filename: str
    gt: str | None
    text: str | None
    exact_match: bool
    db_id: int


def rabbit_publish(payload: dict):
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds, heartbeat=30)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(payload).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conn.close()

import re

def norm_plate(s: str | None) -> str | None:
    if s is None:
        return None
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


@app.on_event("startup")
def _startup():
    global annotations
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    init_db(DB_PATH)
    annotations = load_annotations(ANNOTATIONS_PATH)

@app.post("/analyze-sync", response_model=AnalyzeResponse)
async def analyze_sync(
    file: UploadFile = File(...),
    use_annotations: bool = Query(True, description="Jeśli true i istnieje wartość w annotations.xml, robimy OCR na cropie tablicy"),
):
    image_bytes = await file.read()
    filename = file.filename or f"upload_{int(time.time())}.jpg"

    box = None
    if use_annotations and annotations:
        b = best_box_for_image(annotations, filename)
        if b:
            box = (b.xtl, b.ytl, b.xbr, b.ybr)

    res = ocr_image_bytes(image_bytes, box=box)
    created = datetime.now(timezone.utc).isoformat()
    gt = gt_plate_for_image(ANNOTATIONS_PATH, filename)
    ocr = res.text

    exact_match = (
        norm_plate(gt) is not None
        and norm_plate(gt) == norm_plate(ocr)
    )
    db_id = insert_result(
        DB_PATH,
        filename=filename,
        mode="sync",
        crop_used=res.crop_used,
        text=res.text,
        confidence=res.confidence,
        created_at=created,
    )

    return AnalyzeResponse(
    filename=filename,
    text=res.text,
    gt=gt,
    exact_match=exact_match,
    db_id=db_id,
)



@app.post("/enqueue")
async def enqueue(file: UploadFile = File(...)):
    filename = file.filename or f"upload_{int(time.time())}.jpg"
    content = await file.read()

    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    save_path = str(Path(UPLOAD_DIR) / filename)
    with open(save_path, "wb") as f:
        f.write(content)

    payload = {"filename": filename, "path": save_path, "created_at": datetime.now(timezone.utc).isoformat()}
    rabbit_publish(payload)

    return {"status": "queued", "filename": filename, "path": save_path}

@app.get("/results")
def results(filename: str | None = None, limit: int = 50):
    rows = fetch_results(limit=limit, filename=filename)

    out = []
    for r in rows:
        gt = gt_plate_for_image(ANNOTATIONS_PATH, r["filename"])
        ocr = r["text"]
        out.append({
            "id": r["id"],
            "filename": r["filename"],
            "gt_text": gt,
            "ocr_text": ocr,
            "exact_match": (norm_plate(gt) is not None and norm_plate(gt) == norm_plate(ocr)),
            "created_at": r["created_at"],
        })
    return out
