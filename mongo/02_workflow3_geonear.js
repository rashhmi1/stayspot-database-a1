/**
 * ============================================================================
 * Workflow 3: Trending Search Hotspots (MongoDB Geospatial Aggregation)
 * ============================================================================
 * 
 * Objective:
 *   Write a MongoDB $geoNear pipeline to cluster recent SearchSessions within
 *   a 5km radius of specific coordinates.
 * 
 * Pipeline Architecture:
 *   1. $geoNear:
 *      - Leverages 2dsphere index on `SearchSessions.location`
 *      - Filters strictly within 5,000 meters (5 km) of target coordinates
 *      - spherical: true calculates real-world geodesic spherical distances
 *      - Filters for recent sessions created within the active 2-hour window
 *   2. $project:
 *      - Extracts coordinates, distance, and projects spatial cluster keys
 *        (rounding coordinates to ~1.1km micro-cells)
 *   3. $group:
 *      - Clusters recent pin drops into localized demand hotspots
 *      - Aggregates search volume, unique searchers, average distance, and recency
 *   4. $addFields / $project:
 *      - Derives hotspot demand intensity rating and formatted coordinates
 *   5. $sort:
 *      - Ranks hotspots descending by search volume to surface top trending zones
 * 
 * Usage:
 *   mongosh stayspot 02_workflow3_geonear.js
 * ============================================================================
 */

const targetDb = typeof db !== "undefined" ? db.getSiblingDB("stayspot") : new Mongo().getDB("stayspot");

print("================================================================================");
print("Workflow 3: Trending Search Hotspots Pipeline");
print("Database: " + targetDb.getName());
print("================================================================================\n");

// -----------------------------------------------------------------------------
// Target Center Coordinates & Parameters
// -----------------------------------------------------------------------------
// Coordinates: Downtown San Francisco / Union Square Hub [longitude, latitude]
const TARGET_COORDINATES = [-122.4194, 37.7749];
const MAX_RADIUS_METERS = 5000; // 5 km radius limit
const RECENCY_WINDOW_HOURS = 2; // Active 2-hour window matching TTL index
const RECENCY_CUTOFF = new Date(Date.now() - RECENCY_WINDOW_HOURS * 60 * 60 * 1000);

print(`Target Center Coordinates : [Longitude: ${TARGET_COORDINATES[0]}, Latitude: ${TARGET_COORDINATES[1]}]`);
print(`Max Search Radius         : ${MAX_RADIUS_METERS} meters (${MAX_RADIUS_METERS / 1000} km)`);
print(`Recency Filter Cutoff     : >= ${RECENCY_CUTOFF.toISOString()} (Past ${RECENCY_WINDOW_HOURS} hours)\n`);

// -----------------------------------------------------------------------------
// Aggregation Pipeline Definition: Trending Search Hotspots
// -----------------------------------------------------------------------------
const trendingHotspotsPipeline = [
  // Stage 1: $geoNear - MUST be the first stage in pipeline
  {
    $geoNear: {
      near: {
        type: "Point",
        coordinates: TARGET_COORDINATES
      },
      distanceField: "distance_meters",
      maxDistance: MAX_RADIUS_METERS,
      spherical: true,
      query: {
        created_at: { $gte: RECENCY_CUTOFF }
      }
    }
  },

  // Stage 2: Spatial Discretization & Attribute Shaping
  {
    $project: {
      session_id: 1,
      user_id: 1,
      distance_meters: 1,
      created_at: 1,
      filters: 1,
      device_info: 1,
      raw_coordinates: "$location.coordinates",
      // Grid clustering: round coordinates to 2 decimal places (~1.1 km spatial resolution)
      cluster_lon: { $round: [{ $arrayElemAt: ["$location.coordinates", 0] }, 2] },
      cluster_lat: { $round: [{ $arrayElemAt: ["$location.coordinates", 1] }, 2] },
      // Proximity ring bucket for radial analysis
      distance_ring_km: {
        $concat: [
          { $toString: { $floor: { $divide: ["$distance_meters", 1000] } } },
          " - ",
          { $toString: { $add: [{ $floor: { $divide: ["$distance_meters", 1000] } }, 1] } },
          " km"
        ]
      }
    }
  },

  // Stage 3: $group - Spatial Clustering into Demand Hotspots
  {
    $group: {
      _id: {
        grid_longitude: "$cluster_lon",
        grid_latitude: "$cluster_lat"
      },
      total_searches: { $sum: 1 },
      unique_searchers: { $addToSet: "$user_id" },
      avg_distance_meters: { $avg: "$distance_meters" },
      min_distance_meters: { $min: "$distance_meters" },
      max_distance_meters: { $max: "$distance_meters" },
      latest_search_timestamp: { $max: "$created_at" },
      earliest_search_timestamp: { $min: "$created_at" },
      sample_session_ids: { $push: "$session_id" },
      sample_price_filters: { $push: "$filters.max_price" }
    }
  },

  // Stage 4: Hotspot Metrics Shaping
  {
    $project: {
      _id: 0,
      hotspot_cluster: {
        type: "Point",
        coordinates: ["$_id.grid_longitude", "$_id.grid_latitude"]
      },
      grid_coordinates: {
        longitude: "$_id.grid_longitude",
        latitude: "$_id.grid_latitude"
      },
      search_volume: "$total_searches",
      unique_users_count: { $size: "$unique_searchers" },
      avg_distance_meters: { $round: ["$avg_distance_meters", 1] },
      avg_distance_km: { $round: [{ $divide: ["$avg_distance_meters", 1000] }, 2] },
      min_distance_meters: { $round: ["$min_distance_meters", 1] },
      max_distance_meters: { $round: ["$max_distance_meters", 1] },
      latest_search_at: "$latest_search_timestamp",
      sample_session_count: { $size: "$sample_session_ids" },
      hotspot_status: {
        $switch: {
          branches: [
            { case: { $gte: ["$total_searches", 30] }, then: "CRITICAL_SURGE" },
            { case: { $gte: ["$total_searches", 20] }, then: "HIGH_DEMAND" },
            { case: { $gte: ["$total_searches", 10] }, then: "MODERATE_DEMAND" }
          ],
          default: "LOW_ACTIVITY"
        }
      }
    }
  },

  // Stage 5: $sort - Rank hotspots by search volume descending
  {
    $sort: {
      search_volume: -1,
      avg_distance_meters: 1
    }
  }
];

// -----------------------------------------------------------------------------
// Auxiliary Pipeline: Concentric Radial Distance Ring Distribution
// -----------------------------------------------------------------------------
const radialDensityPipeline = [
  {
    $geoNear: {
      near: {
        type: "Point",
        coordinates: TARGET_COORDINATES
      },
      distanceField: "distance_meters",
      maxDistance: MAX_RADIUS_METERS,
      spherical: true,
      query: {
        created_at: { $gte: RECENCY_CUTOFF }
      }
    }
  },
  {
    $bucket: {
      groupBy: "$distance_meters",
      boundaries: [0, 1000, 2000, 3000, 4000, 5000],
      default: "Other",
      output: {
        total_pin_drops: { $sum: 1 },
        unique_users: { $addToSet: "$user_id" },
        avg_distance_m: { $avg: "$distance_meters" }
      }
    }
  },
  {
    $project: {
      _id: 0,
      distance_ring: {
        $switch: {
          branches: [
            { case: { $eq: ["$_id", 0] }, then: "0 - 1 km (Inner Core)" },
            { case: { $eq: ["$_id", 1000] }, then: "1 - 2 km (Near Ring)" },
            { case: { $eq: ["$_id", 2000] }, then: "2 - 3 km (Mid Ring)" },
            { case: { $eq: ["$_id", 3000] }, then: "3 - 4 km (Outer Ring)" },
            { case: { $eq: ["$_id", 4000] }, then: "4 - 5 km (Perimeter)" }
          ],
          default: "Unknown"
        }
      },
      pin_drops_count: "$total_pin_drops",
      unique_searchers: { $size: "$unique_users" },
      avg_distance_m: { $round: ["$avg_distance_m", 1] }
    }
  }
];

// -----------------------------------------------------------------------------
// EXECUTION: Run Hotspot Clustering Pipeline
// -----------------------------------------------------------------------------
print("--------------------------------------------------------------------------------");
print("Executing Trending Search Hotspots Clustering Pipeline...");
print("--------------------------------------------------------------------------------");

const hotspotResults = targetDb.SearchSessions.aggregate(trendingHotspotsPipeline).toArray();

print(`Found ${hotspotResults.length} distinct trending spatial clusters within 5km radius:\n`);

let rank = 1;
let totalClusteredSearches = 0;
hotspotResults.forEach(h => {
  totalClusteredSearches += h.search_volume;
  print(`  [Rank #${rank}] Status: [${h.hotspot_status}]`);
  print(`    - Cluster Coordinates : [Lon: ${h.grid_coordinates.longitude}, Lat: ${h.grid_coordinates.latitude}]`);
  print(`    - Search Volume       : ${h.search_volume} sessions (${h.unique_users_count} unique searchers)`);
  print(`    - Distance Range      : ${h.min_distance_meters}m to ${h.max_distance_meters}m (Avg: ${h.avg_distance_meters}m / ${h.avg_distance_km}km)`);
  print(`    - Latest Pin Drop     : ${h.latest_search_at.toISOString()}`);
  print("");
  rank++;
});

print(`Total Pin Drops in 5km Radius: ${totalClusteredSearches}`);

// -----------------------------------------------------------------------------
// EXECUTION: Run Concentric Radial Distance Density
// -----------------------------------------------------------------------------
print("\n--------------------------------------------------------------------------------");
print("Radial Distance Density Breakdown (Concentric Rings):");
print("--------------------------------------------------------------------------------");
const radialResults = targetDb.SearchSessions.aggregate(radialDensityPipeline).toArray();
radialResults.forEach(r => {
  print(`  * ${r.distance_ring.padEnd(25)} : ${r.pin_drops_count.toString().padStart(4)} searches | Avg Distance: ${r.avg_distance_m}m | Searchers: ${r.unique_searchers}`);
});

// -----------------------------------------------------------------------------
// PERFORMANCE & INDEX UTILIZATION CHECK (explain)
// -----------------------------------------------------------------------------
print("\n--------------------------------------------------------------------------------");
print("Query Plan & Index Utilization Analysis (explain executionStats):");
print("--------------------------------------------------------------------------------");

const explainStats = targetDb.SearchSessions.explain("executionStats").aggregate(trendingHotspotsPipeline);

// Extract execution metrics
const executionSuccess = explainStats.stages || explainStats.executionStats;
print("[EXPLAIN] Aggregation Plan Summary:");
if (explainStats.stages && explainStats.stages.length > 0) {
  const geoNearStage = explainStats.stages[0].$geoNear;
  if (geoNearStage) {
    print(`  - Stage Name       : $geoNear`);
    print(`  - Spherical        : ${geoNearStage.spherical}`);
    print(`  - Max Distance     : ${geoNearStage.maxDistance} meters`);
  }
}

if (explainStats.executionStats) {
  print(`  - Execution Time   : ${explainStats.executionStats.executionTimeMillis} ms`);
  print(`  - Total Docs Examined: ${explainStats.executionStats.totalDocsExamined}`);
  print(`  - Total Keys Examined: ${explainStats.executionStats.totalKeysExamined}`);
} else if (explainStats.stages) {
  print("  - Stages in Pipeline : " + explainStats.stages.map(s => Object.keys(s)[0]).join(" -> "));
}

function explainSearchHotspots(targetLng, targetLat, maxDistanceMeters = 5000) {
  return db.SearchSessions.explain("executionStats").aggregate([
    {
      $geoNear: {
        near: {
          type: "Point",
          coordinates: [parseFloat(targetLng), parseFloat(targetLat)]
        },
        distanceField: "distanceInMeters",
        maxDistance: maxDistanceMeters,
        spherical: true
      }
    },
    {
      $group: {
        _id: {
          latGrid: { $round: [{ $arrayElemAt: ["$location.coordinates", 1] }, 3] },
          lngGrid: { $round: [{ $arrayElemAt: ["$location.coordinates", 0] }, 3] }
        },
        totalSearches: { $sum: 1 }
      }
    }
  ]);
}

const stats3 = explainSearchHotspots(-122.4194, 37.7749);
fs.writeFileSync("workflow3_execution_stats.json", EJSON.stringify(stats3, null, 2));

print("\n[SUCCESS] Workflow 3 executed successfully!");
