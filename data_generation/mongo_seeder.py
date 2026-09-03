#!/usr/bin/env python3
"""
StaySpot MongoDB Seeder - Generates 500k+ SearchSessions (geospatial pings)
with realistic distribution around San Francisco for StaySpot project.
Uses Faker for realistic data and Pydantic for validation.
"""

import os
import sys
import uuid
import random
import math
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum

try:
    from pymongo import MongoClient, InsertOne
    from pymongo.errors import BulkWriteError
except ImportError:
    print("Error: pymongo not installed. Run: pip install pymongo")
    sys.exit(1)

try:
    from faker import Faker
    from pydantic import BaseModel, Field, field_validator, model_validator
except ImportError:
    print("Error: faker or pydantic not installed. Run: pip install faker pydantic")
    sys.exit(1)


fake = Faker()
Faker.seed(42)
random.seed(42)


SAN_FRANCISCO_CENTER = (-122.4194, 37.7749)


class Platform(str, Enum):
    IOS = "iOS"
    ANDROID = "Android"
    WEB = "Web"


class Hotspot(BaseModel):
    name: str
    lat: float
    lon: float
    weight: float
    radius_km: float


HOTSPOTS = [
    Hotspot(name="Union Square Shopping Core", lat=37.7879, lon=-122.4074, weight=0.15, radius_km=0.8),
    Hotspot(name="SoMa Tech Corridor", lat=37.7853, lon=-122.3999, weight=0.13, radius_km=1.0),
    Hotspot(name="Mission Culinary Strip", lat=37.7599, lon=-122.4196, weight=0.11, radius_km=0.9),
    Hotspot(name="Fisherman's Wharf Tourist Hub", lat=37.8080, lon=-122.4177, weight=0.10, radius_km=1.2),
    Hotspot(name="Pacific Heights Scenic Strip", lat=37.7925, lon=-122.4356, weight=0.08, radius_km=0.8),
    Hotspot(name="Castro Nightlife District", lat=37.7609, lon=-122.4350, weight=0.07, radius_km=0.7),
    Hotspot(name="Presidio Heights Edge", lat=37.7885, lon=-122.4550, weight=0.05, radius_km=1.0),
    Hotspot(name="Inner Sunset Park Area", lat=37.7694, lon=-122.4662, weight=0.05, radius_km=0.8),
    Hotspot(name="Marina Waterfront", lat=37.8037, lon=-122.4368, weight=0.06, radius_km=0.9),
    Hotspot(name="Financial District Core", lat=37.7946, lon=-122.3999, weight=0.09, radius_km=0.6),
    Hotspot(name="Hayes Valley", lat=37.7762, lon=-122.4268, weight=0.06, radius_km=0.5),
    Hotspot(name="Noe Valley", lat=37.7465, lon=-122.4323, weight=0.05, radius_km=0.7),
]

OUT_OF_RANGE_HOTSPOTS = [
    Hotspot(name="Ocean Beach", lat=37.7600, lon=-122.5090, weight=0.03, radius_km=0.8),
    Hotspot(name="Oakland Downtown", lat=37.8044, lon=-122.2711, weight=0.02, radius_km=1.0),
    Hotspot(name="Daly City BART", lat=37.7058, lon=-122.4619, weight=0.02, radius_km=0.8),
    Hotspot(name="SFO Airport", lat=37.6189, lon=-122.3750, weight=0.01, radius_km=1.5),
]

USER_POOL_SIZE = 50000
APP_VERSIONS = ["3.4.1", "3.4.0", "3.3.2", "3.3.1"]
SEARCH_RADII = [500, 1000, 2000, 3000, 5000, 8000, 10000]
MIN_PRICES = [50, 75, 100, 125, 150, 200]
MAX_PRICES = [250, 300, 400, 500, 600, 750, 1000]
MIN_RATINGS = [3.0, 3.5, 4.0, 4.5]


ALL_AMENITIES = [
    "High-Speed WiFi", "Dedicated Workspace", "Air Conditioning", "Kitchen",
    "Free Parking", "Pet Friendly", "Pool", "Gym", "Washer", "Dryer",
    "EV Charging", "Rooftop Access", "Balcony", "Ocean View", "City View",
    "Hot Tub", "Fireplace", "BBQ Grill", "Bicycle Storage", "Elevator",
    "Doorman", "Security System", "Smart Lock", "Keyless Entry", "Coffee Machine",
    "Wine Fridge", "Dishwasher", "Espresso Machine", "Sound System", "Projector"
]


def generate_amenity_set() -> List[str]:
    num_amenities = random.randint(1, 4)
    return random.sample(ALL_AMENITIES, num_amenities)


class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., min_length=2, max_length=2)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: List[float]) -> List[float]:
        if len(v) != 2:
            raise ValueError("Coordinates must be [longitude, latitude]")
        lon, lat = v
        if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
            raise ValueError("Invalid longitude/latitude")
        return [round(lon, 6), round(lat, 6)]


class DeviceInfo(BaseModel):
    platform: Platform
    app_version: str
    device_model: str = Field(default_factory=lambda: fake.random_element([
        "iPhone 15 Pro", "iPhone 14", "iPhone 13", "Samsung Galaxy S24",
        "Samsung Galaxy S23", "Google Pixel 8", "Google Pixel 7",
        "iPad Pro", "MacBook Pro", "Windows Laptop", "Chrome Browser"
    ]))


class SearchFilters(BaseModel):
    min_price: int = Field(default_factory=lambda: random.choice(MIN_PRICES))
    max_price: int = Field(default_factory=lambda: random.choice(MAX_PRICES))
    min_rating: float = Field(default_factory=lambda: random.choice(MIN_RATINGS))
    required_amenities: List[str] = Field(default_factory=generate_amenity_set)
    check_in_date: Optional[str] = Field(default_factory=lambda: (datetime.now() + timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d"))
    guests: int = Field(default_factory=lambda: random.randint(1, 6))
    instant_book: bool = Field(default_factory=lambda: random.choice([True, False]))


class SearchSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:12]}")
    user_id: str
    location: GeoPoint
    search_radius_meters: int = Field(default_factory=lambda: random.choice(SEARCH_RADII))
    filters: SearchFilters = Field(default_factory=SearchFilters)
    device_info: DeviceInfo = Field(default_factory=lambda: DeviceInfo(
        platform=random.choice(list(Platform)),
        app_version=random.choice(APP_VERSIONS)
    ))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_price_range(self) -> "SearchSession":
        if self.filters.min_price >= self.filters.max_price:
            self.filters.max_price = self.filters.min_price + 50
        return self

    def to_mongo_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "location": self.location.model_dump(),
            "search_radius_meters": self.search_radius_meters,
            "filters": self.filters.model_dump(),
            "device_info": self.device_info.model_dump(),
            "created_at": self.created_at
        }


def generate_user_pool(size: int) -> List[str]:
    return [str(uuid.uuid4()) for _ in range(size)]


def random_point_in_radius(center_lat: float, center_lon: float, radius_km: float) -> tuple:
    angle = random.random() * 2 * math.pi
    r = radius_km * math.sqrt(random.random())
    dlat = (r / 111.32) * math.cos(angle)
    dlon = (r / (111.32 * math.cos(center_lat * math.pi / 180))) * math.sin(angle)
    return round(center_lat + dlat, 6), round(center_lon + dlon, 6)


def generate_session(user_pool: List[str], hotspot: Hotspot, now: datetime) -> SearchSession:
    lat, lon = random_point_in_radius(hotspot.lat, hotspot.lon, hotspot.radius_km)
    minutes_ago = random.randint(1, 115)
    created_at = now - timedelta(minutes=minutes_ago)
    user_id = random.choice(user_pool)
    
    return SearchSession(
        user_id=user_id,
        location=GeoPoint(coordinates=[lon, lat]),
        created_at=created_at
    )


def seed_search_sessions(
    uri: str,
    db_name: str,
    target_count: int,
    batch_size: int = 5000,
    clear_existing: bool = True
) -> int:
    client = MongoClient(uri)
    db = client[db_name]
    collection = db["SearchSessions"]
    
    if clear_existing:
        print(f"Clearing existing SearchSessions...")
        collection.delete_many({})
    
    collection.create_index([("location", "2dsphere")], name="idx_searchsessions_location_2dsphere")
    collection.create_index(
        [("created_at", 1)], 
        name="idx_searchsessions_created_at_ttl_2h", 
        expireAfterSeconds=7200
    )
    collection.create_index(
        [("user_id", 1), ("created_at", -1)], 
        name="idx_searchsessions_user_time"
    )
    
    print(f"Target: {target_count:,} SearchSessions")
    print(f"Batch size: {batch_size:,}")
    print(f"Hotspots: {len(HOTSPOTS)} in-range + {len(OUT_OF_RANGE_HOTSPOTS)} out-of-range")
    print()
    
    user_pool = generate_user_pool(USER_POOL_SIZE)
    now = datetime.utcnow()
    
    all_hotspots = HOTSPOTS + OUT_OF_RANGE_HOTSPOTS
    weights = [h.weight for h in all_hotspots]
    
    total_inserted = 0
    batch = []
    
    try:
        for i in range(target_count):
            hotspot = random.choices(all_hotspots, weights=weights, k=1)[0]
            session = generate_session(user_pool, hotspot, now)
            batch.append(InsertOne(session.to_mongo_dict()))
            
            if len(batch) >= batch_size:
                result = collection.bulk_write(batch, ordered=False)
                total_inserted += result.inserted_count
                batch = []
                if total_inserted % 50000 == 0:
                    print(f"  Inserted: {total_inserted:,} / {target_count:,} ({total_inserted/target_count*100:.1f}%)")
        
        if batch:
            result = collection.bulk_write(batch, ordered=False)
            total_inserted += result.inserted_count
            
    except BulkWriteError as e:
        print(f"Bulk write error: {e.details}")
        total_inserted += e.details.get("nInserted", 0)
    
    print(f"\nCompleted: {total_inserted:,} SearchSessions inserted")
    print(f"Collection count: {collection.count_documents({}):,}")
    
    client.close()
    return total_inserted


def main():
    parser = argparse.ArgumentParser(description="StaySpot MongoDB Seeder")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="stayspot", help="Database name")
    parser.add_argument("--count", type=int, default=500000, help="Number of SearchSessions to generate")
    parser.add_argument("--batch", type=int, default=5000, help="Batch size for bulk inserts")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear existing data")
    args = parser.parse_args()
    
    print("=" * 60)
    print("StaySpot MongoDB Seeder - SearchSessions Generator")
    print("=" * 60)
    print(f"MongoDB: {args.uri}/{args.db}")
    print(f"Target: {args.count:,} geospatial pings")
    print()
    
    seed_search_sessions(
        uri=args.uri,
        db_name=args.db,
        target_count=args.count,
        batch_size=args.batch,
        clear_existing=not args.no_clear
    )


if __name__ == "__main__":
    main()