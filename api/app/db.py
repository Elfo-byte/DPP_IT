import sqlite3
from pathlib import Path
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/shared/results.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS ocr_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  mode TEXT NOT NULL,              -- "sync" albo "async"
  crop_used INTEGER NOT NULL,      -- 0/1
  text TEXT,
  confidence REAL,
  created_at TEXT NOT NULL
);
"""

def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute(SCHEMA)
        con.commit()

def insert_result(db_path: str, filename: str, mode: str, crop_used: bool, text: str | None, confidence: float | None, created_at: str) -> int:
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO ocr_results(filename, mode, crop_used, text, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (filename, mode, 1 if crop_used else 0, text, confidence, created_at),
        )
        con.commit()
        return int(cur.lastrowid)
    
from typing import Optional

def fetch_results(limit: int = 50, filename: Optional[str] = None, db_path: Optional[str] = None):
    if db_path is None:
        db_path = DB_PATH

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        q = """
        SELECT id, filename, mode, crop_used, text, confidence, created_at
        FROM ocr_results
        """
        params = []
        if filename:
            q += " WHERE filename = ?"
            params.append(filename)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]



