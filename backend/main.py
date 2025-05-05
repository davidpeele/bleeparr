from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
from tasks import start_polling_loop

app = FastAPI(title="Bleeparr 2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    start_polling_loop()

@app.get("/")
def read_root():
    return {"message": "Bleeparr 2.0 backend is running"}
