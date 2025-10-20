from fastapi import FastAPI
from api.containers import router as containers_router
from api.networking import router as networking_router
from api.logs import router as logs_router

app = FastAPI()

app.include_router(containers_router, prefix="/containers", tags=["containers"])
app.include_router(networking_router, prefix="/networking", tags=["networking"])
app.include_router(logs_router, prefix="/logs", tags=["logs"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Self-Hosted Container Manager API"}