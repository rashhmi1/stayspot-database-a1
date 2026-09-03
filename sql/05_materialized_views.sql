CREATE MATERIALIZED VIEW mv_property_summary AS
SELECT 
    p.id AS property_id,
    p.title,
    COUNT(b.id) AS total_nights_booked,
    COALESCE(SUM(b.total_cost), 0) AS gross_revenue
FROM properties p
LEFT JOIN bookings b ON p.id = b.property_id AND b.status = 'COMPLETED'
GROUP BY p.id, p.title;

CREATE UNIQUE INDEX idx_mv_property_summary_id ON mv_property_summary(property_id);

CREATE OR REPLACE FUNCTION refresh_mv_property_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_property_summary;
END;
$$ LANGUAGE plpgsql;
