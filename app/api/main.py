from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import garmin

app = FastAPI(
    title="Coach Bot API",
    description="API for web-based coaching app with Garmin integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            "garmin_activities": "/garmin/activities",
            "garmin_weekly_analysis": "/garmin/analysis/weekly",
            "health_webhook": "/garmin/webhook/health",
            "activity_webhook": "/garmin/webhook/activity"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
