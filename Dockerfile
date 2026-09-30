# Backend (FastAPI)
FROM python:3.11-slim AS backend
WORKDIR /app
COPY ./backend ./backend
COPY ./bleeparr-1.1.py ./
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Frontend (React)
FROM node:20 AS frontend
WORKDIR /app
COPY ./frontend ./
RUN npm install && npm run build

# Combine both backend and frontend into one container
FROM backend AS final
COPY --from=frontend /app/dist /app/frontend-build

ENV UVICORN_PORT=5050
EXPOSE 5050

ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5050", "--app-dir", "backend"]
