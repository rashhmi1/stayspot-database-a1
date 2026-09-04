
const fs = require("fs"); 
const path = require("path");

const targetDb = typeof db !== "undefined" ? db.getSiblingDB("stayspot") : new Mongo().getDB("stayspot");

print("================================================================================");
print("Workflow 4: Multi-Faceted Review Analytics Pipeline ($facet)");
print("Database: " + targetDb.getName());
print("================================================================================\n");

function buildReviewAnalyticsPipeline(filterQuery = {}) {
  const pipeline = [];

  
  if (filterQuery && Object.keys(filterQuery).length > 0) {
    pipeline.push({ $match: filterQuery });
  }

  
  pipeline.push({
    $facet: {
      
      rating_distributions: [
        {
          $group: {
            _id: "$rating",
            review_count: { $sum: 1 }
          }
        },
        {
          $sort: { _id: -1 } 
        },
        {
          $project: {
            _id: 0,
            rating_star: "$_id",
            count: "$review_count"
          }
        }
      ],

      
      
      most_frequent_tags: [
        {
          $unwind: {
            path: "$location_tags",
            preserveNullAndEmptyArrays: false
          }
        },
        {
          $group: {
            _id: "$location_tags",
            tag_frequency: { $sum: 1 },
            avg_rating_for_tag: { $avg: "$rating" }
          }
        },
        {
          $sort: {
            tag_frequency: -1,
            _id: 1
          }
        },
        {
          $limit: 10
        },
        {
          $project: {
            _id: 0,
            tag: "$_id",
            frequency: "$tag_frequency",
            avg_rating: { $round: ["$avg_rating_for_tag", 2] }
          }
        }
      ],

      overall_rating_summary: [
        {
          $group: {
            _id: null,
            total_reviews: { $sum: 1 },
            overall_avg_rating: { $avg: "$rating" },
            min_rating: { $min: "$rating" },
            max_rating: { $max: "$rating" },
            avg_cleanliness: { $avg: "$sub_ratings.cleanliness" },
            avg_location: { $avg: "$sub_ratings.location" },
            avg_communication: { $avg: "$sub_ratings.communication" }
          }
        },
        {
          $project: {
            _id: 0,
            total_reviews: 1,
            overall_avg_rating: { $round: ["$overall_avg_rating", 2] },
            min_rating: 1,
            max_rating: 1,
            sub_category_averages: {
              cleanliness: { $round: ["$avg_cleanliness", 2] },
              location: { $round: ["$avg_location", 2] },
              communication: { $round: ["$avg_communication", 2] }
            }
          }
        }
      ]
    }
  });

  
  pipeline.push({
    $project: {
      overall_summary: {
        $ifNull: [
          { $arrayElemAt: ["$overall_rating_summary", 0] },
          {
            total_reviews: 0,
            overall_avg_rating: 0,
            min_rating: 0,
            max_rating: 0,
            sub_category_averages: { cleanliness: 0, location: 0, communication: 0 }
          }
        ]
      },
      most_frequent_tags: "$most_frequent_tags",
      rating_distributions: {
        $map: {
          input: "$rating_distributions",
          as: "dist",
          in: {
            rating: "$$dist.rating_star",
            count: "$$dist.count",
            percentage: {
              $cond: [
                { $gt: [{ $arrayElemAt: ["$overall_rating_summary.total_reviews", 0] }, 0] },
                {
                  $round: [
                    {
                      $multiply: [
                        {
                          $divide: [
                            "$$dist.count",
                            { $arrayElemAt: ["$overall_rating_summary.total_reviews", 0] }
                          ]
                        },
                        100
                      ]
                    },
                    1
                  ]
                },
                0
              ]
            }
          }
        }
      }
    }
  });

  return pipeline;
}




function displayAnalyticsResults(title, results) {
  print("================================================================================");
  print(title);
  print("================================================================================");

  if (!results || results.length === 0) {
    print("  [No review records found matching criteria]\n");
    return;
  }

  const data = results[0];
  const summary = data.overall_summary;
  const distributions = data.rating_distributions || [];
  const tags = data.most_frequent_tags || [];

  print("\n1. OVERALL PROPERTY RATING SUMMARY:");
  print("--------------------------------------------------------------------------------");
  print(`  - Total Reviews Logged : ${summary.total_reviews}`);
  print(`  - Overall Avg Rating   : ${summary.overall_avg_rating} / 5.00 ⭐`);
  print(`  - Rating Range         : Min: ${summary.min_rating} ⭐ | Max: ${summary.max_rating} ⭐`);
  if (summary.sub_category_averages) {
    print(`  - Sub-Ratings Average  : Cleanliness: ${summary.sub_category_averages.cleanliness} | Location: ${summary.sub_category_averages.location} | Communication: ${summary.sub_category_averages.communication}`);
  }

  print("\n2. RATING DISTRIBUTIONS (1 TO 5 STARS):");
  print("--------------------------------------------------------------------------------");
  print("  Rating    Count      Share        Distribution Bar");
  print("  --------------------------------------------------");
  distributions.forEach(d => {
    const starStr = `${d.rating} Stars`.padEnd(9);
    const countStr = d.count.toString().padStart(5);
    const pctStr = `${d.percentage.toFixed(1)}%`.padStart(7);
    const barLength = Math.round(d.percentage / 2.5);
    const bar = "█".repeat(barLength);
    print(`  ${starStr} : ${countStr}  (${pctStr})  ${bar}`);
  });

  print("\n3. TOP 10 MOST FREQUENT REVIEW TAGS ($unwind):");
  print("--------------------------------------------------------------------------------");
  print("  Rank  Tag Identifier            Frequency    Avg Rating");
  print("  ------------------------------------------------------");
  let tagRank = 1;
  tags.forEach(t => {
    const rankStr = `#${tagRank}`.padStart(4);
    const tagStr = t.tag.padEnd(25);
    const freqStr = t.frequency.toString().padStart(6);
    const avgRStr = `${t.avg_rating} ⭐`.padStart(8);
    print(`  ${rankStr}  ${tagStr} : ${freqStr} reviews  |  ${avgRStr}`);
    tagRank++;
  });
  print("\n");
}

const globalPipeline = buildReviewAnalyticsPipeline();
const globalResults = targetDb.PropertyReviews.aggregate(globalPipeline).toArray();
displayAnalyticsResults("PLATFORM-WIDE REVIEW ANALYTICS (PORTFOLIO-LEVEL)", globalResults);

let singlePropertyPipeline = null;
const sampleProperty = targetDb.PropertyReviews.findOne({}, { property_id: 1, propertyId: 1 });
if (sampleProperty) {
  const propIdKey = sampleProperty.property_id ? "property_id" : "propertyId";
  const propertyId = sampleProperty[propIdKey];
  if (propertyId) {
    singlePropertyPipeline = buildReviewAnalyticsPipeline({ [propIdKey]: propertyId });
    const singlePropertyResults = targetDb.PropertyReviews.aggregate(singlePropertyPipeline).toArray();
    displayAnalyticsResults(`SINGLE PROPERTY REVIEW ANALYTICS (Property ID: ${propertyId})`, singlePropertyResults);
  }
}

print("--------------------------------------------------------------------------------");
print("Exporting Query Plan & executionStats to performance/mongo_execution_stats.json...");
print("--------------------------------------------------------------------------------");

// Prefer single-property pipeline to demonstrate index scan (IXSCAN) on idx_reviews_property_created
const facetExplain = singlePropertyPipeline
  ? targetDb.PropertyReviews.explain("executionStats").aggregate(singlePropertyPipeline)
  : targetDb.PropertyReviews.explain("executionStats").aggregate(globalPipeline);

function getStatsFilePath() {
  const currentDirCandidate = path.resolve("performance", "mongo_execution_stats.json");
  const parentDirCandidate = path.resolve("..", "performance", "mongo_execution_stats.json");

  if (fs.existsSync(path.dirname(currentDirCandidate))) {
    return currentDirCandidate;
  } else if (fs.existsSync(path.dirname(parentDirCandidate))) {
    return parentDirCandidate;
  }

  const defaultDir = path.resolve("performance");
  if (!fs.existsSync(defaultDir)) {
    fs.mkdirSync(defaultDir, { recursive: true });
  }
  return path.resolve(defaultDir, "mongo_execution_stats.json");
}

const statsFilePath = getStatsFilePath();
let statsList = [];
if (fs.existsSync(statsFilePath)) {
  try {
    const raw = fs.readFileSync(statsFilePath, "utf8");
    if (raw.trim()) {
      const parsed = EJSON.parse(raw);
      if (Array.isArray(parsed)) {
        statsList = parsed;
      } else {
        print(`[WARN] Existing content in ${statsFilePath} is not a list. Initializing empty list.`);
        statsList = [];
      }
    }
  } catch (err) {
    print(`[WARN] Could not parse existing ${statsFilePath}: ${err.message}. Initializing fresh list.`);
    statsList = [];
  }
}

statsList[1] = facetExplain;
fs.writeFileSync(statsFilePath, EJSON.stringify(statsList, null, 2));

print(`[SUCCESS] Workflow 4 execution stats saved to ${statsFilePath}`);
print("\n[SUCCESS] Workflow 4 executed successfully and execution stats exported!");
