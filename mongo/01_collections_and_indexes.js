const targetDb = typeof db !== "undefined" ? db.getSiblingDB("stayspot") : new Mongo().getDB("stayspot");

print("================================================================================");
print("Initializing StaySpot MongoDB Schema & Indexes on database: " + targetDb.getName());
print("================================================================================\n");
function ensureCollectionWithValidator(dbInstance, collName, validatorDoc) {
  const existingColls = dbInstance.getCollectionNames();
  if (existingColls.includes(collName)) {
    print(`[INFO] Collection '${collName}' already exists. Updating schema validator...`);
    dbInstance.runCommand({
      collMod: collName,
      validator: validatorDoc,
      validationLevel: "moderate",
      validationAction: "error"
    });
  } else {
    print(`[INFO] Creating collection '${collName}' with schema validator...`);
    dbInstance.createCollection(collName, {
      validator: validatorDoc,
      validationLevel: "strict",
      validationAction: "error"
    });
  }
}
const propertyAmenitiesValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["property_id", "amenities", "house_rules", "accessibility_features"],
    properties: {
      property_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        description: "Foreign Key linking to PostgreSQL properties(id) - must be a valid UUID string"
      },
      property_title: {
        bsonType: "string",
        description: "Optional denormalized title for caching"
      },
      amenities: {
        bsonType: "array",
        description: "Array of general amenities available at the property",
        items: {
          bsonType: "string"
        }
      },
      house_rules: {
        bsonType: "array",
        minItems: 1,
        description: "Nested array of house rules (flexible: string statements or structured rule objects)",
        items: {
          bsonType: ["string", "object"]
        }
      },
      accessibility_features: {
        bsonType: "array",
        minItems: 1,
        description: "Nested array of accessibility features (e.g., step-free entrance, wide doorways)",
        items: {
          bsonType: ["string", "object"]
        }
      },
      safety_features: {
        bsonType: "array",
        description: "Optional nested array of safety items (e.g., smoke detector, fire extinguisher)",
        items: {
          bsonType: "string"
        }
      },
      host_guidelines: {
        bsonType: "object",
        description: "Flexible host notes, keyless entry instructions, or parking details"
      },
      updated_at: {
        bsonType: "date",
        description: "Timestamp of last catalog update"
      }
    },
    additionalProperties: true 
  }
};

ensureCollectionWithValidator(targetDb, "PropertyAmenities", propertyAmenitiesValidator);

const propertyReviewsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["property_id", "guest_id", "rating", "location_tags", "review_text", "created_at"],
    properties: {
      property_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        description: "Foreign Key linking to PostgreSQL properties(id) - valid UUID string"
      },
      guest_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        description: "Foreign Key linking to PostgreSQL guests(id) - valid UUID string"
      },
      booking_id: {
        bsonType: "string",
        description: "Optional reference linking to PostgreSQL bookings(id)"
      },
      rating: {
        bsonType: ["int", "double", "decimal"],
        minimum: 1,
        maximum: 5,
        description: "Overall review rating, bounded strictly between 1 and 5"
      },
      sub_ratings: {
        bsonType: "object",
        description: "Optional granular category ratings",
        properties: {
          cleanliness: { bsonType: ["int", "double"], minimum: 1, maximum: 5 },
          accuracy: { bsonType: ["int", "double"], minimum: 1, maximum: 5 },
          communication: { bsonType: ["int", "double"], minimum: 1, maximum: 5 },
          location: { bsonType: ["int", "double"], minimum: 1, maximum: 5 },
          check_in: { bsonType: ["int", "double"], minimum: 1, maximum: 5 },
          value: { bsonType: ["int", "double"], minimum: 1, maximum: 5 }
        }
      },
      location_tags: {
        bsonType: "array",
        minItems: 1,
        description: "Array of descriptive tags for review analytics (e.g., 'downtown', 'walkable')",
        items: {
          bsonType: "string"
        }
      },
      review_text: {
        bsonType: "string",
        minLength: 3,
        description: "Review commentary provided by guest"
      },
      created_at: {
        bsonType: "date",
        description: "Timestamp when review was submitted"
      }
    }
  }
};

ensureCollectionWithValidator(targetDb, "PropertyReviews", propertyReviewsValidator);

const searchSessionsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["session_id", "user_id", "location", "created_at"],
    properties: {
      session_id: {
        bsonType: "string",
        description: "Unique tracking session identifier"
      },
      user_id: {
        bsonType: "string",
        description: "Identifier of guest or anonymous searcher"
      },
      location: {
        bsonType: "object",
        required: ["type", "coordinates"],
        description: "GeoJSON Point representing pin drop location",
        properties: {
          type: {
            enum: ["Point"],
            description: "GeoJSON geometry type, must be 'Point'"
          },
          coordinates: {
            bsonType: "array",
            minItems: 2,
            maxItems: 2,
            description: "Coordinates in GeoJSON format: [longitude, latitude]",
            items: {
              bsonType: ["double", "int", "long", "decimal"]
            }
          }
        }
      },
      search_radius_meters: {
        bsonType: ["int", "double"],
        minimum: 100,
        maximum: 100000,
        description: "Search radius requested by user in meters"
      },
      filters: {
        bsonType: "object",
        description: "Search criteria applied during pin drop (price, amenities, etc.)"
      },
      device_info: {
        bsonType: "object",
        description: "Client metadata (platform, app_version)"
      },
      created_at: {
        bsonType: "date",
        description: "Timestamp of pin drop. Governed by 2-hour TTL expiration index"
      }
    }
  }
};

ensureCollectionWithValidator(targetDb, "SearchSessions", searchSessionsValidator);


print("\n--------------------------------------------------------------------------------");
print("Provisioning MongoDB Indexes & TTL Expiration Policies...");
print("--------------------------------------------------------------------------------");

try {
  const legacySessionIndexes = ["pin_2dsphere", "searchSessions_ttl", "userId_1", "createdAt_1"];
  const existingSessionIndexes = targetDb.SearchSessions.getIndexes().map(i => i.name);
  for (let name of legacySessionIndexes) {
    if (existingSessionIndexes.includes(name)) {
      print(`[MIGRATION] Dropping legacy index '${name}' on SearchSessions...`);
      targetDb.SearchSessions.dropIndex(name);
    }
  }

  const legacyReviewIndexes = ["locationTag_2dsphere", "propertyId_1", "createdAt_1"];
  const existingReviewIndexes = targetDb.PropertyReviews.getIndexes().map(i => i.name);
  for (let name of legacyReviewIndexes) {
    if (existingReviewIndexes.includes(name)) {
      print(`[MIGRATION] Dropping legacy index '${name}' on PropertyReviews...`);
      targetDb.PropertyReviews.dropIndex(name);
    }
  }
} catch (e) {
}

print("[INDEX] Creating 2dsphere index on SearchSessions.location...");
targetDb.SearchSessions.createIndex(
  { location: "2dsphere" },
  {
    name: "idx_searchsessions_location_2dsphere",
    background: true
  }
);

print("[INDEX] Creating 2-hour TTL index (7200 seconds) on SearchSessions.created_at...");
targetDb.SearchSessions.createIndex(
  { created_at: 1 },
  {
    name: "idx_searchsessions_created_at_ttl_2h",
    expireAfterSeconds: 7200,
    background: true
  }
);

print("[INDEX] Creating compound index on SearchSessions (user_id, created_at)...");
targetDb.SearchSessions.createIndex(
  { user_id: 1, created_at: -1 },
  {
    name: "idx_searchsessions_user_time",
    background: true
  }
);

print("[INDEX] Creating indexes on PropertyReviews...");

targetDb.PropertyReviews.createIndex(
  { property_id: 1, created_at: -1 },
  {
    name: "idx_reviews_property_created",
    background: true
  }
);

targetDb.PropertyReviews.createIndex(
  { rating: 1 },
  {
    name: "idx_reviews_rating",
    background: true
  }
);

targetDb.PropertyReviews.createIndex(
  { location_tags: 1 },
  {
    name: "idx_reviews_location_tags",
    background: true
  }
);

targetDb.PropertyReviews.createIndex(
  { guest_id: 1 },
  {
    name: "idx_reviews_guest_id",
    background: true
  }
);

print("[INDEX] Creating indexes on PropertyAmenities...");

targetDb.PropertyAmenities.createIndex(
  { property_id: 1 },
  {
    name: "idx_amenities_property_id_unique",
    unique: true,
    background: true
  }
);

targetDb.PropertyAmenities.createIndex(
  { amenities: 1 },
  {
    name: "idx_amenities_catalog",
    background: true
  }
);

print("\n================================================================================");
print("Active Indexes Summary:");
print("================================================================================");

print("\n--- SearchSessions Indexes ---");
targetDb.SearchSessions.getIndexes().forEach(idx => {
  print(`  * ${idx.name}: ${JSON.stringify(idx.key)} ${idx.expireAfterSeconds ? `(TTL: ${idx.expireAfterSeconds}s / ${idx.expireAfterSeconds/3600}h)` : ""}`);
});

print("\n--- PropertyReviews Indexes ---");
targetDb.PropertyReviews.getIndexes().forEach(idx => {
  print(`  * ${idx.name}: ${JSON.stringify(idx.key)}`);
});

print("\n--- PropertyAmenities Indexes ---");
targetDb.PropertyAmenities.getIndexes().forEach(idx => {
  print(`  * ${idx.name}: ${JSON.stringify(idx.key)} ${idx.unique ? "(UNIQUE)" : ""}`);
});

print("\n[SUCCESS] Collections and indexes provisioned successfully!");
