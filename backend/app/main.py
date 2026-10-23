import os
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, Depends, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, engine, Base
from app.models import StoreListing, Platform, CanonicalProduct, PriceHistory

# Ensure tables exist (will not overwrite existing columns)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DealNest API",
    version="1.0.0",
    description="Automated Grocery Price Aggregation and Comparison Engine"
)

# Configure CORS so Vite on port 5173 can query FastAPI on port 8000
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas ---

class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_id: int
    platform_uid: str
    raw_title: str
    url: str
    image_url: Optional[str] = None
    current_mrp: Optional[float] = None
    current_selling_price: float
    in_stock: bool
    location: str
    last_updated: Optional[datetime] = None

class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime


# --- Routes ---

@app.get("/", tags=["Health"])
@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Verifies that the server and PostgreSQL database connection are active."""
    try:
        db.execute(StoreListing.__table__.select().limit(1))
        db_status = "connected"
    except Exception as e:
        db_status = f"unreachable: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.utcnow()
    }


@app.get("/api/v1/deals", response_model=List[DealOut], tags=["Deals"])
def get_deals(
    location: Optional[str] = Query(
        default=None, 
        description="Filter by specific hub, e.g. 'GUDIMALKAPUR'"
    ),
    search: Optional[str] = Query(
        default=None, 
        description="Search title matching keyword"
    ),
    platform_id: Optional[int] = Query(
        default=None, 
        description="Filter by platform identifier"
    ),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Fetches deals with optional filtering by location hub, text search, or platform.
    """
    query = db.query(StoreListing)

    # 1. Location Filtering
    if location and location.strip() and location.lower() != "all locations":
        query = query.filter(StoreListing.location == location.strip())

    # 2. Keyword Search
    if search and search.strip():
        query = query.filter(StoreListing.raw_title.ilike(f"%{search.strip()}%"))

    # 3. Platform Filtering
    if platform_id is not None:
        query = query.filter(StoreListing.platform_id == platform_id)

    # Order by highest discount percentage if MRP exists, otherwise by ID
    deals = query.order_by(desc(StoreListing.id)).offset(skip).limit(limit).all()
    return deals


@app.get("/api/v1/locations", response_model=List[str], tags=["Locations"])
def get_available_locations(db: Session = Depends(get_db)):
    """Returns the list of distinct active locations present in the database."""
    results = db.query(StoreListing.location).distinct().all()
    locations = [r[0] for r in results if r[0]]
    return sorted(locations)
