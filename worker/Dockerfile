FROM python:3.11-slim

WORKDIR /worker

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .
# jeśli nie montujesz annotations.xml jako volume, możesz go skopiować:
# COPY ../api/app/annotations.xml ./annotations.xml

CMD ["python", "worker.py"]
