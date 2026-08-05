# Build context is the repo root (see docker-compose.yml) since this image
# needs the agent/ and eval/ packages alongside backend/.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/
COPY eval/ ./eval/
COPY backend/ ./backend/

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
