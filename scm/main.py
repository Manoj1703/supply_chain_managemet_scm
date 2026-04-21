import os

from fastapi import FastAPI
import uvicorn

from database.db import init_db, is_db_connected
from route.device import router as device_router
from route.history import router as history_router
from route.shipment import router as shipment_router
from route.user import router as user_router
from services.kafka_service import start_device_consumer


app = FastAPI(
    title="SCM Management System",
    version="0.1.0",
    description="SCM backend with devices, shipments, history, signup, login, and account APIs.",
    openapi_tags=[
        {"name": "health", "description": "Health check endpoint."},
        {"name": "auth", "description": "Signup and login endpoints."},
        {"name": "devices", "description": "Device data ingestion and listing."},
        {"name": "shipments", "description": "Shipment creation and listing."},
        {"name": "history", "description": "Activity history listing."},
    ],
)


@app.get("/", include_in_schema=False)
def home() -> dict[str, object]:
    return {
        "message": "SCM backend is running",
        "docs": "/docs",
        "health": "/health",
        "auth": ["/signup", "/login", "/me", "/verify-password", "/change-password"],
        "devices": ["/api/devices/", "/api/devices/events"],
        "shipments": ["/api/shipments/"],
        "history": ["/api/history/"],
    }


@app.get("/health", tags=["health"], summary="Health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": "connected" if is_db_connected() else "disconnected"}


app.include_router(user_router)
app.include_router(device_router)
app.include_router(shipment_router)
app.include_router(history_router)


@app.on_event("startup")
def startup() -> None:
    if not init_db():
        print("MongoDB is not reachable. Set MONGODB_URI or start MongoDB on localhost:27017.")
    if start_device_consumer():
        print("Kafka device consumer started.")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)
