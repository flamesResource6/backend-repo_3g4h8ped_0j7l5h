import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Barbershop

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Barbershop Booking API"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# -------------------------
# Barbershops Endpoints
# -------------------------

class CreateBarbershopRequest(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
    rating: Optional[float] = 4.5
    reviews: Optional[int] = 0
    phone: Optional[str] = None

@app.post("/api/barbershops")
def create_barbershop(payload: CreateBarbershopRequest):
    try:
        barbershop = Barbershop(**payload.model_dump())
        inserted_id = create_document("barbershop", barbershop)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/barbershops")
def list_barbershops(
    q: Optional[str] = Query(None, description="Search by name"),
    lat: Optional[float] = Query(None, description="Latitude for proximity"),
    lng: Optional[float] = Query(None, description="Longitude for proximity"),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        filter_dict = {}
        if q:
            filter_dict["name"] = {"$regex": q, "$options": "i"}

        shops = get_documents("barbershop", filter_dict, limit)

        # naive distance sort if coordinates provided
        if lat is not None and lng is not None:
            def haversine(a_lat, a_lng, b_lat, b_lng):
                from math import radians, sin, cos, sqrt, atan2
                R = 6371
                dlat = radians(b_lat - a_lat)
                dlng = radians(b_lng - a_lng)
                A = sin(dlat/2)**2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(dlng/2)**2
                c = atan2(sqrt(A), sqrt(1-A)) * 2
                return R * c
            for s in shops:
                s["distance_km"] = haversine(lat, lng, float(s.get("lat", 0)), float(s.get("lng", 0)))
            shops.sort(key=lambda x: x.get("distance_km", 1e9))

        # project id as string
        for s in shops:
            if "_id" in s:
                s["id"] = str(s.pop("_id"))
        return {"items": shops}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SeedRequest(BaseModel):
    lat: float
    lng: float

@app.post("/api/barbershops/seed")
def seed_barbershops(payload: SeedRequest):
    try:
        base_lat = payload.lat
        base_lng = payload.lng
        samples = [
            ("Fade Masters", "123 Main St", 0.002, 0.001, 4.8, 210),
            ("Sharp Cuts", "45 Oak Ave", -0.0015, 0.0025, 4.6, 150),
            ("Clip & Sip", "77 Pine Rd", 0.001, -0.002, 4.7, 98),
            ("Urban Barber Co.", "19 Market St", -0.002, -0.001, 4.9, 320),
            ("The Gentleman's Den", "5 River Lane", 0.0005, 0.0015, 4.5, 75),
            ("Blade & Brush", "88 Sunset Blvd", -0.001, -0.002, 4.4, 64),
        ]
        created = []
        for name, address, dlat, dlng, rating, reviews in samples:
            shop = Barbershop(
                name=name,
                address=address,
                lat=base_lat + dlat,
                lng=base_lng + dlng,
                rating=rating,
                reviews=reviews,
            )
            inserted_id = create_document("barbershop", shop)
            created.append(inserted_id)
        return {"created": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
