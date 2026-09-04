#!/usr/bin/env python3

import os
import sys
import uuid
import random
import argparse
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Tuple, Optional
from enum import Enum

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ImportError:
    print("Error: psycopg2-binary not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

try:
    from faker import Faker
    from pydantic import BaseModel, Field, field_validator, model_validator
    from pydantic.types import UUID4
except ImportError:
    print("Error: faker or pydantic not installed. Run: pip install faker pydantic")
    sys.exit(1)


fake = Faker()
Faker.seed(42)
random.seed(42)


GUEST_COUNT = 10000
PROPERTY_COUNT = 1000
BOOKING_COUNT = 50000
AUDIT_LOG_COUNT = 100000
BATCH_SIZE = 5000


class BookingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"


class AuditAction(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


SF_NEIGHBORHOODS = [
    "Union Square", "SoMa", "Mission District", "Fisherman's Wharf",
    "Pacific Heights", "Inner Sunset", "Marina", "Castro",
    "Nob Hill", "Financial District", "Hayes Valley", "Noe Valley",
    "Presidio", "Richmond District", "Sunset District", "Dogpatch",
    "Potrero Hill", "Bernal Heights", "Glen Park", "Excelsior"
]

PROPERTY_TYPES = [
    "Luxury Loft", "Modern Apartment", "Charming Victorian", "Boutique Suite",
    "Scenic Hilltop Haven", "Cozy Studio", "Waterfront Oasis", "Cultural Retreat",
    "Penthouse", "Garden Cottage", "Tech-Friendly Condo", "Historic Brownstone"
]

AMENITY_POOL = [
    "High-Speed WiFi", "Air Conditioning", "Dedicated Workspace", "Smart TV",
    "Elevator", "Coffee Bar", "Gigabit Fiber WiFi", "EV Charging Station",
    "In-Unit Washer/Dryer", "Gym Access", "Rooftop Terrace", "Garden Patio",
    "Espresso Machine", "Chef's Kitchen", "Radiant Floor Heating", "Vinyl Record Player",
    "Bay Views", "Breakfast Included", "Bicycle Storage", "Fireplace",
    "Panoramic City Views", "Hot Tub", "Private Garage", "Wine Cellar", "Sonos Sound System"
]


class Guest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(default_factory=lambda: fake.name())
    wallet_balance: Decimal = Field(default_factory=lambda: Decimal(str(round(random.uniform(50.0, 5000.0), 2))))

    @field_validator("wallet_balance", mode="before")
    @classmethod
    def round_balance(cls, v):
        if isinstance(v, float):
            return Decimal(str(round(v, 2)))
        return v


class Property(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    base_price: Decimal = Field(default_factory=lambda: Decimal(str(round(random.uniform(80.0, 800.0), 2))))
    latitude: Decimal = Field(default_factory=lambda: Decimal(str(round(random.uniform(37.70, 37.80), 6))))
    longitude: Decimal = Field(default_factory=lambda: Decimal(str(round(random.uniform(-122.50, -122.35), 6))))

    @field_validator("base_price", mode="before")
    @classmethod
    def round_price(cls, v):
        if isinstance(v, float):
            return Decimal(str(round(v, 2)))
        return v

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def round_coords(cls, v):
        if isinstance(v, float):
            return Decimal(str(round(v, 6)))
        return v


class Booking(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    guest_id: str
    property_id: str
    total_cost: Decimal
    status: BookingStatus
    created_at: datetime

    @field_validator("total_cost", mode="before")
    @classmethod
    def round_cost(cls, v):
        if isinstance(v, float):
            return Decimal(str(round(v, 2)))
        return v


class WalletAuditLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    guest_id: str
    amount_changed: Decimal
    action_type: AuditAction
    balance_after: Decimal
    timestamp: datetime

    @field_validator("amount_changed", "balance_after", mode="before")
    @classmethod
    def round_amount(cls, v):
        if isinstance(v, float):
            return Decimal(str(round(v, 2)))
        return v


def generate_properties(count: int) -> List[Property]:
    properties = []
    for i in range(count):
        neighborhood = random.choice(SF_NEIGHBORHOODS)
        prop_type = random.choice(PROPERTY_TYPES)
        title = f"{prop_type} in {neighborhood}"
        
        lat = round(random.uniform(37.70, 37.80), 6)
        lon = round(random.uniform(-122.50, -122.35), 6)
        base_price = round(random.uniform(80.0, 800.0), 2)
        
        properties.append(Property(
            id=str(uuid.uuid4()),
            title=title,
            base_price=Decimal(str(base_price)),
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lon))
        ))
    return properties


def generate_guests(count: int) -> List[Guest]:
    return [Guest(
        id=str(uuid.uuid4()),
        name=fake.name(),
        wallet_balance=Decimal(str(round(random.uniform(50.0, 5000.0), 2)))
    ) for _ in range(count)]


def generate_bookings_and_audits(
    guests: List[Guest],
    properties: List[Property],
    booking_count: int,
    audit_count: int
) -> Tuple[List[Booking], List[WalletAuditLog]]:
    now = datetime.utcnow()
    statuses = list(BookingStatus)
    status_weights = [0.3, 0.2, 0.5]
    
    bookings = []
    audits = []
    
    for i in range(booking_count):
        guest = random.choice(guests)
        prop = random.choice(properties)
        
        nights = random.randint(1, 14)
        base_price = float(prop.base_price)
        total_cost = round(base_price * nights * random.uniform(0.9, 1.3), 2)
        
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        created_at = now - timedelta(days=random.randint(0, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        
        booking = Booking(
            id=str(uuid.uuid4()),
            guest_id=guest.id,
            property_id=prop.id,
            total_cost=Decimal(str(total_cost)),
            status=status,
            created_at=created_at
        )
        bookings.append(booking)
        
        if len(audits) < audit_count:
            action = random.choice(list(AuditAction))
            amount = round(random.uniform(10.0, 500.0), 2)
            balance_after = round(random.uniform(0.0, 5000.0), 2)
            audit_time = created_at + timedelta(minutes=random.randint(1, 120))
            
            audits.append(WalletAuditLog(
                id=str(uuid.uuid4()),
                guest_id=guest.id,
                amount_changed=Decimal(str(amount)),
                action_type=action,
                balance_after=Decimal(str(balance_after)),
                timestamp=audit_time
            ))
    
    while len(audits) < audit_count:
        guest = random.choice(guests)
        action = random.choice(list(AuditAction))
        amount = round(random.uniform(10.0, 500.0), 2)
        balance_after = round(random.uniform(0.0, 5000.0), 2)
        audit_time = now - timedelta(days=random.randint(0, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        
        audits.append(WalletAuditLog(
            id=str(uuid.uuid4()),
            guest_id=guest.id,
            amount_changed=Decimal(str(amount)),
            action_type=action,
            balance_after=Decimal(str(balance_after)),
            timestamp=audit_time
        ))
    
    return bookings, audits


def get_connection(uri: str):
    return psycopg2.connect(uri)


def seed_guests(conn, guests: List[Guest]) -> List[str]:
    cursor = conn.cursor()
    print(f"Seeding {len(guests):,} guests...")
    cursor.execute("TRUNCATE TABLE guests RESTART IDENTITY CASCADE;")
    
    guests_data = [(g.id, g.name, g.wallet_balance) for g in guests]
    
    execute_batch(
        cursor,
        "INSERT INTO guests (id, name, wallet_balance) VALUES (%s, %s, %s)",
        guests_data,
        page_size=BATCH_SIZE
    )
    conn.commit()
    cursor.close()
    print(f"  -> Inserted {len(guests):,} guests")
    return [g.id for g in guests]


def seed_properties(conn, properties: List[Property]) -> List[Property]:
    cursor = conn.cursor()
    print(f"Seeding {len(properties):,} properties...")
    cursor.execute("TRUNCATE TABLE properties RESTART IDENTITY CASCADE;")
    
    properties_data = [
        (p.id, p.title, p.base_price, p.latitude, p.longitude)
        for p in properties
    ]
    
    execute_batch(
        cursor,
        "INSERT INTO properties (id, title, base_price, latitude, longitude) VALUES (%s, %s, %s, %s, %s)",
        properties_data,
        page_size=BATCH_SIZE
    )
    conn.commit()
    cursor.close()
    print(f"  -> Inserted {len(properties):,} properties")
    return properties


def seed_bookings_and_audit_logs(
    conn,
    bookings: List[Booking],
    audits: List[WalletAuditLog]
):
    cursor = conn.cursor()
    print(f"Seeding {len(bookings):,} bookings and {len(audits):,} wallet audit logs...")
    cursor.execute("TRUNCATE TABLE bookings, wallet_audit_logs RESTART IDENTITY CASCADE;")
    
    bookings_data = [
        (b.id, b.guest_id, b.property_id, b.total_cost, b.status.value, b.created_at)
        for b in bookings
    ]
    
    execute_batch(
        cursor,
        "INSERT INTO bookings (id, guest_id, property_id, total_cost, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
        bookings_data,
        page_size=BATCH_SIZE
    )
    conn.commit()
    print(f"  -> Inserted {len(bookings):,} bookings")
    
    audit_data = [
        (a.id, a.guest_id, a.amount_changed, a.action_type.value, a.balance_after, a.timestamp)
        for a in audits
    ]
    
    execute_batch(
        cursor,
        "INSERT INTO wallet_audit_logs (id, guest_id, amount_changed, action_type, balance_after, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
        audit_data,
        page_size=BATCH_SIZE
    )
    conn.commit()
    print(f"  -> Inserted {len(audits):,} wallet audit logs")
    cursor.close()


def main():
    parser = argparse.ArgumentParser(description="StaySpot PostgreSQL Seeder")
    parser.add_argument("--uri", default="postgresql://postgres:postgres@localhost:5432/stayspot", help="PostgreSQL URI")
    parser.add_argument("--guests", type=int, default=GUEST_COUNT, help="Number of guests")
    parser.add_argument("--properties", type=int, default=PROPERTY_COUNT, help="Number of properties")
    parser.add_argument("--bookings", type=int, default=BOOKING_COUNT, help="Number of bookings")
    parser.add_argument("--audits", type=int, default=AUDIT_LOG_COUNT, help="Number of audit log entries")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help="Batch size")
    args = parser.parse_args()
    
    print("=" * 60)
    print("StaySpot PostgreSQL Seeder")
    print("=" * 60)
    print(f"PostgreSQL: {args.uri}")
    print(f"Guests: {args.guests:,}")
    print(f"Properties: {args.properties:,}")
    print(f"Bookings: {args.bookings:,}")
    print(f"Audit Logs: {args.audits:,}")
    print()
    
    conn = get_connection(args.uri)
    
    try:
        guests = generate_guests(args.guests)
        properties = generate_properties(args.properties)
        bookings, audits = generate_bookings_and_audits(guests, properties, args.bookings, args.audits)
        
        seed_guests(conn, guests)
        seed_properties(conn, properties)
        seed_bookings_and_audit_logs(conn, bookings, audits)
        
        print("\n✓ PostgreSQL seeding completed successfully!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
