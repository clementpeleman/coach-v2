from fastapi import FastAPI
from app.api import garmin

app = FastAPI(
    title="Coach Bot API",
    description="API for Telegram coaching bot with Garmin integration",
    version="1.0.0"
)

# Include Garmin OAuth and webhook routes
app.include_router(garmin.router)

@app.get("/")
def read_root():
    return {
        "message": "Coach Bot API",
        "endpoints": {
            "garmin_auth_start": "/garmin/auth/start",
            "garmin_auth_callback": "/garmin/auth/callback",
            "garmin_auth_status": "/garmin/auth/status",
            "garmin_disconnect": "/garmin/auth/disconnect",
            "health_webhook": "/garmin/webhook/health",
            "activity_webhook": "/garmin/webhook/activity"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
