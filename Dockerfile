FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY cli/ ./cli/
COPY scripts/ ./scripts/
COPY --from=frontend /build/dist ./frontend/dist/
ENV DATA_DIR=/data HF_HOME=/models MEDIA_ROOTS=/media OUTPUT_DIR=/output ORIGINALS_DIR=/originals PYTHONUNBUFFERED=1
EXPOSE 5050
ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "5050", "--workers", "1"]
