from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from api.routes import router as api_router
from api.admin_routes import router as admin_router
from backend.db import init_db
from tasks import start_polling_loop
from api.settings_routes import router as settings_router
import os

app = FastAPI(title="Bleeparr 2.0")

# Enable CORS for frontend to access backend APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static frontend assets
app.mount("/assets", StaticFiles(directory="frontend-build/assets"), name="assets")

# Serve index.html at root
@app.get("/")
def read_index():
    return FileResponse("frontend-build/index.html")

# Include backend API routes
app.include_router(api_router)
app.include_router(settings_router)

# Fallback route to support React Router, excluding API and asset requests
@app.get("/{full_path:path}")
def catch_all(request: Request):
    path = request.url.path
    if path.startswith("/api") or path.startswith("/assets"):
        return Response(status_code=404)
    return FileResponse("frontend-build/index.html")

# Start polling loop on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    start_polling_loop()
