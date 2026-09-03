CREATE UNIQUE INDEX idx_active_stay ON bookings (guest_id) WHERE status = 'CHECKED_IN';

CREATE INDEX idx_bookings_property_id ON bookings(property_id);
CREATE INDEX idx_wallet_audit_logs_guest_id ON wallet_audit_logs(guest_id);
