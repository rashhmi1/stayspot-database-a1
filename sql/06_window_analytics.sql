-- Workflow 2: SQL Window Analytics
-- Calculate a 7-day moving average of booking revenue per property, ranked by DENSE_RANK()

WITH daily_revenue AS (
    SELECT 
        property_id,
        DATE(created_at) AS booking_date,
        SUM(total_cost) AS daily_total
    FROM bookings
    WHERE status = 'COMPLETED'
    GROUP BY property_id, DATE(created_at)
),
moving_avg AS (
    SELECT
        property_id,
        booking_date,
        daily_total,
        AVG(daily_total) OVER (
            PARTITION BY property_id 
            ORDER BY booking_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS moving_avg_7d
    FROM daily_revenue
)
SELECT 
    property_id,
    booking_date,
    daily_total,
    ROUND(moving_avg_7d, 2) AS moving_avg_7d,
    DENSE_RANK() OVER (ORDER BY moving_avg_7d DESC) AS revenue_rank
FROM moving_avg
ORDER BY revenue_rank, property_id, booking_date;
