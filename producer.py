# producer.py
import csv
import os
import sys
import uuid
import time
from datetime import datetime

TASKS_FILE = "tasks.csv"
LOCK_FILE = TASKS_FILE + ".lock"


def acquire_lock():
    """Prosty lock na plik działa na zasadzie tworzenia pliku .lock."""
    while True:
        try:
            # os.O_EXCL + os.O_CREAT -> błąd, jeśli plik już istnieje
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            return fd
        except FileExistsError:
            time.sleep(0.5)  # lock zajęty, czekamy chwilkę


def release_lock(fd):
    """Zwolnienie locka."""
    os.close(fd)
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def ensure_tasks_file_exists():
    """Utwórz plik z nagłówkiem, jeśli nie istnieje."""
    if not os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "status", "created_at", "started_at", "finished_at"])


def add_task():
    """Dodaj jedno zadanie do pliku."""
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat(timespec="seconds")

    fd = acquire_lock()
    try:
        ensure_tasks_file_exists()
        with open(TASKS_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([task_id, "pending", now, "", ""])
        print(f"[PRODUCER] Dodano zadanie: {task_id}")
    finally:
        release_lock(fd)


def main():
    # python producer.py 100 -> wrzuci 100 zadań
    count = 1
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            print("Użycie: python producer.py [liczba_zadań]")
            sys.exit(1)

    for _ in range(count):
        add_task()


if __name__ == "__main__":
    main()
