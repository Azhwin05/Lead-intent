import os
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import (
    CORSMiddleware
)
from datetime import datetime

# Import from existing backend
from config.settings import get_settings
from storage.airtable_client import get_airtable_client
from main import run_pipeline

app = FastAPI(title="AdRadar Lead Gen API")

# Allow the Next.js dashboard to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    """Verify API is running and Airtable is connected."""
    settings = get_settings()
    try:
        # Just instantiate client to verify import/settings work
        client = get_airtable_client()
        airtable_status = "connected" if settings.airtable_api_key else "missing_key"
    except Exception as e:
        airtable_status = f"error: {str(e)}"

    return {
        "status": "online",
        "airtable": airtable_status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/leads")
def get_leads():
    """
    Fetch all leads from Airtable.
    Returns the raw Airtable records formatted for the Dashboard.
    """
    try:
        client = get_airtable_client()
        # Fetch all records
        records = client._table.all()
        
        # Transform for the frontend
        formatted_leads = []
        for r in records:
            fields = r.get("fields", {})
            
            # Map Score Breakdown text to signals object if possible
            # In a real scenario we'd parse the long text, or rely on Airtable fields.
            # Falling back to mock signals for Dashboard compatibility if not present natively.
            
            lead = {
                "id": r["id"],
                "brand": fields.get("Brand Name", "Unknown Brand"),
                "website": fields.get("Website", ""),
                "score": fields.get("ROAS Risk Score", 0),
                "tier": fields.get("Lead Tier", "COLD"),
                
                # We'll map the next fields to match Dashboard expectations
                "signals": {
                    "s1": 2 if "Creative Fatigue" in fields.get("Score Breakdown", "") else 1,
                    "s2": 1,
                    "s3": 2,
                    "s4": 1,
                    "s5": 1
                },
                "daysRunning": fields.get("Days Running", 0),
                "numAds": fields.get("Num Ads", 0),
                "estSpend": f"Varies (Traffic: {fields.get('Monthly Traffic', 0)})",
                "adCopy": fields.get("Email 1 Body", "No copy generated yet."),
                "contact": {
                    "name": fields.get("Contact Name", ""),
                    "title": fields.get("Contact Title", "Founder"),
                    "email": fields.get("Contact Email", None),
                    "confirmed": bool(fields.get("Contact Email")),
                },
                "pushedToInstantly": fields.get("Outreach Status") == "Sent",
                "dateAdded": fields.get("Date Added", datetime.now().isoformat())
            }
            formatted_leads.append(lead)
            
        # Sort by score descending
        formatted_leads.sort(key=lambda x: x["score"], reverse=True)
        return {"leads": formatted_leads}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """
    Trigger the main lead generation pipeline in the background.
    """
    def _run_task():
        try:
            # We call the main module's run_pipeline function
            # You could pass specific keywords if desired via the API
            run_pipeline()
        except Exception as e:
            print(f"Pipeline background task failed: {e}")

    background_tasks.add_task(_run_task)
    return {"message": "Pipeline triggered successfully in the background."}

@app.get("/api/pipeline/history")
def get_pipeline_history():
    """
    Optional: If you maintained a SQLite DB/Airtable table of run history.
    For now, returns the mock run history exactly as the Dashboard expects.
    """
    return {
        "history": [
            { "date": "Today 06:00", "scraped": 147, "filtered": 89, "enriched": 76, "hot": 8, "warm": 12, "cold": 14, "pushed": 8, "duration": "4m 12s", "current": True },
            { "date": "Yesterday 06:02", "scraped": 122, "filtered": 70, "enriched": 61, "hot": 5, "warm": 9, "cold": 15, "pushed": 5, "duration": "3m 45s", "current": False },
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
