#!/usr/bin/env python3
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

HOUSE_RULES = [
    "No smoking", "No parties", "Quiet hours after 10pm", "No pets",
    "Check-in after 3pm", "Checkout by 11am", "Remove shoes at entry",
    "Recycling and compost required", "Max 2 guests per bedroom", "No candles",
    "Lock door when leaving", "Thermostat set to 68°F max", "Patio furniture to remain indoors"
]

HOUSE_RULES_OBJECTS = [
    {"rule": "early_checkin", "description": "Early check-in available upon request - contact host 24h in advance"},
    {"rule": "late_checkout", "description": "Late checkout until 2pm available for $25 fee"},
    {"rule": "visitor_policy", "description": "Registered guests only - no unauthorized visitors after 9pm"},
    {"rule": "parking_instructions", "description": "Street parking only - permit required Mon-Sat"},
    {"rule": "noise_sensor", "description": "Noise monitoring device installed - violations result in $100 fine"}
]

ACCESSIBILITY_FEATURES = [
    "Step-free entrance", "Wide doorways (36+ inches)", "Elevator access",
    "Grab bars in bathroom", "Roll-in shower", "Lowered light switches",
    "Accessible parking spot", "Visual doorbell", "Braille elevator buttons"
]

ACCESSIBILITY_FEATURES_OBJECTS = [
    {"feature": "wheelchair_ramp", "description": "Portable wheelchair ramp available at entrance"},
    {"feature": "shower_seat", "description": "Fold-down shower seat installed"},
    {"feature": "handheld_shower", "description": "Handheld showerhead for seated bathing"}
]

SAFETY_FEATURES = [
    "Smoke detector", "Fire extinguisher", "First aid kit",
    "Carbon monoxide detector", "Lockbox for keys", "Exterior lighting"
]

LOCATION_TAGS = [
    "downtown", "walkable", "public_transit", "restaurants", "nightlife",
    "shopping", "beach", "parks", "museums", "tourist_attractions",
    "quiet_neighborhood", "central_location", "boutique_shops", "cafes",
    "grocery_stores", "fitness_center", "hospital_nearby", "airport_convenient",
    "mountain_views", "waterfront", "historic_district", "arts_district"
]

REVIEW_SUB_RATINGS = ["cleanliness", "accuracy", "communication", "location", "check_in", "value"]


def generate_amenity_set() -> List[str]:
    num_amenities = random.randint(5, 15)
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


class HouseRule(BaseModel):
    rule: str


class PropertyAmenities(BaseModel):
    property_id: str
    property_title: Optional[str] = None
    amenities: List[str]
    house_rules: List
    accessibility_features: List
    safety_features: Optional[List[str]] = None
    host_guidelines: Optional[Dict[str, Any]] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_mongo_dict(self) -> Dict[str, Any]:
        doc = {
            "property_id": self.property_id,
            "amenities": self.amenities,
            "house_rules": self.house_rules,
            "accessibility_features": self.accessibility_features,
            "updated_at": self.updated_at
        }
        if self.property_title:
            doc["property_title"] = self.property_title
        if self.safety_features:
            doc["safety_features"] = self.safety_features
        if self.host_guidelines:
            doc["host_guidelines"] = self.host_guidelines
        return doc


class SubRatings(BaseModel):
    cleanliness: Optional[int] = None
    accuracy: Optional[int] = None
    communication: Optional[int] = None
    location: Optional[int] = None
    check_in: Optional[int] = None
    value: Optional[int] = None


class PropertyReview(BaseModel):
    property_id: str
    guest_id: str
    booking_id: Optional[str] = None
    rating: int
    sub_ratings: Optional[Dict[str, Any]] = None
    location_tags: List[str]
    review_text: str
    created_at: datetime

    def to_mongo_dict(self) -> Dict[str, Any]:
        doc = {
            "property_id": self.property_id,
            "guest_id": self.guest_id,
            "rating": self.rating,
            "location_tags": self.location_tags,
            "review_text": self.review_text,
            "created_at": self.created_at
        }
        if self.booking_id:
            doc["booking_id"] = self.booking_id
        if self.sub_ratings:
            doc["sub_ratings"] = self.sub_ratings
        return doc


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


def generate_property_amenities(property_id: str, property_title: Optional[str] = None) -> PropertyAmenities:
    house_rules = []
    num_rules = random.randint(3, 8)
    for _ in range(num_rules):
        if random.random() < 0.7:
            house_rules.append(random.choice(HOUSE_RULES))
        else:
            house_rules.append(random.choice(HOUSE_RULES_OBJECTS).copy())

    accessibility_features = []
    num_access = random.randint(2, 5)
    for _ in range(num_access):
        if random.random() < 0.7:
            accessibility_features.append(random.choice(ACCESSIBILITY_FEATURES))
        else:
            accessibility_features.append(random.choice(ACCESSIBILITY_FEATURES_OBJECTS).copy())

    safety_features = None
    if random.random() < 0.6:
        num_safety = random.randint(2, 4)
        safety_features = random.sample(SAFETY_FEATURES, num_safety)

    host_guidelines = None
    if random.random() < 0.4:
        host_guidelines = {
            "keyless_entry": f"Code: {random.randint(1000, 9999)}",
            "parking": random.choice(["Free street parking", "Paid garage - $25/day", "No parking available"]),
            "wifi": f"Network: StaySpot-Guest Password: {fake.word()}{random.randint(10, 99)}",
            "host_contact": fake.email()
        }

    return PropertyAmenities(
        property_id=property_id,
        property_title=property_title,
        amenities=generate_amenity_set(),
        house_rules=house_rules,
        accessibility_features=accessibility_features,
        safety_features=safety_features,
        host_guidelines=host_guidelines
    )


def generate_property_review(
    property_ids: List[str],
    guest_ids: List[str],
    booking_ids: Optional[List[str]] = None
) -> PropertyReview:
    property_id = random.choice(property_ids)
    guest_id = random.choice(guest_ids)

    booking_id = None
    if booking_ids and random.random() < 0.7:
        booking_id = random.choice(booking_ids)

    rating = random.randint(3, 5)
    sub_ratings = None
    if random.random() < 0.7:
        sub_ratings = {}
        for sub in REVIEW_SUB_RATINGS:
            if random.random() < 0.8:
                sub_ratings[sub] = random.randint(max(1, rating - 1), min(5, rating + 1))

    num_tags = random.randint(2, 5)
    location_tags = random.sample(LOCATION_TAGS, num_tags)

    review_templates = [
        "Great place to stay! {} Highly recommended.",
        "Beautiful property with {} The host was wonderful.",
        "{} and perfect location. Would definitely book again.",
        "Fantastic experience! {} Everything was clean and comfortable.",
        "Wonderful stay! {} The neighborhood is lovely.",
    ]
    adjectives = ["Loved it!", "Amazing views!", "Very clean!", "Perfect for our trip!", "Great value!"]
    review_text = random.choice(review_templates).format(random.choice(adjectives), random.choice(adjectives))
    if len(review_text) < 10:
        review_text = f"Really enjoyed our stay. {random.choice(adjectives)} Would come back!"
    review_text = review_text[:500] if len(review_text) > 500 else review_text

    days_ago = random.randint(1, 365)
    created_at = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23))

    return PropertyReview(
        property_id=property_id,
        guest_id=guest_id,
        booking_id=booking_id,
        rating=rating,
        sub_ratings=sub_ratings,
        location_tags=location_tags,
        review_text=review_text,
        created_at=created_at
    )


def seed_property_amenities(
    uri: str,
    db_name: str,
    property_ids: List[str],
    property_titles: Optional[List[str]] = None,
    batch_size: int = 5000,
    clear_existing: bool = True
) -> int:
    client = MongoClient(uri)
    db = client[db_name]
    collection = db["PropertyAmenities"]

    if clear_existing:
        print(f"Clearing existing PropertyAmenities...")
        collection.delete_many({})

    print(f"Seeding PropertyAmenities for {len(property_ids):,} properties...")
    print()

    total_inserted = 0
    batch = []

    try:
        for i, prop_id in enumerate(property_ids):
            title = property_titles[i] if property_titles and i < len(property_titles) else None
            amenities = generate_property_amenities(prop_id, title)
            batch.append(InsertOne(amenities.to_mongo_dict()))

            if len(batch) >= batch_size:
                result = collection.bulk_write(batch, ordered=False)
                total_inserted += result.inserted_count
                batch = []

        if batch:
            result = collection.bulk_write(batch, ordered=False)
            total_inserted += result.inserted_count

    except BulkWriteError as e:
        print(f"Bulk write error: {e.details}")
        total_inserted += e.details.get("nInserted", 0)

    print(f"Completed: {total_inserted:,} PropertyAmenities inserted")
    print(f"Collection count: {collection.count_documents({}):,}")

    client.close()
    return total_inserted


def seed_property_reviews(
    uri: str,
    db_name: str,
    property_ids: List[str],
    guest_ids: List[str],
    booking_ids: Optional[List[str]] = None,
    reviews_per_property: int = 5,
    batch_size: int = 5000,
    clear_existing: bool = True
) -> int:
    client = MongoClient(uri)
    db = client[db_name]
    collection = db["PropertyReviews"]

    if clear_existing:
        print(f"Clearing existing PropertyReviews...")
        collection.delete_many({})

    total_target = len(property_ids) * reviews_per_property
    print(f"Seeding PropertyReviews: ~{total_target:,} reviews ({reviews_per_property} per property)...")
    print()

    total_inserted = 0
    batch = []

    try:
        for prop_id in property_ids:
            for _ in range(reviews_per_property):
                review = generate_property_review(property_ids, guest_ids, booking_ids)
                batch.append(InsertOne(review.to_mongo_dict()))

                if len(batch) >= batch_size:
                    result = collection.bulk_write(batch, ordered=False)
                    total_inserted += result.inserted_count
                    batch = []

        if batch:
            result = collection.bulk_write(batch, ordered=False)
            total_inserted += result.inserted_count

    except BulkWriteError as e:
        print(f"Bulk write error: {e.details}")
        total_inserted += e.details.get("nInserted", 0)

    print(f"Completed: {total_inserted:,} PropertyReviews inserted")
    print(f"Collection count: {collection.count_documents({}):,}")

    client.close()
    return total_inserted


def main():
    parser = argparse.ArgumentParser(description="StaySpot MongoDB Seeder")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="stayspot", help="Database name")
    parser.add_argument("--sessions", type=int, default=500000, help="Number of SearchSessions to generate")
    parser.add_argument("--reviews-per-property", type=int, default=5, help="Number of reviews per property")
    parser.add_argument("--batch", type=int, default=5000, help="Batch size for bulk inserts")
    parser.add_argument("--no-clear", default=False, action="store_true", help="Don't clear existing data")
    parser.add_argument("--pg-uri", default=None, help="PostgreSQL URI to fetch property/guest IDs (optional for --seed-all, uses synthetic UUIDs if omitted)")
    parser.add_argument("--seed-all", action="store_true", help="Seed PropertyAmenities and PropertyReviews (works with or without --pg-uri)")
    parser.add_argument("--property-count", type=int, default=1000, help="Number of properties to simulate when not using --pg-uri")
    args = parser.parse_args()

    print("=" * 60)
    print("StaySpot MongoDB Seeder")
    print("=" * 60)
    print(f"MongoDB: {args.uri}/{args.db}")
    print()

    property_ids = None
    guest_ids = None
    booking_ids = None

    if args.seed_all:
        if args.pg_uri:
            try:
                import psycopg2
                conn = psycopg2.connect(args.pg_uri)
                cur = conn.cursor()
                cur.execute("SELECT id FROM properties ORDER BY id")
                property_ids = [str(row[0]) for row in cur.fetchall()]
                cur.execute("SELECT id FROM guests ORDER BY id")
                guest_ids = [str(row[0]) for row in cur.fetchall()]
                cur.execute("SELECT id FROM bookings ORDER BY id")
                booking_ids = [str(row[0]) for row in cur.fetchall()]
                cur.close()
                conn.close()
                print(f"Loaded {len(property_ids):,} properties, {len(guest_ids):,} guests, {len(booking_ids):,} bookings from PostgreSQL")
                print()
            except ImportError:
                print("Error: psycopg2-binary required for --pg-uri. Run: pip install psycopg2-binary")
                sys.exit(1)
            except Exception as e:
                print(f"Error connecting to PostgreSQL: {e}")
                sys.exit(1)
        else:
            print(f"Generating synthetic UUIDs for {args.property_count:,} properties...")
            property_ids = [str(uuid.uuid4()) for _ in range(args.property_count)]
            guest_ids = [str(uuid.uuid4()) for _ in range(args.property_count * 10)]
            booking_ids = [str(uuid.uuid4()) for _ in range(args.property_count * 50)]
            print(f"  -> {len(property_ids):,} property IDs, {len(guest_ids):,} guest IDs, {len(booking_ids):,} booking IDs")
            print()

    print(f"SearchSessions target: {args.sessions:,} geospatial pings")
    print()
    print("-" * 60)

    seed_search_sessions(
        uri=args.uri,
        db_name=args.db,
        target_count=args.sessions,
        batch_size=args.batch,
        clear_existing=not args.no_clear
    )

    if args.seed_all and property_ids and guest_ids:
        print()
        print("=" * 60)
        print("Seeding PropertyAmenities & PropertyReviews")
        print("=" * 60)
        print()

        seed_property_amenities(
            uri=args.uri,
            db_name=args.db,
            property_ids=property_ids,
            batch_size=args.batch,
            clear_existing=not args.no_clear
        )

        print()

        seed_property_reviews(
            uri=args.uri,
            db_name=args.db,
            property_ids=property_ids,
            guest_ids=guest_ids,
            booking_ids=booking_ids,
            reviews_per_property=args.reviews_per_property,
            batch_size=args.batch,
            clear_existing=not args.no_clear
        )

    print()
    print("[SUCCESS] MongoDB seeding completed!")


if __name__ == "__main__":
    main()