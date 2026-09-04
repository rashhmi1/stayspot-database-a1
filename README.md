# StaySpot — Vacation Rental & Experiences: Database Layer

A polyglot-persistence backend for a vacation-rental platform: PostgreSQL
holds transactional data (guests, wallets, properties, bookings) and MongoDB
holds flexible/high-volume data (amenity catalogs, reviews, geospatial search
telemetry). This repo contains only the database layer — schema, indexes,
triggers, stored procedures, materialized views, and Mongo aggregation
pipelines — no application/API code.

## Architecture

| Concern | Engine | Why |
|---|---|---|
| Guests, wallets, wallet audit trail | PostgreSQL | Strong consistency, `CHECK` constraints, transactional debits |
| Properties, bookings | PostgreSQL | Relational integrity (FKs), partial unique index for check-in state |
| Amenities / house rules / accessibility features | MongoDB | Per-property shape varies; nested arrays of mixed string/object rules |
| Reviews | MongoDB | Structured but with optional sub-ratings and free-text tags |
| Search-pin telemetry | MongoDB | Very high write volume, geospatial (`2dsphere`), short-lived (TTL) |

There is **no enforced foreign key across the two engines** — Mongo documents
reference Postgres rows by copying the UUID as a plain string (see
`docs/mongo_schema_map.json` → `cross_database_relationships`). Referential
integrity between Postgres and Mongo is an application-layer responsibility.

## Repository Structure

```
sql/            DDL, indexes, triggers, stored procedures, materialized views, window analytics
mongo/          Collection validators, 2dsphere/TTL indexes, $geoNear and $facet pipelines
data_generation/  Seeders for both databases
performance/    EXPLAIN / executionStats output
docs/           ERD + Mongo schema map
```

## Setup

### 1. Provision the databases

```bash
# PostgreSQL (adjust connection string as needed)
export PG_URI="postgresql://postgres:postgres@localhost:5432/stayspot"
psql "$PG_URI" -f sql/01_schema_ddl.sql
psql "$PG_URI" -f sql/02_indexes.sql
psql "$PG_URI" -f sql/03_triggers_and_audit.sql
psql "$PG_URI" -f sql/04_stored_procedures.sql
psql "$PG_URI" -f sql/05_materialized_views.sql
# 06_window_analytics.sql is a query, not DDL — run it after seeding, not here

# MongoDB
mongosh "mongodb://localhost:27017/stayspot" mongo/01_collections_and_indexes.js
```

> **Before you run the above against real data**, read "Known issues &
> assumptions" below — `sql/01_schema_ddl.sql`'s `status` `CHECK` constraint
> currently disagrees with `sql/02_indexes.sql` and the seeder, which blocks
> every `CHECKED_IN` booking. Fix that line first (`'CHECKED IN'` →
> `'CHECKED_IN'`) or every seed run will error out partway through.

### 2. Install seeder dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r data_generation/requirements.txt
```

### 3. Seed data

```bash
python3 data_generation/postgres_seeder.py --uri "$PG_URI"
#   -> 10,000 guests, 1,000 properties, 50,000 bookings, 100,000 wallet_audit_logs

python3 data_generation/mongo_seeder.py --uri "mongodb://localhost:27017" --db stayspot
#   -> 500,000 SearchSessions geospatial pings (2h TTL, so the live count
#      drifts below 500k as older pings expire)

# To also seed PropertyAmenities and PropertyReviews:
python3 data_generation/mongo_seeder.py --uri "mongodb://localhost:27017" --db stayspot \
  --pg-uri "$PG_URI" --seed-all --reviews-per-property 5
#   -> 1,000 PropertyAmenities + 5,000 PropertyReviews (default)

### 4. Run the workflows

```bash
psql "$PG_URI" -f sql/06_window_analytics.sql          # Workflow 2
mongosh "mongodb://localhost:27017/stayspot" mongo/02_workflow3_geonear.js   # Workflow 3
mongosh "mongodb://localhost:27017/stayspot" mongo/03_workflow4_facet.js    # Workflow 4
```

`sp_execute_booking` (Workflow 1) is called like:

```sql
CALL sp_execute_booking(
  '<guest_id>'::uuid, '<property_id>'::uuid, 245.50
);
```

## Known Issues & Assumptions

These were found by reading the SQL/seeder/index files together — flagging
them here rather than quietly "fixing" them in the docs, since fixing the
actual `.sql`/`.py` files is a decision for you to make and commit.

1. **`status` value mismatch (blocks all `CHECKED_IN` seeding).**
   `sql/01_schema_ddl.sql`'s `CHECK` constraint allows `'CHECKED IN'` (space),
   but `sql/02_indexes.sql`'s partial index and
   `data_generation/postgres_seeder.py`'s `BookingStatus` enum both use
   `'CHECKED_IN'` (underscore). As shipped, every seeded `CHECKED_IN` row
   (~20% of `BOOKING_COUNT`) fails the `CHECK` constraint, and even if it
   didn't, `idx_active_stay`'s predicate would never match `'CHECKED IN'`
   anyway. **Fix:** change the `CHECK` constraint to use `'CHECKED_IN'`, or
   change both `02_indexes.sql` and the seeder to use `'CHECKED IN'` —
   whichever you use in application code should be the standard. All EXPLAIN
   plans in `performance/postgres_explain_analyzes.txt` assume the
   `CHECKED_IN` (underscore) version, since that's what two of the three
   files already agree on.

2. **Seeder doesn't enforce "one active stay per guest."**
   `generate_bookings_and_audits()` assigns guest and status independently at
   random, with no check for an existing `CHECKED_IN` row. With 10,000 guests
   and ~10,000 randomly-assigned `CHECKED_IN` bookings, expect thousands of
   `idx_active_stay` unique-violation errors mid-seed once Bug #1 is fixed.
   The seeder should route through `sp_execute_booking` (which it currently
   bypasses via direct `INSERT`) and skip/retry on conflict, or pre-shuffle
   guest IDs so each is used at most once for a `CHECKED_IN` row.

3. **`PropertyReviews` / `PropertyAmenities` are now bulk-seeded.**
   Run with `--seed-all --pg-uri "$PG_URI"` to populate both collections.
   The default is 5 reviews per property (configurable via `--reviews-per-property`).
   `performance/mongo_execution_stats.json`'s 128-document run was from a prior
   ad-hoc dataset — the new seeder generates at scale matching the 1,000 properties.

## Performance Summary

Full detail lives in `performance/postgres_explain_analyzes.txt` and the
real captured `performance/mongo_execution_stats.json`. Headlines:

- **`idx_active_stay` (partial unique index):** a guest's active-check-in
  lookup resolves as a single `Index Scan` with no `Filter` needed — the
  index's own `WHERE status = 'CHECKED_IN'` predicate absorbs that condition,
  so the plan only has to match on `guest_id`.
- **`sp_execute_booking`:** the wallet debit and the booking insert are two
  plans inside one PL/pgSQL block; a `CHECK` violation on the debit (would-be
  negative balance) is caught by the procedure's own `EXCEPTION` clause,
  which rolls back the block's implicit subtransaction before the `INSERT`
  ever runs — no explicit `ROLLBACK` statement needed.
- **Workflow 2 (moving average + `DENSE_RANK`):** both CTEs get inlined by
  the planner (single continuous plan, not materialized separately, since
  Postgres 12+ inlines singly-referenced CTEs). The base `Seq Scan` on
  `bookings` filtered to `COMPLETED` is expected/correct at this table size —
  no index makes a ~50%-selectivity scan cheaper than reading the table.
- **Workflow 3 (`$geoNear` clustering) — real captured numbers:** 264,856 of
  529,712 examined `SearchSessions` documents matched the 5km/2h window in
  909ms, using `idx_searchsessions_location_2dsphere`
  (`GEO_NEAR_2DSPHERE` stage). The `created_at` recency filter applies as a
  post-fetch filter, not an index-covered one, since MongoDB doesn't support
  a single compound 2dsphere+range scan the way relational engines do — this
  is expected geospatial-index behavior, not a missed index.
- **Workflow 4 (`$facet` review analytics) — real captured numbers:** on the
  128-document `PropertyReviews` test set, the unfiltered global pipeline
  does a `COLLSCAN` (no index matches "no filter"); a per-property call
  would use `idx_reviews_property_created` instead.

## Reference

- ERD: `docs/relational_erd.png` *(— the four
  PostgreSQL tables and their FKs are fully described in
  `sql/01_schema_ddl.sql` )*
- Mongo document/validator/index map: `docs/mongo_schema_map.json`
- Postgres EXPLAIN plans: `performance/postgres_explain_analyzes.txt`
- Real Mongo `executionStats` capture: `performance/mongo_execution_stats.json`
