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

# Final stage: Serve both frontend and backend
FROM python:3.11-slim
WORKDIR /app

COPY --from=backend /app /app
COPY --from=frontend /app/dist /app/frontend-build

ENV UVICORN_PORT=5050
EXPOSE 5050

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "5050"]
